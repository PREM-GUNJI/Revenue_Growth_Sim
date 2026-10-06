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

import copy
import hashlib
import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import numpy as np

from backend.assumptions import registry
from backend.assumptions.assumptions import FORMATS, N_SKUS, SKU_IDS, SKUS
from backend.data.generator import generate
from backend.engine.ids import ExpandedScenario, expand_scenario, result_hash, scenario_id
from backend.engine.margin import Bridge, _cents_array, cogs_per_unit
from backend.engine.scenario import CostShock, Scenario
from backend.engine.support import SupportEnvelope, nearest_supported
from backend.model.backtest import spec_hash
from backend.model.baselines import Baselines, compute_baselines, national_weekly_series
from backend.model.envelope_build import build_joint_coverage
from backend.model.spec import (
    ParamDraws,
    average_monthly_promo_log_effect,
    build_param_draws,
    cross_price_log_effect,
)

ENGINE_VERSION = "1.1.0"
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


@lru_cache(maxsize=1)
def _support_envelope() -> SupportEnvelope:
    raw = generate(42)
    return SupportEnvelope(_baseline(), build_joint_coverage(raw))


def _model_hash(draws: ParamDraws) -> str:
    h = hashlib.sha256()
    for arr in (draws.elasticity, draws.promo_k, draws.promo_b, draws.pull_forward_share):
        h.update(np.ascontiguousarray(arr).round(10).tobytes())
    for name in sorted(draws.mech_mult):
        h.update(np.ascontiguousarray(draws.mech_mult[name]).round(10).tobytes())
    return h.hexdigest()


@dataclass(frozen=True)
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
    p10, p50, p90 = np.percentile(tail, (10, 50, 90))
    return Band(value=central, p10=float(p10), p50=float(p50), p90=float(p90))


def _band_at(values: np.ndarray, quantiles: np.ndarray, si: int, ji: int) -> Band:
    return Band(value=float(values[0, si, ji]), p10=float(quantiles[0, si, ji]),
                p50=float(quantiles[1, si, ji]), p90=float(quantiles[2, si, ji]))


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    status: str
    volume: dict[str, Band]
    gsv: dict[str, Band]
    nsv: dict[str, Band]
    gp: dict[str, Band]
    portfolio_gp: Band | None
    bridge: dict[str, Bridge]
    retailer_risk_skus: list[str]
    result_hash: str
    refusal_reasons: list[dict]
    nearest_supported_scenario: Scenario | None


