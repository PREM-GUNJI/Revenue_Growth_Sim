"""Sensitivity and goal-seeking over the deterministic batch engine. No fitting: both only
re-evaluate scenarios, so every number still comes from `evaluate_batch`."""

from __future__ import annotations

from dataclasses import asdict

from backend.agent.tools import ToolError, _override
from backend.assumptions.assumptions import ASSUMPTIONS, FOCAL_BRAND, SKU_IDS, SKUS
from backend.engine.batch import evaluate_batch
from backend.engine.scenario import Lever, Scenario
from backend.model.spec import build_param_draws

SENSITIVITY_IDS = ["A-001", "A-002", "A-003", "A-004", "A-005", "A-006",
                   "A-007", "A-008", "A-009", "A-010", "A-011", "A-012"]
PRICE_GRID = [0.94, 0.96, 0.98, 1.02, 1.04, 1.06]
PROMO_OPTIONS = [("none", 0.0, 0.0), ("TPR", 10.0, 2.0)]


def _gp(result: dict) -> float | None:
    # The focal brand's gross profit: competitor brands' profit is not the user's profit.
    return None if result["status"] == "REFUSED" or not result["focal"] else result["focal"]["gp"]["value"]


def _volume(result: dict) -> float:
    return result["focal"]["volume"]["value"]


def _leader(results: list[dict]) -> int | None:
    scored = [(g, -i) for i, r in enumerate(results) if (g := _gp(r)) is not None]
    return None if not scored else -max(scored)[1]


def _evaluate(scenarios: list[Scenario], overrides: dict[str, float] | None = None, k: int = 0, seed: int = 42) -> list[dict]:
    draws = build_param_draws(k=k, seed=seed)
    for assumption_id, value in (overrides or {}).items():
        _override(draws, assumption_id, value)
    return [asdict(r) for r in evaluate_batch(scenarios, draws)]


def sensitivity(scenarios: list[Scenario], seed: int = 42) -> dict:
    """Re-rank the scenarios with each assumption at the low and high end of its documented range."""
    base = _evaluate(scenarios, seed=seed)
    leader = _leader(base)
    rows = []
    for assumption_id in SENSITIVITY_IDS:
        assumption = ASSUMPTIONS.get(assumption_id)
        if assumption is None or assumption.valid_range is None:
            continue
        cases = {}
        for end, value in zip(("low", "high"), assumption.valid_range, strict=True):
            results = _evaluate(scenarios, {assumption_id: value}, seed=seed)
            winner = _leader(results)
            cases[end] = {"value": value, "winner": winner,
                          "winner_gp": None if winner is None else _gp(results[winner]),
                          "ranking": sorted((i for i, r in enumerate(results) if _gp(r) is not None),
                                            key=lambda i: -_gp(results[i]))}
        gps = [c["winner_gp"] for c in cases.values() if c["winner_gp"] is not None]
        base_gp = None if leader is None else _gp(base[leader])
        rows.append({"assumption_id": assumption_id, "label": assumption.label, "base_value": assumption.value,
                     "low": cases["low"], "high": cases["high"],
                     "flips_winner": any(c["winner"] != leader for c in cases.values()),
                     "swing": None if not gps or base_gp is None else max(abs(g - base_gp) for g in gps)})
    rows.sort(key=lambda r: (-(r["swing"] or 0), r["assumption_id"]))
    return {"base_winner": leader, "base_ranking": sorted((i for i, r in enumerate(base) if _gp(r) is not None),
                                                          key=lambda i: -_gp(base[i])),
            "base_gp": [_gp(r) for r in base], "assumptions": rows}


def goal_seek(max_volume_loss_pct: float = 5.0, sku_ids: list[str] | None = None, top: int = 5, seed: int = 42) -> dict:
    """Max focal-brand gross profit subject to a unit-loss cap, over single-SKU and brand-wide price/promo moves."""
    if not 0 <= max_volume_loss_pct <= 100:
        raise ToolError("max_volume_loss_pct must be between 0 and 100")
    skus = sku_ids or [item["sku_id"] for item in SKUS if item["brand"] == FOCAL_BRAND]
    unknown = set(skus) - set(SKU_IDS)
    if unknown:
        raise ToolError("unknown sku ids: " + ", ".join(sorted(unknown)))
    candidates = [Scenario(name="Baseline")]
    for price in PRICE_GRID:
        for mechanic, depth, weeks in PROMO_OPTIONS:
            lever = Lever(price_index=price, promo_depth_pct=depth, mechanic=mechanic, promo_weeks_per_month=weeks)
            for sku in skus:
                candidates.append(Scenario(name=f"{sku} price {price:g} {mechanic}", levers={sku: lever}))
            candidates.append(Scenario(name=f"All {FOCAL_BRAND} packs price {price:g} {mechanic}", levers={s: lever for s in skus}))
    results = _evaluate(candidates, seed=seed)
    base_volume, base_gp = _volume(results[0]), _gp(results[0])
    kept = []
    for scenario, result in zip(candidates[1:], results[1:], strict=True):
        gp = _gp(result)
        if gp is None:
            continue
        loss = (base_volume - _volume(result)) / base_volume * 100
        if loss <= max_volume_loss_pct and gp > base_gp:
            kept.append({"scenario": scenario.model_dump(mode="json"), "scenario_id": result["scenario_id"],
                         "focal_gp": gp, "gp_change": gp - base_gp, "volume_loss_pct": loss})
    kept.sort(key=lambda r: (-r["focal_gp"], r["scenario_id"]))
    return {"objective": "focal_gp", "max_volume_loss_pct": max_volume_loss_pct, "baseline_gp": base_gp,
            "evaluated": len(candidates) - 1, "feasible": len(kept), "top": kept[:top]}
