"""The starting position a decision is made from: baseline P&L, observed history and engine probes.

Every figure is either read from the synthetic history (Observed), produced by the deterministic engine
(Modeled), or a registry assumption (Assumed); `labels` says which. Nothing is fitted and nothing here is
computed outside the engine: the baseline is the engine's zero-change scenario and each probe is an
ordinary engine scenario compared with it.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import APIRouter

from backend.assumptions.assumptions import (
    ASSUMPTIONS,
    BRANDS,
    CURRENCY_CODE,
    FOCAL_BRAND,
    N_WEEKS,
    OWN_ELASTICITY_BY_FORMAT,
    REGIONS,
    SKUS,
    STORES_PER_REGION,
)
from backend.data.generator import GENERATOR_VERSION
from backend.engine.batch import _baseline, _data_hash, _raw_data, evaluate_batch
from backend.engine.scenario import CostShock, Lever, Scenario
from backend.model.baselines import BACKTEST_WINDOW_WEEKS
from backend.model.spec import build_param_draws

router = APIRouter(tags=["situation"])

K, SEED = 200, 42
PRICE_PROBE = 1.03  # a 3% list-price rise on one pack
PROMO_PROBE = {"promo_depth_pct": 10.0, "mechanic": "TPR", "promo_weeks_per_month": 2.0}
COST_SHOCK_PCT = 8.0  # same stress the agent adds to every comparison

LABELS = {
    "prices_and_promo_history": "Observed",
    "baseline_volume": "Modeled",
    "profit_and_loss": "Modeled",
    "probes": "Modeled",
    "elasticities": "Assumed",
}


def _pct(new: float, old: float) -> float | None:
    return (new / old - 1.0) * 100.0 if old else None


def _history() -> dict[str, dict[str, Any]]:
    """Per-SKU promo history, read straight from the generated rows."""
    df = _raw_data()
    out: dict[str, dict[str, Any]] = {}
    for sku, rows in df.groupby("sku_id", observed=True):
        on_promo = rows[rows["promo_depth_pct"] > 0]
        out[str(sku)] = {
            "promo_week_share_pct": float(len(on_promo) / len(rows) * 100.0),
            "avg_promo_depth_pct": float(on_promo["promo_depth_pct"].mean()) if len(on_promo) else 0.0,
            "main_mechanic": str(on_promo["promo_mechanic"].mode().iat[0]) if len(on_promo) else "none",
        }
    return out


def _totals(rows: list[dict[str, Any]]) -> dict[str, float]:
    units = sum(r["baseline_units"] for r in rows)
    litres = sum(r["baseline_units"] * r["pack_size_l"] for r in rows)
    gsv, nsv, cogs, gp = (sum(r[k] for r in rows) for k in ("baseline_gsv", "baseline_nsv", "baseline_cogs", "baseline_gp"))
    return {"units": units, "litres": litres, "gsv": gsv, "trade": gsv - nsv, "nsv": nsv, "cogs": cogs, "gp": gp,
            "gp_margin_pct": gp / nsv * 100.0 if nsv else 0.0}


def _probe(base: Any, scenario_result: Any, sku_ids: list[str]) -> dict[str, Any]:
    """How one engine scenario compares with the baseline, for the focal brand and for the one pack."""
    if scenario_result.status == "REFUSED":
        return {"status": "REFUSED", "reasons": [r["message"] for r in scenario_result.refusal_reasons]}
    f, b = scenario_result.focal, base.focal
    return {
        "status": scenario_result.status,
        "scenario_id": scenario_result.scenario_id,
        "focal_volume_pct": _pct(f["volume"].value, b["volume"].value),
        "focal_gsv_pct": _pct(f["gsv"].value, b["gsv"].value),
        "focal_gp_change": f["gp"].value - b["gp"].value,
        "focal_gp_pct": _pct(f["gp"].value, b["gp"].value),
        "focal_gp_change_p10": f["gp"].p10 - b["gp"].value,
        "focal_gp_change_p90": f["gp"].p90 - b["gp"].value,
        "pack_volume_pct": _pct(scenario_result.volume[sku_ids[0]].value, base.volume[sku_ids[0]].value),
    }


@lru_cache(maxsize=1)
def build_situation() -> dict[str, Any]:
    """Baseline P&L per SKU and brand, observed history, and engine probes. Deterministic and cached."""
    baselines = _baseline()
    draws = build_param_draws(k=K, seed=SEED)
    focal_skus = [s for s in SKUS if s["brand"] == FOCAL_BRAND]

    scenarios = [Scenario(name="Baseline")]
    for s in focal_skus:
        scenarios.append(Scenario(name=f"+3% price, {s['sku_id']}", levers={s["sku_id"]: Lever(price_index=PRICE_PROBE)}))
    for s in focal_skus:
        scenarios.append(Scenario(name=f"10% TPR promo, {s['sku_id']}", levers={s["sku_id"]: Lever(**PROMO_PROBE)}))
    scenarios.append(Scenario(name="Input costs +8%", cost_shock=CostShock(
        aluminium_pct=COST_SHOCK_PCT, pet_resin_pct=COST_SHOCK_PCT, sugar_pct=COST_SHOCK_PCT)))
    results = evaluate_batch(scenarios, draws)
    base = results[0]
    n = len(focal_skus)
    price_results, promo_results, cost_result = results[1:1 + n], results[1 + n:1 + 2 * n], results[-1]

    history = _history()
    price_by_brand_format = {(s["brand"], s["format"]): baselines.reference_price[s["sku_id"]] for s in SKUS}
    rows: list[dict[str, Any]] = []
    for s in SKUS:
        sku = s["sku_id"]
        units, gsv, nsv, gp = (getattr(base, m)[sku].value for m in ("volume", "gsv", "nsv", "gp"))
        price = baselines.reference_price[sku]
        lo, hi = baselines.price_index_p1_p99[sku]
        is_focal = s["brand"] == FOCAL_BRAND
        row: dict[str, Any] = {
            "sku_id": sku, "brand": s["brand"], "format": s["format"], "pack_size_l": s["pack_size_l"],
            "is_focal": is_focal,
            "price": price, "price_per_litre": price / s["pack_size_l"],
            "price_range": [price * lo, price * hi],
            "baseline_units": units, "baseline_gsv": gsv, "baseline_trade": gsv - nsv, "baseline_nsv": nsv,
            "baseline_cogs": nsv - gp, "baseline_gp": gp, "gp_margin_pct": gp / nsv * 100.0 if nsv else 0.0,
            "history": history[sku],
            "own_elasticity": OWN_ELASTICITY_BY_FORMAT[s["format"]].value,
            "own_elasticity_id": OWN_ELASTICITY_BY_FORMAT[s["format"]].id,
            "price_gap_vs_competitors_pct": (
                {b: _pct(price, price_by_brand_format[(b, s["format"])]) for b in BRANDS if b != FOCAL_BRAND}
                if is_focal else None),
        }
        if is_focal:
            i = [x["sku_id"] for x in focal_skus].index(sku)
            row["price_probe"] = _probe(base, price_results[i], [sku])
            row["promo_probe"] = _probe(base, promo_results[i], [sku])
        rows.append(row)

    focal_rows = [r for r in rows if r["is_focal"]]
    by_brand = {b: _totals([r for r in rows if r["brand"] == b]) for b in BRANDS}
    market = _totals(rows)
    return {
        "currency": CURRENCY_CODE,
        "focal_brand": FOCAL_BRAND,
        "competitors": [b for b in BRANDS if b != FOCAL_BRAND],
        "period": {
            "basis": f"One typical week: the last {BACKTEST_WINDOW_WEEKS} of {N_WEEKS} weeks of history, with the "
                     "registry's price and promotion effects backed out, summed over all regions.",
            "history_weeks": N_WEEKS, "regions": REGIONS, "stores_per_region": STORES_PER_REGION,
            "rows": int(len(_raw_data())), "generator_version": GENERATOR_VERSION,
        },
        "data_hash": _data_hash(),
        "skus": rows,
        "totals": {"focal": _totals(focal_rows), "by_brand": by_brand, "market": market,
                   "focal_value_share_pct": by_brand[FOCAL_BRAND]["gsv"] / market["gsv"] * 100.0},
        "cost_shock_probe": {
            "shock_pct": COST_SHOCK_PCT,
            "applies_to": "aluminium, PET resin and sugar costs together",
            **_probe(base, cost_result, [focal_skus[0]["sku_id"]]),
        },
        "probe_definitions": {
            "price": f"+{round((PRICE_PROBE - 1) * 100)}% list price on one pack, everything else unchanged",
            "promo": f"{PROMO_PROBE['promo_depth_pct']:.0f}% {PROMO_PROBE['mechanic']} promotion "
                     f"{PROMO_PROBE['promo_weeks_per_month']:.0f} weeks a month on one pack",
        },
        "assumption_ids": ["A-013", "A-014a", "A-014b", "A-014c", "A-014d", "A-015", "A-016",
                           *[a.id for a in OWN_ELASTICITY_BY_FORMAT.values()], "A-005", "A-006", "A-007", "A-008", "A-012"],
        "model": {"k": K, "seed": SEED, "assumption_count": len(ASSUMPTIONS)},
        "labels": LABELS,
    }


def compact_for_agent() -> dict[str, Any]:
    """The part of the situation a planner needs to choose scenarios: focal packs only, no competitor detail."""
    s = build_situation()
    packs = []
    for r in (r for r in s["skus"] if r["is_focal"]):
        packs.append({
            "sku_id": r["sku_id"], "price": round(r["price"], 2), "baseline_units_per_week": round(r["baseline_units"]),
            "gp_margin_pct": round(r["gp_margin_pct"], 1), "own_elasticity": r["own_elasticity"],
            "weeks_on_promo_pct": round(r["history"]["promo_week_share_pct"], 1),
            "price_gap_vs_competitors_pct": {k: round(v, 1) for k, v in r["price_gap_vs_competitors_pct"].items()},
            "plus_3pct_price_gp_change": round(r["price_probe"].get("focal_gp_change", 0.0)),
            "ten_pct_promo_gp_change": round(r["promo_probe"].get("focal_gp_change", 0.0)),
        })
    cost = s["cost_shock_probe"]
    return {
        "currency": s["currency"], "focal_brand": s["focal_brand"], "period": "one typical week",
        "focal_totals": {k: round(v, 1) for k, v in s["totals"]["focal"].items()},
        "packs": packs,
        "input_costs_plus_8pct_gp_change": round(cost.get("focal_gp_change", 0.0)),
        "note": "Modeled by the deterministic engine; gp changes are per week for the focal brand against the baseline.",
    }


@router.get("/situation")
async def situation() -> dict[str, Any]:
    return build_situation()