def _evaluate_chunk(
    scenarios: list[Scenario], draws: ParamDraws, expanded: list[ExpandedScenario]
) -> list[ScenarioResult]:
    baselines = _baseline()
    envelope = _support_envelope()
    decisions = [envelope.check(scenario) for scenario in scenarios]
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
    if np.any(depth):
        promo_effect = average_monthly_promo_log_effect(depth, mech, weeks, draws)
    else:
        promo_effect = np.zeros_like(own_effect)

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
    cogs_base_units = np.array([cogs_unit_base_by_format[SKU_FORMAT[sku]] for sku in SKU_IDS])
    if all(not any(s.cost_shock.model_dump().values()) for s in scenarios):
        cogs_unit = np.broadcast_to(cogs_base_units, (s_count, N_SKUS))
    else:
        cogs_unit = np.zeros((s_count, N_SKUS))
        for si, scenario in enumerate(scenarios):
            for ji, sku in enumerate(SKU_IDS):
                cogs_unit[si, ji] = cogs_per_unit(SKU_FORMAT[sku], scenario.cost_shock)
    cogs_all = cogs_unit[None, :, :] * vol3

    trade_base_all = fixed_trade_pct * price_base * base_vec[None, :]
    cogs_base_all = cogs_base_units[None, :] * base_vec[None, :]
    bridge_dollars = np.stack(
        (
            (price_final - price_base) * base_vec[None, :],
            price_final * (vol1[0] - base_vec[None, :]),
            price_final * (vol2[0] - vol1[0]),
            price_final * (vol3[0] - vol2[0]),
            trade_base_all - trade_all[0],
            cogs_base_all - cogs_all[0],
        ),
        axis=0,
    )
    bridge_cents = _cents_array(bridge_dollars)
    gp_base_all = price_base * base_vec[None, :] - trade_base_all - cogs_base_all
    gp_final_all = price_final * vol3[0] - trade_all[0] - cogs_all[0]
    total_bridge_cents = _cents_array(gp_final_all) - _cents_array(gp_base_all)
    residual = total_bridge_cents - bridge_cents.sum(axis=0)
    target = np.argmax(np.abs(bridge_dollars), axis=0)
    for component in range(bridge_cents.shape[0]):
        mask = target == component
        bridge_cents[component][mask] += residual[mask]

    nsv_all = gsv_all - trade_all
    gp_all = nsv_all - cogs_all
    portfolio_gp_all = gp_all.sum(axis=2)  # (K+1, S)

    # Quantiles are computed in bulk per metric and chunk, avoiding hundreds
    # of thousands of tiny sorting calls at 10,000 scenarios.
    if draws.k:
        volume_q = np.percentile(vol3[1:], (10, 50, 90), axis=0)
        gsv_q = np.percentile(gsv_all[1:], (10, 50, 90), axis=0)
        nsv_q = np.percentile(nsv_all[1:], (10, 50, 90), axis=0)
        gp_q = np.percentile(gp_all[1:], (10, 50, 90), axis=0)
        portfolio_q = np.percentile(portfolio_gp_all[1:], (10, 50, 90), axis=0)
    else:
        volume_q = np.repeat(vol3[:1], 3, axis=0)
        gsv_q = np.repeat(gsv_all[:1], 3, axis=0)
        nsv_q = np.repeat(nsv_all[:1], 3, axis=0)
        gp_q = np.repeat(gp_all[:1], 3, axis=0)
        portfolio_q = np.repeat(portfolio_gp_all[:1], 3, axis=0)

    mh = _model_hash(draws)
    dh = _data_hash()
    rvh = spec_hash()

    scenario_ids: list[str] = []
    ids_by_key: dict[tuple, str] = {}
    for item in expanded:
        key = (
            item.schema_version,
            tuple((sku, lv.price_bp, lv.depth_pct, lv.mechanic, lv.weeks_per_month)
                  for sku, lv in item.levers.items()),
            tuple(sorted(item.cost_shock.items())),
        )
        sid = ids_by_key.get(key)
        if sid is None:
            sid = scenario_id(item)
            ids_by_key[key] = sid
        scenario_ids.append(sid)

    results = []
    hurdle = registry.get("A-017").value
    pass_through = registry.get("A-017b").value
    price_index = price_bp / 1000.0
    shelf_rel = 1.0 + (price_index - 1.0) * pass_through
    retailer_risk_mask = 1.0 - price_index * (1.0 - hurdle) / shelf_rel < hurdle
    for si, e in enumerate(expanded):
        sid = scenario_ids[si]
        decision = decisions[si]
        if decision.status == "REFUSED":
            reasons = [reason.message for reason in decision.reasons]
            rh = result_hash(
                scenario_id_=sid,
                engine_version=ENGINE_VERSION,
                model_hash=mh,
                data_hash=dh,
                registry_values_hash=rvh,
                k=draws.k,
                seed=draws.seed,
                status="REFUSED",
                reasons=reasons,
                outputs_quantized={},
            )
            suggested = nearest_supported(scenarios[si], envelope).scenario
            results.append(ScenarioResult(
                scenario_id=sid, status="REFUSED", volume={}, gsv={}, nsv={}, gp={},
                portfolio_gp=None, bridge={}, retailer_risk_skus=[], result_hash=rh,
                refusal_reasons=[vars(reason) for reason in decision.reasons],
                nearest_supported_scenario=suggested,
            ))
            continue
        volume_bands, gsv_bands, nsv_bands, gp_bands, bridge = {}, {}, {}, {}, {}
        flagged = []
        outputs_quantized: dict[str, dict] = {}

        for ji, sku in enumerate(SKU_IDS):
            volume_bands[sku] = _band_at(vol3, volume_q, si, ji)
            gsv_bands[sku] = _band_at(gsv_all, gsv_q, si, ji)
            nsv_bands[sku] = _band_at(nsv_all, nsv_q, si, ji)
            gp_bands[sku] = _band_at(gp_all, gp_q, si, ji)

            if decision.status == "EDGE":
                # Explicitly widen all reported intervals on sparse support.
                for bands in (volume_bands, gsv_bands, nsv_bands, gp_bands):
                    band = bands[sku]
                    radius = max(abs(band.value - band.p10), abs(band.p90 - band.value))
                    bands[sku] = Band(
                        value=band.value,
                        p10=max(0.0, band.p10 - radius * 0.5),
                        p50=band.p50,
                        p90=band.p90 + radius * 0.5,
                    )

            lv = e.levers[sku]
            bridge[sku] = Bridge(
                price_cents=int(bridge_cents[0, si, ji]),
                volume_cents=int(bridge_cents[1, si, ji]),
                cross_pack_cents=int(bridge_cents[2, si, ji]),
                promo_cents=int(bridge_cents[3, si, ji]),
                trade_cents=int(bridge_cents[4, si, ji]),
                cogs_cents=int(bridge_cents[5, si, ji]),
                total_cents=int(total_bridge_cents[si, ji]),
            )
            if retailer_risk_mask[si, ji]:
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
            status=decision.status,
            reasons=[],
            outputs_quantized=outputs_quantized,
        )

        results.append(
            ScenarioResult(
                scenario_id=sid,
                status=decision.status,
                volume=volume_bands,
                gsv=gsv_bands,
                nsv=nsv_bands,
                gp=gp_bands,
                portfolio_gp=Band(value=float(portfolio_gp_all[0, si]),
                                  p10=float(portfolio_q[0, si]),
                                  p50=float(portfolio_q[1, si]),
                                  p90=float(portfolio_q[2, si])),
                bridge=bridge,
                retailer_risk_skus=flagged,
                result_hash=rh,
                refusal_reasons=[],
                nearest_supported_scenario=None,
            )
        )

    return results


