"""Synthetic consumer evidence and non-estimating pricing research methods.

Research output is *candidate generation* only. Volume, revenue and margin come
from the deterministic engine via `research_to_scenarios`. Nothing here fits or
learns a model: WTP / Gabor-Granger / Van Westendorp are descriptive rules over
synthetic respondents, and the conjoint simulation uses supplied part-worths.
Every tunable number is read from the assumptions registry.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from backend.assumptions import registry
from backend.assumptions.assumptions import (
    ASSUMPTIONS,
    BRANDS,
    FORMATS,
    REFERENCE_PRICE_BY_FORMAT,
    REGIONS,
    RESEARCH_ASSUMPTION_IDS,
    SKU_IDS,
)
from backend.assumptions.assumptions import (
    CONSUMER_GENERATOR_SEED as GEN,
)
from backend.engine.batch import ENGINE_VERSION, _support_envelope, evaluate_batch
from backend.engine.scenario import Lever, Scenario
from backend.engine.support import nearest_supported
from backend.model.spec import build_param_draws

LABEL = "SYNTHETIC CONSUMER EVIDENCE"
CONJOINT_STATEMENT = (
    "This simulation uses supplied synthetic utilities. "
    "It does not estimate or fit consumer utilities."
)
METHODOLOGIES = ("Willingness to Pay", "Gabor-Granger", "Van Westendorp Price Sensitivity Meter")
CONJOINT_METHOD = "Conjoint simulation (supplied utilities)"


def _hash(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_price(pack: str) -> float:
    if pack not in REFERENCE_PRICE_BY_FORMAT:
        raise ValueError(f"unsupported pack {pack!r}; observed packs are {FORMATS}")
    return float(registry.get(REFERENCE_PRICE_BY_FORMAT[pack].id).value)


def default_sample_size() -> int:
    return int(registry.get("A-026").value)


def generate_consumers(seed: int = 42, sample_size: int | None = None) -> dict:
    """Create synthetic, non-PII respondents and comments from fixed distributions."""
    sample_size = default_sample_size() if sample_size is None else sample_size
    low, high = registry.get("A-026").valid_range
    if not low <= sample_size <= high:
        raise ValueError(f"sample_size must be between {int(low)} and {int(high)}")
    rng = np.random.default_rng(seed)
    segments = GEN["segments"]
    rows = []
    for i in range(sample_size):
        segment = segments[i % len(segments)]
        price_sens = float(
            np.clip(
                rng.normal(
                    GEN["price_sensitivity_mean"][segment], GEN["sensitivity_sigma"]["price"]
                ),
                0,
                1,
            )
        )
        promo_sens = float(
            np.clip(
                rng.normal(
                    GEN["promotion_sensitivity_mean"][segment],
                    GEN["sensitivity_sigma"]["promotion"],
                ),
                0,
                1,
            )
        )
        pack = str(rng.choice(FORMATS, p=GEN["pack_mix"]))
        current_price = reference_price(pack)
        wtp = round(
            current_price
            * (
                1
                + (
                    GEN["wtp_premium_at_zero_sensitivity"]
                    - price_sens * GEN["wtp_sensitivity_slope"]
                )
                + rng.normal(0, GEN["wtp_noise_sigma"])
            ),
            2,
        )
        vw = np.sort(
            [
                wtp * GEN["vw_factors"][k] * (1 + rng.normal(0, GEN["vw_noise_sigma"]))
                for k in ("too_cheap", "cheap", "expensive", "too_expensive")
            ]
        )
        if segment == "deal_responsive" or promo_sens > GEN["promo_comment_threshold"]:
            comment = f"I normally buy this only when it is on promotion; around ₹{round(wtp)} feels fair."
        elif pack in ("bottle_1500ml", "multipack_6x330ml"):
            comment = "I prefer the bigger pack because it gives better value for my family."
        elif price_sens < GEN["low_price_sensitivity_comment_threshold"]:
            comment = "A small price increase would not change my purchase."
        else:
            comment = f"I usually wait for offers. At ₹{round(wtp * 1.05)} I would probably switch."
        rows.append(
            {
                "respondent_id": f"SYN-{i + 1:05d}",
                "segment": segment,
                "age_band": str(rng.choice(GEN["age_bands"], p=GEN["age_mix"])),
                "region": str(rng.choice(REGIONS)),
                "current_brand": str(rng.choice(BRANDS)),
                "current_pack": pack,
                "current_price": current_price,
                "purchase_frequency": str(
                    rng.choice(GEN["purchase_frequency"], p=GEN["purchase_frequency_mix"])
                ),
                "price_sensitivity": round(price_sens, 4),
                "promotion_sensitivity": round(promo_sens, 4),
                "pack_preference": pack,
                "willingness_to_pay": wtp,
                "vw_too_cheap": round(float(vw[0]), 2),
                "vw_cheap": round(float(vw[1]), 2),
                "vw_expensive": round(float(vw[2]), 2),
                "vw_too_expensive": round(float(vw[3]), 2),
                "comment": comment,
            }
        )
    return {
        "label": LABEL,
        "seed": seed,
        "sample_size": sample_size,
        "respondents": rows,
        "data_hash": _hash(rows),
    }


def summarize_consumers(consumers: dict, comment_sample: int = 5) -> dict:
    """Compact, fully numeric summary (what the agent sees instead of every row)."""
    rows = consumers["respondents"]
    segments: dict[str, dict] = {}
    for name in GEN["segments"]:
        part = [r for r in rows if r["segment"] == name]
        if part:
            segments[name] = {
                "count": len(part),
                "mean_price_sensitivity": round(
                    float(np.mean([r["price_sensitivity"] for r in part])), 4
                ),
                "mean_promotion_sensitivity": round(
                    float(np.mean([r["promotion_sensitivity"] for r in part])), 4
                ),
            }
    wtp_by_pack = {}
    for pack in FORMATS:
        values = [r["willingness_to_pay"] for r in rows if r["current_pack"] == pack]
        if values:
            wtp_by_pack[pack] = {
                "respondents": len(values),
                "mean_wtp": round(float(np.mean(values)), 2),
            }
    sample = [
        {"respondent_id": r["respondent_id"], "segment": r["segment"], "comment": r["comment"]}
        for r in rows[:comment_sample]
    ]
    return {
        "label": LABEL,
        "seed": consumers["seed"],
        "sample_size": len(rows),
        "data_hash": consumers["data_hash"],
        "segments": segments,
        "wtp_by_pack": wtp_by_pack,
        "sample_comments": sample,
        "note": "Comments are synthetic qualitative evidence for explanation only, not demand observations.",
    }


@dataclass(frozen=True)
class ResearchResult:
    methodology: str
    research_id: str
    sample_size: int
    inputs: dict
    outputs: dict
    candidates: list[dict]
    assumptions: list[str]
    assumption_ids: list[str]
    limitations: list[str]
    source_data_hash: str
    result_hash: str


def _used(*ids: str) -> tuple[list[str], list[str]]:
    """Read ids through the registry (so coverage is tracked) and describe them."""
    registry_values = [registry.get(item) for item in ids]
    return sorted(ids), [f"{a.id}: {a.label} = {a.value}" for a in registry_values]


def _finalize(
    methodology: str,
    evidence: dict,
    inputs: dict,
    outputs: dict,
    candidates: list[dict],
    ids: tuple[str, ...],
    limitations: list[str],
) -> ResearchResult:
    assumption_ids, assumptions = _used(*ids)
    payload = {
        "methodology": methodology,
        "inputs": inputs,
        "outputs": outputs,
        "candidates": candidates,
        "sample_size": len(evidence["respondents"]),
        "source_data_hash": evidence["data_hash"],
        "assumption_ids": assumption_ids,
    }
    result_hash = _hash(payload)
    return ResearchResult(
        methodology,
        "RES-" + result_hash[:12].upper(),
        len(evidence["respondents"]),
        inputs,
        outputs,
        candidates,
        assumptions,
        assumption_ids,
        [
            "Synthetic sample is not representative of real consumers.",
            "Research results generate candidates only; commercial outcomes come from the RGM engine.",
            *limitations,
        ],
        evidence["data_hash"],
        result_hash,
    )


def _candidate(
    pack: str,
    price: float,
    source_metric: str,
    promotion_depth_pct: float = 0.0,
    brand: str | None = None,
) -> dict:
    row = {
        "pack": pack,
        "price": round(float(price), 2),
        "promotion_depth_pct": promotion_depth_pct,
        "source_metric": source_metric,
    }
    if brand is not None:
        row["brand"] = brand
    return row


def _dedupe(candidates: list[dict]) -> list[dict]:
    seen, out = set(), []
    for item in candidates:
        key = (item.get("brand"), item["pack"], item["price"], item["promotion_depth_pct"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _crossing(grid: np.ndarray, falling: np.ndarray, rising: np.ndarray) -> float | None:
    """First price where a falling curve meets a rising one (linear interpolation)."""
    gap = falling - rising
    for i in range(len(grid) - 1):
        if gap[i] > 0 >= gap[i + 1] or gap[i] == 0:
            if gap[i] == gap[i + 1]:
                return float(grid[i])
            return float(grid[i] + (grid[i + 1] - grid[i]) * gap[i] / (gap[i] - gap[i + 1]))
    return None


def run_research(
    methodology: str, evidence: dict, prices: list[float] | None = None, pack: str = "pet_500ml"
) -> ResearchResult:
    """Apply transparent descriptive rules to respondent answers for one observed pack."""
    ref = reference_price(pack)
    rows = [r for r in evidence["respondents"] if r["current_pack"] == pack]
    if len(rows) < 2:
        raise ValueError(f"need at least 2 synthetic respondents for {pack}; got {len(rows)}")
    wtp = np.asarray([r["willingness_to_pay"] for r in rows], dtype=float)
    inputs = {
        "methodology": methodology,
        "pack": pack,
        "reference_price": ref,
        "prices": list(prices or []),
        "respondents_used": len(rows),
        "sample_label": LABEL,
    }
    if methodology == "Willingness to Pay":
        quantiles = [float(q) for q in registry.get("A-032").value]
        outputs = {f"p{round(q * 100)}": round(float(np.quantile(wtp, q)), 2) for q in quantiles}
        outputs["mean"] = round(float(wtp.mean()), 2)
        candidates = [
            _candidate(pack, np.quantile(wtp, q), f"P{round(q * 100)} WTP") for q in quantiles
        ]
        ids = ("A-026", "A-028", "A-029", "A-030", "A-031", "A-032")
        limits = ["WTP is stated, not observed; it is not a purchase probability."]
    elif methodology == "Gabor-Granger":
        grid = sorted(
            {round(float(p), 2) for p in (prices or [ref * m for m in registry.get("A-034").value])}
        )
        threshold = float(registry.get("A-033").value)
        accept = {str(p): round(float(np.mean(wtp >= p)), 4) for p in grid}
        index = {str(p): round(p * accept[str(p)], 4) for p in grid}
        best = max(grid, key=lambda p: (index[str(p)], -p))
        passing = [p for p in grid if accept[str(p)] >= threshold]
        outputs = {
            "acceptance_share_by_price": accept,
            "revenue_index_by_price": index,
            "revenue_index_maximum_price": best,
        }
        candidates = [_candidate(pack, best, "Gabor-Granger revenue-index maximum")]
        if passing:
            candidates.append(
                _candidate(pack, max(passing), "Gabor-Granger highest accepted price")
            )
        ids = ("A-026", "A-028", "A-029", "A-030", "A-031", "A-033", "A-034")
        limits = [
            "The revenue index is price x stated acceptance per respondent, not a volume or revenue forecast."
        ]
    elif methodology == "Van Westendorp Price Sensitivity Meter":
        answers = {
            k: np.asarray([r["vw_" + k] for r in rows], dtype=float)
            for k in ("too_cheap", "cheap", "expensive", "too_expensive")
        }
        step = float(registry.get("A-035").value)
        grid = np.arange(
            np.floor(min(a.min() for a in answers.values())),
            np.ceil(max(a.max() for a in answers.values())) + step,
            step,
        )
        too_cheap = np.array([(answers["too_cheap"] >= p).mean() for p in grid])
        not_cheap = 1 - np.array([(answers["cheap"] >= p).mean() for p in grid])
        not_expensive = 1 - np.array([(answers["expensive"] <= p).mean() for p in grid])
        too_expensive = np.array([(answers["too_expensive"] <= p).mean() for p in grid])
        cheap = 1 - not_cheap
        expensive = 1 - not_expensive
        points = {
            "pmc": _crossing(grid, too_cheap, not_cheap),
            "opp": _crossing(grid, too_cheap, too_expensive),
            "ipp": _crossing(grid, cheap, expensive),
            "pme": _crossing(grid, not_expensive, too_expensive),
        }
        outputs = {k: None if v is None else round(v, 2) for k, v in points.items()}
        candidates = [
            _candidate(pack, points[k], label)
            for k, label in (
                ("opp", "Van Westendorp optimal price point"),
                ("ipp", "Van Westendorp indifference price point"),
            )
            if points[k] is not None
        ]
        ids = ("A-026", "A-028", "A-029", "A-030", "A-031", "A-035")
        limits = [
            "Price points are curve intersections on a fixed grid; they are not demand estimates."
        ]
    else:
        raise ValueError("unsupported research methodology")
    return _finalize(methodology, evidence, inputs, outputs, _dedupe(candidates), ids, limits)


def _promotion_depth(label: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)% off", label)
    return float(match.group(1)) if match else 0.0


def conjoint_simulation(
    consumers: dict,
    alternatives: list[dict],
    utilities: dict | None = None,
    focus_brand: str = "Aurora",
) -> ResearchResult:
    """Deterministic multinomial-logit choice shares from supplied part-worths only."""
    if not alternatives:
        raise ValueError("at least one alternative is required")
    supplied = json.loads(
        json.dumps(utilities if utilities is not None else registry.get("A-037").value)
    )
    scale = float(registry.get("A-027").value)
    weight = float(registry.get("A-036").value)
    for group in ("brand", "pack", "promotion"):
        if not isinstance(supplied.get(group), dict):
            raise ValueError(f"supplied utilities need a {group!r} table")
    for key in ("pack_match_bonus", "price_slope"):
        if not isinstance(supplied.get(key), (int, float)):
            raise ValueError(f"supplied utilities need a numeric {key!r}")
    rows = consumers["respondents"]
    price_sens = np.asarray([r["price_sensitivity"] for r in rows])
    promo_sens = np.asarray([r["promotion_sensitivity"] for r in rows])
    pack_pref = np.asarray([r["pack_preference"] for r in rows])
    columns = []
    for alt in alternatives:
        brand, pack, promotion = alt.get("brand"), alt.get("pack"), alt.get("promotion", "None")
        price = float(alt.get("price", 0))
        if (
            brand not in supplied["brand"]
            or pack not in supplied["pack"]
            or promotion not in supplied["promotion"]
        ):
            raise ValueError(f"alternative {alt} uses a level with no supplied utility")
        if price <= 0:
            raise ValueError("alternative price must be positive")
        ratio = price / reference_price(pack)
        columns.append(
            scale
            * (
                supplied["brand"][brand]
                + supplied["pack"][pack]
                + supplied["pack_match_bonus"] * (pack_pref == pack)
                + supplied["price_slope"] * (ratio - 1) * (1 + weight * (price_sens - 0.5))
                + supplied["promotion"][promotion] * (1 + weight * (promo_sens - 0.5))
            )
        )
    utility = np.column_stack(columns)
    weights = np.exp(utility - utility.max(axis=1, keepdims=True))
    probability = weights / weights.sum(axis=1, keepdims=True)
    shares = probability.mean(axis=0)
    by_segment = {
        name: [
            round(float(x) * 100, 2)
            for x in probability[[r["segment"] == name for r in rows]].mean(axis=0)
        ]
        for name in GEN["segments"]
        if any(r["segment"] == name for r in rows)
    }
    pct = [round(float(x) * 100, 2) for x in shares]
    candidates = sorted(
        [
            _candidate(
                a["pack"],
                a["price"],
                f"Conjoint simulated choice share {pct[i]:.1f}%",
                _promotion_depth(a.get("promotion", "None")),
                a["brand"],
            )
            for i, a in enumerate(alternatives)
            if a["brand"] == focus_brand
        ],
        key=lambda c: -float(c["source_metric"].split()[-1].rstrip("%")),
    )
    inputs = {
        "methodology": CONJOINT_METHOD,
        "alternatives": alternatives,
        "focus_brand": focus_brand,
        "supplied_utilities": supplied,
        "respondents_used": len(rows),
        "sample_label": LABEL,
    }
    outputs = {
        "choice_share_pct": pct,
        "choice_share_pct_by_segment": by_segment,
        "statement": CONJOINT_STATEMENT,
    }
    return _finalize(
        CONJOINT_METHOD,
        consumers,
        inputs,
        outputs,
        _dedupe(candidates),
        ("A-026", "A-027", "A-028", "A-029", "A-030", "A-031", "A-036", "A-037"),
        [
            CONJOINT_STATEMENT,
            "Choice shares are simulated preference among the listed alternatives, not market share.",
        ],
    )


def default_conjoint_alternatives(brand: str = "Aurora", pack: str = "pet_500ml") -> list[dict]:
    """Configurations to compare, built from the registry price grid (not agent-invented numbers)."""
    ref = reference_price(pack)
    grid = [float(m) for m in registry.get("A-034").value]
    rival = next(b for b in BRANDS if b != brand)
    mid = grid.index(1.0)
    lower, higher = grid[mid - 1], grid[mid + 1]
    return [{"brand": brand, "pack": pack, "price": round(ref * m, 2), "promotion": "None"}
            for m in (lower, 1.0, higher)] + [
        {"brand": brand, "pack": pack, "price": round(ref, 2), "promotion": "10% off"},
        {"brand": rival, "pack": pack, "price": round(ref, 2), "promotion": "None"}]


def conjoint_defaults() -> dict:
    """Levels and supplied part-worths, so the UI never hard-codes research numbers."""
    utilities = registry.get("A-037").value
    return {
        "label": LABEL,
        "statement": CONJOINT_STATEMENT,
        "utilities": utilities,
        "brands": list(utilities["brand"]),
        "packs": list(utilities["pack"]),
        "promotions": list(utilities["promotion"]),
        "reference_prices": {pack: reference_price(pack) for pack in FORMATS},
    }


def research_to_scenarios(
    research: ResearchResult,
    brand: str = "Aurora",
    promotion_depth_pct: float = 0,
    k: int = 200,
    seed: int = 42,
) -> list[dict]:
    """Map research candidates to engine requests; the engine and support envelope decide the rest."""
    envelope = _support_envelope()
    requests, chains = [], []
    for index, candidate in enumerate(research.candidates):
        item_brand = candidate.get("brand") or brand
        pack = candidate["pack"]
        sku = f"{item_brand}-{pack}"
        if item_brand not in BRANDS or sku not in SKU_IDS:
            raise ValueError(f"candidate {sku} is not an observed brand/pack")
        depth = float(candidate.get("promotion_depth_pct") or promotion_depth_pct)
        scenario = Scenario(
            name=f"{candidate['source_metric'].split(' simulated')[0]} ₹{candidate['price']:.2f} {pack}"[
                :80
            ],
            levers={
                sku: Lever(
                    price_index=float(candidate["price"]) / reference_price(pack),
                    promo_depth_pct=depth,
                    mechanic="none" if depth == 0 else "TPR",
                    promo_weeks_per_month=0 if depth == 0 else 1,
                )
            },
        )
        requests.append(scenario)
        chains.append(
            {
                "label": LABEL,
                "research_id": research.research_id,
                "methodology": research.methodology,
                "sample_size": research.sample_size,
                "source_data_hash": research.source_data_hash,
                "research_result_hash": research.result_hash,
                "candidate_index": index,
                "candidate": candidate,
                "scenario_id": None,
                "model_version": ENGINE_VERSION,
                "research_assumption_ids": research.assumption_ids,
                "engine_assumption_ids": sorted(set(ASSUMPTIONS) - set(RESEARCH_ASSUMPTION_IDS)),
                "result_hash": None,
            }
        )
    results = evaluate_batch(requests, build_param_draws(k=k, seed=seed)) if requests else []
    output = []
    for scenario, result, chain in zip(requests, results, chains, strict=True):
        chain["scenario_id"], chain["result_hash"] = result.scenario_id, result.result_hash
        row = {**asdict(result), "scenario": scenario.model_dump(mode="json"), "provenance": chain}
        if result.status == "REFUSED":
            row["nearest_supported_scenario"] = nearest_supported(
                scenario, envelope
            ).scenario.model_dump(mode="json")
        output.append(row)
    return output
