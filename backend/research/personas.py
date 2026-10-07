"""Customer personas: an LLM-designed segment mix, and illustrative LLM-voiced reactions.

Two separate uses, with different standing:

1. DESIGN. The model proposes a `PersonaMix` (segment shares and bounded sensitivity parameters).
   The seeded generator turns it into respondents, so numbers stay reproducible: same mix + seed =
   same respondents. The model never writes a respondent or a price.
2. VOICE. The model writes a short quote per persona about a price. This is labelled illustrative,
   never feeds a number, and every figure in it must already appear in the supplied facts.

Everything here is synthetic. Nothing is fitted.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Protocol

from pydantic import BaseModel, Field, model_validator

from backend.agent.grounding import _NUMBER, _PACK_LABEL, _evidence_numbers, _rounded
from backend.assumptions.assumptions import FORMATS
from backend.research.evidence import LABEL, run_research

DESIGN_LABEL = "SYNTHETIC · LLM-DESIGNED PERSONAS"
VOICE_LABEL = "ILLUSTRATIVE · LLM-VOICED, NOT EVIDENCE"
_SUM_TOLERANCE = 0.01  # the model's shares may be off by rounding; they are rescaled to exactly 1, never silently reshaped


class PackMix(BaseModel):
    """How a persona's respondents split across the four observed packs (follows FORMATS)."""

    can_330ml: float = Field(ge=0, le=1)
    pet_500ml: float = Field(ge=0, le=1)
    bottle_1500ml: float = Field(ge=0, le=1)
    multipack_6x330ml: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _sums_to_one(self) -> PackMix:
        total = sum(getattr(self, f) for f in FORMATS)
        if abs(total - 1) > _SUM_TOLERANCE:
            raise ValueError(f"pack_mix must sum to 1, got {total:.3f}")
        return self