def evaluate_batch(scenarios: list[Scenario], draws: ParamDraws) -> list[ScenarioResult]:
    """Evaluate in bounded, fully vectorised scenario chunks to cap peak memory."""
    if not scenarios:
        return []
    chunk_size = int(registry.get("A-024").value)
    expanded_by_request: dict[tuple, ExpandedScenario] = {}
    unique_index_by_key: dict[tuple, int] = {}
    unique_scenarios: list[Scenario] = []
    unique_expanded: list[ExpandedScenario] = []
    request_to_unique: list[int] = []
    expanded = []
    for scenario in scenarios:
        key = (
            scenario.schema_version,
            tuple((sku, scenario.levers[sku].price_index,
                   scenario.levers[sku].promo_depth_pct, scenario.levers[sku].mechanic,
                   scenario.levers[sku].promo_weeks_per_month)
                  for sku in SKU_IDS if sku in scenario.levers),
            tuple(sorted(scenario.cost_shock.model_dump().items())),
        )
        item = expanded_by_request.get(key)
        if item is None:
            item = expand_scenario(scenario)
            expanded_by_request[key] = item
            unique_index_by_key[key] = len(unique_scenarios)
            unique_scenarios.append(scenario)
            unique_expanded.append(item)
        request_to_unique.append(unique_index_by_key[key])
        expanded.append(item)
    unique_results: list[ScenarioResult] = []
    for start in range(0, len(unique_scenarios), chunk_size):
        end = start + chunk_size
        unique_results.extend(_evaluate_chunk(
            unique_scenarios[start:end], draws, unique_expanded[start:end]
        ))
    output = []
    for index, scenario in zip(request_to_unique, scenarios, strict=True):
        item = unique_results[index]
        if item.status != "REFUSED":
            # Results are read-only values to engine callers. Reusing the
            # value avoids copying five 12-SKU maps for duplicate scenarios.
            output.append(item)
            continue
        if item.status == "REFUSED":
            item = copy.deepcopy(item)
            if item.nearest_supported_scenario is not None:
                item.nearest_supported_scenario.name = (
                    f"Nearest supported to {scenario.name}"[:80]
                )
        output.append(replace(
            item,
            volume=item.volume.copy(), gsv=item.gsv.copy(),
            nsv=item.nsv.copy(), gp=item.gp.copy(), bridge=item.bridge.copy(),
            retailer_risk_skus=item.retailer_risk_skus.copy(),
            refusal_reasons=copy.deepcopy(item.refusal_reasons),
            nearest_supported_scenario=copy.deepcopy(item.nearest_supported_scenario),
        ))
    return output


def evaluate_one(scenario: Scenario, draws: ParamDraws) -> ScenarioResult:
    return evaluate_batch([scenario], draws)[0]
