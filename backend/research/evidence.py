"""Reproducible synthetic consumer evidence and non-estimating research methods."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from backend.assumptions.assumptions import BRANDS, FORMATS, REGIONS
from backend.assumptions import registry
from backend.engine.batch import ENGINE_VERSION, _support_envelope, evaluate_batch
from backend.engine.scenario import Lever, Scenario
from backend.engine.support import nearest_supported
from backend.model.spec import build_param_draws


def _hash(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def generate_consumers(seed: int = 42, sample_size: int = 250) -> dict:
    """Create synthetic, non-PII respondents and comments from fixed distributions."""
    if sample_size < 1 or sample_size > 10000:
        raise ValueError("sample_size must be between 1 and 10000")
    rng = np.random.default_rng(seed)
    segments = ("value_seeker", "family_planner", "brand_loyal", "deal_responsive")
    rows = []
    for i in range(sample_size):
        segment = segments[i % len(segments)]
        price_sens = float(np.clip(rng.normal({"value_seeker": .82, "family_planner": .45, "brand_loyal": .24, "deal_responsive": .68}[segment], .08), 0, 1))
        promo_sens = float(np.clip(rng.normal({"value_seeker": .45, "family_planner": .3, "brand_loyal": .2, "deal_responsive": .85}[segment], .07), 0, 1))
        pack = str(rng.choice(FORMATS, p=[.32, .30, .22, .16]))
        current_price = {"can_330ml": 40, "pet_500ml": 45, "bottle_1500ml": 75, "multipack_6x330ml": 120}[pack]
        wtp = round(current_price * (1 + (0.12 - price_sens * .16) + rng.normal(0, .035)), 2)
        if segment == "deal_responsive" or promo_sens > .72:
            comment = f"I normally buy this only when it is on promotion; around ₹{round(wtp)} feels fair."
        elif pack in ("bottle_1500ml", "multipack_6x330ml"):
            comment = "I prefer the bigger pack because it gives better value for my family."
        elif price_sens < .35:
            comment = "A small price increase would not change my purchase."
        else:
            comment = f"I usually wait for offers. At ₹{round(wtp)} I would probably switch."
        rows.append({
            "respondent_id": f"SYN-{i + 1:05d}", "segment": segment,
            "age_band": str(rng.choice(["18-24", "25-34", "35-44", "45-54", "55+"], p=[.15,.28,.25,.18,.14])),
            "region": str(rng.choice(REGIONS)), "current_brand": str(rng.choice(BRANDS)),
            "current_pack": pack, "current_price": current_price,
            "purchase_frequency": str(rng.choice(["weekly", "2-3x_month", "monthly"], p=[.45,.4,.15])),
            "price_sensitivity": round(price_sens, 4), "promotion_sensitivity": round(promo_sens, 4),
            "pack_preference": pack, "willingness_to_pay": wtp, "comment": comment,
        })
    return {"label": "SYNTHETIC CONSUMER EVIDENCE", "seed": seed,
            "sample_size": sample_size, "respondents": rows, "data_hash": _hash(rows)}


@dataclass(frozen=True)
class ResearchResult:
    methodology: str
    research_id: str
    sample_size: int
    inputs: dict
    outputs: dict
    candidates: list[dict]
    assumptions: list[str]
    limitations: list[str]
    source_data_hash: str
    result_hash: str


def run_research(methodology: str, evidence: dict, prices: list[float] | None = None) -> ResearchResult:
    """Apply transparent descriptive rules to respondent values; no engine numbers."""
    respondents = evidence["respondents"]
    registry.get("A-026")
    wtp = np.asarray([float(row["willingness_to_pay"]) for row in respondents])
    candidates: list[dict] = []
    if methodology == "Willingness to Pay":
        outputs = {"p25": float(np.quantile(wtp, .25)), "p50": float(np.quantile(wtp, .5)), "p75": float(np.quantile(wtp, .75))}
        values = [outputs["p25"], outputs["p50"], outputs["p75"]]
    elif methodology == "Gabor-Granger":
        grid = sorted(set(float(x) for x in (prices or [35, 40, 42, 45, 50, 60, 75, 90, 120, 150])))
        accept = {str(p): float(np.mean(wtp >= p)) for p in grid}
        outputs = {"acceptance_share_by_price": accept}
        values = [p for p in grid if accept[str(p)] >= .5]
    elif methodology == "Van Westendorp Price Sensitivity Meter":
        outputs = {"too_cheap": float(np.quantile(wtp, .05)), "bargain": float(np.quantile(wtp, .25)),
                   "expensive": float(np.quantile(wtp, .75)), "too_expensive": float(np.quantile(wtp, .95))}
        values = [outputs["bargain"], outputs["expensive"]]
    else:
        raise ValueError("unsupported research methodology")
    for value in sorted(set(values)):
        candidates.append({"price": round(float(value), 2), "pack": "pet_500ml", "promotion_depth_pct": 0,
                           "source_metric": "WTP percentile/acceptance threshold"})
    inputs = {"methodology": methodology, "prices": prices or [], "sample_label": evidence.get("label")}
    assumptions = ["research is descriptive and illustrative", "respondent answers are synthetic"]
    limitations = ["Synthetic sample is not representative of real consumers.",
                   "Research results generate candidates only; commercial outcomes come from the RGM engine."]
    payload = {"methodology": methodology, "inputs": inputs, "outputs": outputs, "candidates": candidates,
               "sample_size": len(respondents), "source_data_hash": evidence["data_hash"]}
    rhash = _hash(payload)
    return ResearchResult(methodology, "RES-" + rhash[:12].upper(), len(respondents), inputs, outputs,
                          candidates, assumptions, limitations, evidence["data_hash"], rhash)


def conjoint_simulation(consumers: dict, alternatives: list[dict], utilities: dict) -> dict:
    """Deterministic MNL choices using caller-supplied synthetic part-worths only."""
    registry.get("A-027")
    if not alternatives:
        raise ValueError("at least one alternative is required")
    shares = np.zeros(len(alternatives), dtype=float)
    for respondent in consumers["respondents"]:
        utility = []
        for alt in alternatives:
            key = f"{alt.get('brand')}|{alt.get('pack')}|{alt.get('price')}|{alt.get('promotion', 'None')}"
            if key not in utilities:
                raise ValueError(f"supplied utility missing for {key}")
            utility.append(float(utilities[key]))
        weights = np.exp(np.asarray(utility) - max(utility))
        shares += weights / weights.sum()
    shares /= len(consumers["respondents"])
    return {"label": "SYNTHETIC CONSUMER EVIDENCE", "methodology": "Conjoint simulation (supplied utilities)",
            "sample_size": len(consumers["respondents"]), "alternatives": alternatives,
            "choice_share": [float(x) for x in shares], "choice_share_pct": [float(x * 100) for x in shares],
            "supplied_utilities": utilities, "source_data_hash": consumers["data_hash"],
            "statement": "This simulation uses supplied synthetic utilities. It does not estimate or fit consumer utilities.",
            "result_hash": _hash({"shares": shares.tolist(), "alternatives": alternatives,
                                  "utilities": utilities, "source": consumers["data_hash"]})}


def research_to_scenarios(research: ResearchResult, brand: str = "Aurora",
                          promotion_depth_pct: float = 0, k: int = 200, seed: int = 42) -> list[dict]:
    """Map research candidates into real engine requests and preserve provenance."""
    from backend.assumptions.assumptions import SKU_IDS

    if brand not in BRANDS:
        raise ValueError("brand must be an observed brand")
    envelope = _support_envelope()
    format_prices = {"can_330ml": 40.0, "pet_500ml": 45.0,
                     "bottle_1500ml": 75.0, "multipack_6x330ml": 120.0}
    requests, provenance = [], []
    for index, candidate in enumerate(research.candidates):
        pack = candidate["pack"]
        sku = f"{brand}-{pack}"
        if sku not in SKU_IDS:
            continue
        price_index = float(candidate["price"]) / format_prices[pack]
        depth = float(promotion_depth_pct)
        scenario = Scenario(name=f"Research candidate {index + 1}", levers={sku: Lever(
            price_index=price_index, promo_depth_pct=depth,
            mechanic="none" if depth == 0 else "TPR",
            promo_weeks_per_month=0 if depth == 0 else 1,
        )})
        requests.append(scenario)
        provenance.append({"research_id": research.research_id, "methodology": research.methodology,
                           "source_data_hash": research.source_data_hash,
                           "research_result_hash": research.result_hash,
                           "candidate": candidate, "scenario_id": None,
                           "model_version": ENGINE_VERSION, "assumptions": research.assumptions})
    results = evaluate_batch(requests, build_param_draws(k=k, seed=seed)) if requests else []
    output = []
    for scenario, result, chain in zip(requests, results, provenance, strict=True):
        chain["scenario_id"] = result.scenario_id
        chain["result_hash"] = result.result_hash
        row = {**asdict(result), "scenario": scenario.model_dump(mode="json"), "provenance": chain}
        if result.status == "REFUSED":
            suggestion = nearest_supported(scenario, envelope)
            row["nearest_supported_scenario"] = suggestion.scenario.model_dump(mode="json")
        output.append(row)
    return output
