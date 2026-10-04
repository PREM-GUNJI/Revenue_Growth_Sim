"""Vectorised batch evaluation (PLAN.md section 6). Volume/GSV/NSV/GP are
computed for every (draw, scenario, SKU) cell in a handful of numpy ops —
no python loop over scenarios for that part. Only two things loop over S:
assembling the per-SKU margin bridge (central draw only, PLAN.md section 7)
and looking up the format-dependent unit COGS, both O(S x 12), not O(S x K).

Note on units: the project's "volume" has meant units sold (not litres)
since Phase 1's generator; this module keeps that convention rather than
switching to litres, which PLAN.md's pre-implementation sketch assumed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from backend.assumptions import registry
from backend.assumptions.assumptions import FORMATS, N_SKUS, SKU_IDS, SKUS
from backend.data.generator import generate
from backend.engine.ids import expand_scenario, result_hash, scenario_id
from backend.engine.margin import Bridge, build_bridge, cogs_per_unit, retailer_risk
from backend.engine.scenario import CostShock, Scenario
from backend.model.backtest import spec_hash
from backend.model.baselines import Baselines, compute_baselines, national_weekly_series
from backend.model.spec import (
    ParamDraws,
    average_monthly_promo_log_effect,
    build_param_draws,
    cross_price_log_effect,
)

ENGINE_VERSION = "1.0.0"
SKU_FORMAT = {s["sku_id"]: s["format"] for s in SKUS}


@lru_cache(maxsize=1)
def _baseline() -> Baselines:
    df = generate(42)
    weekly = national_weekly_series(df)
    reference_draws = build_param_draws(k=0, seed=1000)  # only the central row is used
    return compute_baselines(weekly, df, reference_draws)


@lru_cache(maxsize=1)
def _data_hash() -> str:
    manifest = json.loads(Path("data/data_manifest.json").read_text())
    return manifest["data_sha256"]


def _model_hash(draws: ParamDraws) -> str:
    h = hashlib.sha256()
    for arr in (draws.elasticity, draws.promo_k, draws.promo_b, draws.pull_forward_share):
        h.update(np.ascontiguousarray(arr).round(10).tobytes())
    for name in sorted(draws.mech_mult):
        h.update(np.ascontiguousarray(draws.mech_mult[name]).round(10).tobytes())
    return h.hexdigest()


@dataclass
class Band:
    value: float  # central draw
    p10: float
    p50: float
    p90: float


def _band(draw_values: np.ndarray) -> Band:
    central = float(draw_values[0])
    tail = draw_values[1:]
    if tail.size == 0:
        return Band(value=central, p10=central, p50=central, p90=central)
    return Band(
        value=central,
        p10=float(np.percentile(tail, 10)),
        p50=float(np.percentile(tail, 50)),
        p90=float(np.percentile(tail, 90)),
    )


@dataclass
class ScenarioResult:
    scenario_id: str
    status: str  # Phase 5 adds REFUSED/EDGE; this module only ever returns SUPPORTED
    volume: dict[str, Band]
    gsv: dict[str, Band]
    nsv: dict[str, Band]
    gp: dict[str, Band]
    portfolio_gp: Band
    bridge: dict[str, Bridge]
    retailer_risk_skus: list[str]
    result_hash: str


def evaluate_batch(scenarios: list[Scenario], draws: ParamDraws) -> list[ScenarioResult]:
    baselines = _baseline()
    expanded = [expand_scenario(s) for s in scenarios]
    s_count = len(scenarios)

    ln_price = np.zeros((s_count, N_SKUS))
    depth = np.zeros((s_count, N_SKUS))
    mech = np.empty((s_count, N_SKUS), dtype=object)
    weeks = np.zeros((s_count, N_SKUS))
    price_bp = np.zeros((s_count, N_SKUS))
    for si, e in enumerate(expanded):
        for ji, sku in enumerate(SKU_IDS):
            lv = e.levers[sku]
            price_bp[si, ji] = lv.price_bp
            ln_price[si, ji] = np.log(lv.price_bp / 1000.0)
            depth[si, ji] = lv.depth_pct
            mech[si, ji] = lv.mechanic
            weeks[si, ji] = lv.weeks_per_month

    diag_e = np.diagonal(draws.elasticity, axis1=1, axis2=2)  # (K+1, N_SKUS)
    own_effect = diag_e[:, None, :] * ln_price[None, :, :]  # (K+1, S, N_SKUS)
    cross_effect = cross_price_log_effect(ln_price, draws.elasticity)  # (K+1, S, N_SKUS), own+cross
    promo_effect = average_monthly_promo_log_effect(depth, mech, weeks, draws)  # (K+1, S, N_SKUS)

    base_vec = np.array([baselines.baseline_volume[s] for s in SKU_IDS])  # (N_SKUS,)
    ln_base = np.log(base_vec)

    # Bridge stages, in log space: baseline -> +own price -> +cross-pack -> +promo (final).
    vol1 = np.exp(ln_base[None, None, :] + own_effect)
    vol2 = np.exp(ln_base[None, None, :] + cross_effect)
    vol3 = np.exp(ln_base[None, None, :] + cross_effect + promo_effect)  # final volume

    ref_price_vec = np.array([baselines.reference_price[s] for s in SKU_IDS])  # (N_SKUS,)
    price_base = np.broadcast_to(ref_price_vec, (s_count, N_SKUS))
    price_final = ref_price_vec[None, :] * (price_bp / 1000.0)

    gsv_all = price_final[None, :, :] * vol3  # (K+1, S, N_SKUS)
    fixed_trade_pct = registry.get("A-016").value
    promo_share = (weeks / 4.0) * (depth / 100.0)  # (S, N_SKUS)
    trade_all = fixed_trade_pct * gsv_all + promo_share[None, :, :] * gsv_all

    cogs_unit_base_by_format = {fmt: cogs_per_unit(fmt, CostShock()) for fmt in FORMATS}
    cogs_unit = np.zeros((s_count, N_SKUS))
    for si, scenario in enumerate(scenarios):
        for ji, sku in enumerate(SKU_IDS):
            cogs_unit[si, ji] = cogs_per_unit(SKU_FORMAT[sku], scenario.cost_shock)
    cogs_all = cogs_unit[None, :, :] * vol3

    nsv_all = gsv_all - trade_all
    gp_all = nsv_all - cogs_all
    portfolio_gp_all = gp_all.sum(axis=2)  # (K+1, S)

    mh = _model_hash(draws)
    dh = _data_hash()
    rvh = spec_hash()

    results = []
    for si, e in enumerate(expanded):
        sid = scenario_id(e)
        volume_bands, gsv_bands, nsv_bands, gp_bands, bridge = {}, {}, {}, {}, {}
        flagged = []
        outputs_quantized: dict[str, dict] = {}

        for ji, sku in enumerate(SKU_IDS):
            volume_bands[sku] = _band(vol3[:, si, ji])
            gsv_bands[sku] = _band(gsv_all[:, si, ji])
            nsv_bands[sku] = _band(nsv_all[:, si, ji])
            gp_bands[sku] = _band(gp_all[:, si, ji])

            lv = e.levers[sku]
            fmt = SKU_FORMAT[sku]
            price_base_i = float(price_base[si, ji])
            price_final_i = float(price_final[si, ji])
            trade_base_i = fixed_trade_pct * price_base_i * float(base_vec[ji])
            cogs_base_i = cogs_unit_base_by_format[fmt] * float(base_vec[ji])

            bridge[sku] = build_bridge(
                price_base=price_base_i,
                price_final=price_final_i,
                vol0=float(base_vec[ji]),
                vol1=float(vol1[0, si, ji]),
                vol2=float(vol2[0, si, ji]),
                vol3=float(vol3[0, si, ji]),
                trade_base=trade_base_i,
                trade_final=float(trade_all[0, si, ji]),
                cogs_base=cogs_base_i,
                cogs_final=float(cogs_all[0, si, ji]),
            )
            if retailer_risk(lv.price_bp / 1000.0):
                flagged.append(sku)

            outputs_quantized[sku] = {
                "volume_centiunits": round(float(vol3[0, si, ji]) * 100),
                "gsv_cents": round(float(gsv_all[0, si, ji]) * 100),
                "nsv_cents": round(float(nsv_all[0, si, ji]) * 100),
                "gp_cents": round(float(gp_all[0, si, ji]) * 100),
            }

        rh = result_hash(
            scenario_id_=sid,
            engine_version=ENGINE_VERSION,
            model_hash=mh,
            data_hash=dh,
            registry_values_hash=rvh,
            k=draws.k,
            seed=draws.seed,
            status="SUPPORTED",
            reasons=[],
            outputs_quantized=outputs_quantized,
        )

        results.append(
            ScenarioResult(
                scenario_id=sid,
                status="SUPPORTED",
                volume=volume_bands,
                gsv=gsv_bands,
                nsv=nsv_bands,
                gp=gp_bands,
                portfolio_gp=_band(portfolio_gp_all[:, si]),
                bridge=bridge,
                retailer_risk_skus=flagged,
                result_hash=rh,
            )
        )

    return results


def evaluate_one(scenario: Scenario, draws: ParamDraws) -> ScenarioResult:
    return evaluate_batch([scenario], draws)[0]