class PersonaSpec(BaseModel):
    """One customer segment. `description` is display text only and is treated as untrusted data."""

    name: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z][A-Za-z '\-]{1,39}$")
    description: str = Field(max_length=240)
    share: float = Field(gt=0, le=1)
    price_sensitivity: float = Field(
        ge=0, le=1
    )  # 0-1 scale defined by the registry's consumer generator
    promotion_sensitivity: float = Field(ge=0, le=1)
    pack_mix: PackMix


class PersonaMix(BaseModel):
    personas: list[PersonaSpec] = Field(min_length=2, max_length=6)
    note: str = Field(default="", max_length=400)

    @model_validator(mode="after")
    def _valid_mix(self) -> PersonaMix:
        total = sum(p.share for p in self.personas)
        if abs(total - 1) > _SUM_TOLERANCE:
            raise ValueError(f"persona shares must sum to 1, got {total:.3f}")
        names = [p.name.strip().lower() for p in self.personas]
        if len(set(names)) != len(names):
            raise ValueError("persona names must be unique")
        if any(p.share < 0.05 for p in self.personas):
            raise ValueError("every persona needs a share of at least 5%")
        return self

    def normalised(self) -> PersonaMix:
        """Rescale shares and pack mixes so they sum to exactly 1 (they were within tolerance already)."""
        total = sum(p.share for p in self.personas)
        fixed = []
        for p in self.personas:
            pack_total = sum(getattr(p.pack_mix, f) for f in FORMATS)
            pack = PackMix(**{f: getattr(p.pack_mix, f) / pack_total for f in FORMATS})
            fixed.append(p.model_copy(update={"share": p.share / total, "pack_mix": pack}))
        return self.model_copy(update={"personas": fixed})

    def mix_hash(self) -> str:
        body = json.dumps(
            self.normalised().model_dump(mode="json", exclude={"note"}),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(body.encode()).hexdigest()


class PersonaVoice(BaseModel):
    persona: str = Field(max_length=40)
    quote: str = Field(max_length=300)
    objections: list[str] = Field(default_factory=list, max_length=3)
    would_change_mind: str = Field(default="", max_length=160)


class PersonaVoices(BaseModel):
    voices: list[PersonaVoice] = Field(min_length=1, max_length=6)


class PersonaLLM(Protocol):
    model_id: str

    def design_personas(self, brief: str, feedback: list[str] | None = None) -> PersonaMix: ...
    def persona_voices(
        self, facts: dict[str, Any], feedback: list[str] | None = None
    ) -> PersonaVoices: ...


class PersonaError(ValueError):
    """The model could not produce a valid mix or a grounded set of reactions."""


def design_mix(llm: PersonaLLM, brief: str, attempts: int = 2) -> PersonaMix:
    """Ask the model for a mix. A mix that fails validation is retried once with the reason, never repaired."""
    feedback: list[str] = []
    for _ in range(attempts):
        try:
            return llm.design_personas(brief[:1000], feedback)
        except Exception as exc:  # noqa: BLE001 - provider errors and schema errors both end in a retry or PersonaError
            feedback = [type(exc).__name__ + ": " + str(exc)[:300]]
            last = exc
    raise PersonaError("The model did not return a valid persona mix: " + str(last)[:200])


def persona_report(
    consumers: dict, mix: PersonaMix, pack: str, prices: list[float] | None = None
) -> dict:
    """Per-persona price evidence, from the same descriptive rules as the overall research (no model, no fitting)."""
    out = []
    for persona in mix.normalised().personas:
        part = [r for r in consumers["respondents"] if r["segment"] == persona.name]
        entry: dict[str, Any] = {
            "name": persona.name,
            "description": persona.description,
            "share": round(persona.share, 4),
            "respondents": len(part),
            "price_sensitivity": persona.price_sensitivity,
            "promotion_sensitivity": persona.promotion_sensitivity,
        }
        sub = {
            **consumers,
            "respondents": part,
            "sample_size": len(part),
            "data_hash": hashlib.sha256(json.dumps(part, sort_keys=True).encode()).hexdigest(),
        }
        try:
            wtp = run_research("Willingness to Pay", sub, None, pack)
            gg = run_research("Gabor-Granger", sub, prices, pack)
            entry["wtp"] = wtp.outputs
            entry["acceptance_by_price"] = gg.outputs["acceptance_share_by_price"]
        except (
            ValueError
        ):  # fewer than two respondents on this pack: say so instead of inventing a curve
            entry["wtp"], entry["acceptance_by_price"] = None, None
        out.append(entry)
    return {
        "label": LABEL,
        "pack": pack,
        "mix_hash": mix.mix_hash(),
        "data_hash": consumers["data_hash"],
        "sample_size": consumers["sample_size"],
        "personas": out,
    }


def _facts_for_voices(report: dict, price: float) -> dict:
    """Only figures the model may quote. Acceptance is given as a whole-number percent so a quote can match it."""
    facts = []
    for p in report["personas"]:
        accept = p["acceptance_by_price"] or {}
        near = min(accept, key=lambda k: abs(float(k) - price), default=None)
        facts.append(
            {
                "persona": p["name"],
                "description": p["description"],
                "share_pct": round(p["share"] * 100),
                "median_willingness_to_pay": (p["wtp"] or {}).get("p50"),
                "acceptance_pct_at_nearest_tested_price": None
                if near is None
                else round(accept[near] * 100),
                "nearest_tested_price": None if near is None else float(near),
            }
        )
    return {"pack": report["pack"], "price_tested": price, "personas": facts}


def ungrounded_numbers(voices: PersonaVoices, facts: dict) -> list[str]:
    """Numbers in a quote that are not in the supplied facts. Pack names ("500ml") are labels, not claims."""
    allowed = _evidence_numbers(facts)
    bad = []
    for v in voices.voices:
        for text in (v.quote, v.would_change_mind, *v.objections):
            for token in _NUMBER.findall(_PACK_LABEL.sub(" ", text)):
                if (number := _rounded(token)) is not None and number not in allowed:
                    bad.append(token)
    return sorted(set(bad))


def voice_personas(llm: PersonaLLM, report: dict, price: float, attempts: int = 2) -> dict:
    facts = _facts_for_voices(report, price)
    feedback: list[str] = []
    for _ in range(attempts):
        voices = llm.persona_voices(facts, feedback)
        names = {p["persona"] for p in facts["personas"]}
        bad = ungrounded_numbers(voices, facts)
        unknown = [v.persona for v in voices.voices if v.persona not in names]
        if not bad and not unknown:
            return {
                "label": VOICE_LABEL,
                "facts": facts,
                "voices": [v.model_dump() for v in voices.voices],
            }
        feedback = (
            [f"These numbers are not in the facts, remove them: {', '.join(bad)}"] if bad else []
        ) + ([f"Unknown personas: {', '.join(unknown)}"] if unknown else [])
    raise PersonaError(
        "The model's reactions quoted numbers that are not in the evidence: " + "; ".join(feedback)
    )


class ScriptedPersonaLLM:
    """Offline stand-in for tests: a fixed mix and templated reactions that only quote supplied facts."""

    model_id = "scripted-fake-llm"
    provider = "scripted"
    usage: dict = {}

    def design_personas(self, brief: str, feedback: list[str] | None = None) -> PersonaMix:
        del brief, feedback
        return PersonaMix(
            personas=[
                PersonaSpec(
                    name="Budget student",
                    description="Buys the cheapest pack and waits for deals.",
                    share=0.4,
                    price_sensitivity=0.85,
                    promotion_sensitivity=0.8,
                    pack_mix=PackMix(
                        can_330ml=0.5, pet_500ml=0.3, bottle_1500ml=0.1, multipack_6x330ml=0.1
                    ),
                ),
                PersonaSpec(
                    name="Busy family",
                    description="Stocks up on larger packs.",
                    share=0.35,
                    price_sensitivity=0.45,
                    promotion_sensitivity=0.4,
                    pack_mix=PackMix(
                        can_330ml=0.1, pet_500ml=0.2, bottle_1500ml=0.4, multipack_6x330ml=0.3
                    ),
                ),
                PersonaSpec(
                    name="Loyal regular",
                    description="Sticks to one brand and rarely switches.",
                    share=0.25,
                    price_sensitivity=0.2,
                    promotion_sensitivity=0.2,
                    pack_mix=PackMix(
                        can_330ml=0.25, pet_500ml=0.35, bottle_1500ml=0.2, multipack_6x330ml=0.2
                    ),
                ),
            ]
        )

    def persona_voices(
        self, facts: dict[str, Any], feedback: list[str] | None = None
    ) -> PersonaVoices:
        del feedback
        return PersonaVoices(
            voices=[
                PersonaVoice(
                    persona=p["persona"],
                    quote=f"At ₹{facts['price_tested']:g} about {p['acceptance_pct_at_nearest_tested_price']}% of people like me would still buy."
                    if p["acceptance_pct_at_nearest_tested_price"] is not None
                    else "I cannot say for this pack.",
                    objections=["It feels expensive next to the shelf price."],
                    would_change_mind="A promotion would help.",
                )
                for p in facts["personas"]
            ]
        )


_ = re  # re is used by the pattern constants above via pydantic
