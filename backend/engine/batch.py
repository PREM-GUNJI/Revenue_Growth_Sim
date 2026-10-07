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
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import numpy as np

from backend.assumptions import registry
from backend.assumptions.assumptions import FOCAL_BRAND, FORMATS, N_SKUS, SKU_IDS, SKUS
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

ENGINE_VERSION = "1.2.0"  # 1.2.0: focal-brand totals with per-draw bands; INR money scale
SKU_FORMAT = {s["sku_id"]: s["format"] for s in SKUS}
FOCAL_METRICS = ("volume", "gsv", "nsv", "gp")
_FOCAL_MASK = np.array([1.0 if s["brand"] == FOCAL_BRAND else 0.0 for s in SKUS])  # (N_SKUS,)


@lru_cache(maxsize=1)
def _raw_data():
    """The synthetic history (seed 42), generated once and shared; callers must not modify it."""
    return generate(42)


@lru_cache(maxsize=1)
def _baseline() -> Baselines:
    df = _raw_data()
    weekly = national_weekly_series(df)
    reference_draws = build_param_draws(k=0, seed=1000)  # only the central row is used
    return compute_baselines(weekly, df, reference_draws)


@lru_cache(maxsize=1)
def _data_hash() -> str:
    manifest = json.loads(Path("data/data_manifest.json").read_text())
    return manifest["data_sha256"]


@lru_cache(maxsize=1)
def _support_envelope() -> SupportEnvelope:
    return SupportEnvelope(_baseline(), build_joint_coverage(_raw_data()))


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


def _scale_quantiles(volume_q: np.ndarray, unit: np.ndarray) -> np.ndarray:
    """Quantiles (10, 50, 90) of `volume * unit` from the quantiles of volume, shape (3, S, N).

    Valid because `unit` is constant across draws and percentile interpolation is linear: a negative
    unit reverses the order, so the 10th and 90th swap.
    """
    scaled = volume_q * unit[None, :, :]
    return np.where((unit < 0)[None, :, :], scaled[::-1], scaled)


def _band_from(central: list, quantiles: list, si: int, ji: int) -> Band:
    """`central` is values[0].tolist() and `quantiles` is the (3, S, N) quantile array as lists."""
    return Band(value=central[si][ji], p10=quantiles[0][si][ji], p50=quantiles[1][si][ji], p90=quantiles[2][si][ji])


def _widen(band: Band) -> Band:
    """Widen an interval on sparse support (EDGE status) by half its radius on each side."""
    radius = max(abs(band.value - band.p10), abs(band.p90 - band.value))
    return Band(value=band.value, p10=max(0.0, band.p10 - radius * 0.5), p50=band.p50, p90=band.p90 + radius * 0.5)


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    status: str
    # The focal brand's totals (keys in FOCAL_METRICS), with bands from per-draw sums. Empty if refused.
    focal: dict[str, Band]
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

    lever_rows = [[e.levers[sku] for sku in SKU_IDS] for e in expanded]
    price_bp = np.array([[lv.price_bp for lv in row] for row in lever_rows], dtype=float)
    ln_price = np.log(price_bp / 1000.0)
    depth = np.array([[lv.depth_pct for lv in row] for row in lever_rows], dtype=float)
    weeks = np.array([[lv.weeks_per_month for lv in row] for row in lever_rows], dtype=float)
    mech = np.empty((s_count, N_SKUS), dtype=object)
    for si, row in enumerate(lever_rows):
        mech[si, :] = [lv.mechanic for lv in row]

    diag_e = np.diagonal(draws.elasticity, axis1=1, axis2=2)  # (K+1, N_SKUS)
    cross_effect = cross_price_log_effect(ln_price, draws.elasticity)  # (K+1, S, N_SKUS), own+cross
    if np.any(depth):
        promo_effect = average_monthly_promo_log_effect(depth, mech, weeks, draws)
    else:
        promo_effect = np.zeros_like(cross_effect)

    base_vec = np.array([baselines.baseline_volume[s] for s in SKU_IDS])  # (N_SKUS,)
    ln_base = np.log(base_vec)

    # Bridge stages, in log space: baseline -> +own price -> +cross-pack -> +promo (final). The bridge
    # is reported for the central draw only, so the two intermediate stages are computed for that
    # draw alone; only the final volume is needed for every draw.
    own_effect_central = diag_e[0][None, :] * ln_price  # (S, N_SKUS)
    vol1_central = np.exp(ln_base[None, :] + own_effect_central)
    vol2_central = np.exp(ln_base[None, :] + cross_effect[0])
    vol3 = np.exp(ln_base[None, None, :] + cross_effect + promo_effect)  # final volume

    ref_price_vec = np.array([baselines.reference_price[s] for s in SKU_IDS])  # (N_SKUS,)
    price_base = np.broadcast_to(ref_price_vec, (s_count, N_SKUS))
    price_final = ref_price_vec[None, :] * (price_bp / 1000.0)

    fixed_trade_pct = registry.get("A-016").value
    promo_share = (weeks / 4.0) * (depth / 100.0)  # (S, N_SKUS)

    cogs_unit_base_by_format = {fmt: cogs_per_unit(fmt, CostShock()) for fmt in FORMATS}
    cogs_base_units = np.array([cogs_unit_base_by_format[SKU_FORMAT[sku]] for sku in SKU_IDS])
    if all(not any(s.cost_shock.model_dump().values()) for s in scenarios):
        cogs_unit = np.broadcast_to(cogs_base_units, (s_count, N_SKUS))
    else:
        cogs_unit = np.zeros((s_count, N_SKUS))
        for si, scenario in enumerate(scenarios):
            for ji, sku in enumerate(SKU_IDS):
                cogs_unit[si, ji] = cogs_per_unit(SKU_FORMAT[sku], scenario.cost_shock)

    # Central draw (index 0): the reported value, the bridge and the hashed outputs.
    gsv_c = price_final * vol3[0]  # (S, N_SKUS)
    trade_c = fixed_trade_pct * gsv_c + promo_share * gsv_c
    cogs_c = cogs_unit * vol3[0]
    nsv_c = gsv_c - trade_c
    gp_c = nsv_c - cogs_c

    trade_base_all = fixed_trade_pct * price_base * base_vec[None, :]
    cogs_base_all = cogs_base_units[None, :] * base_vec[None, :]
    bridge_dollars = np.stack(
        (
            (price_final - price_base) * base_vec[None, :],
            price_final * (vol1_central - base_vec[None, :]),
            price_final * (vol2_central - vol1_central),
            price_final * (vol3[0] - vol2_central),
            trade_base_all - trade_c,
            cogs_base_all - cogs_c,
        ),
        axis=0,
    )
    bridge_cents = _cents_array(bridge_dollars)
    gp_base_all = price_base * base_vec[None, :] - trade_base_all - cogs_base_all
    gp_final_all = price_final * vol3[0] - trade_c - cogs_c
    total_bridge_cents = _cents_array(gp_final_all) - _cents_array(gp_base_all)
    residual = total_bridge_cents - bridge_cents.sum(axis=0)
    target = np.argmax(np.abs(bridge_dollars), axis=0)
    for component in range(bridge_cents.shape[0]):
        mask = target == component
        bridge_cents[component][mask] += residual[mask]

    portfolio_c = gp_c.sum(axis=1)  # (S,)
    # Focal-brand totals for the central draw, same formulas as the per-SKU values summed.
    focal_c = np.stack([(arr * _FOCAL_MASK).sum(axis=1) for arr in (vol3[0], gsv_c, nsv_c, gp_c)], axis=-1)  # (S, 4)

    # Per-SKU GSV, NSV and GP are volume times a per-unit amount that is the same in every draw
    # (price, trade rate, promo share and unit COGS are scenario inputs, only volume varies with
    # the assumption draws). Percentiles use linear interpolation, so the percentile of c * x is
    # c * percentile(x) for c >= 0 and c * percentile(x) with the 10th and 90th swapped for c < 0.
    # One volume quantile therefore gives all four per-SKU bands. Totals across SKUs (the all-brand
    # portfolio GP and the focal brand's volume, revenue, net sales and GP) are sums per draw, so
    # their quantiles come from the per-draw sums, never from adding per-SKU quantiles together.
    nsv_unit = price_final - (fixed_trade_pct * price_final + promo_share * price_final)
    gp_unit = nsv_unit - cogs_unit
    if draws.k:
        volume_q = np.percentile(vol3[1:], (10, 50, 90), axis=0)  # (3, S, N_SKUS)
        total_units = np.stack(
            [gp_unit, np.broadcast_to(_FOCAL_MASK, gp_unit.shape), price_final * _FOCAL_MASK,
             nsv_unit * _FOCAL_MASK, gp_unit * _FOCAL_MASK], axis=-1)  # (S, N_SKUS, 5)
        total_draws = np.einsum("ksn,snm->ksm", vol3[1:], total_units)  # (K, S, 5)
        total_q = np.percentile(total_draws, (10, 50, 90), axis=0)  # (3, S, 5)
        portfolio_q = total_q[:, :, 0]
        focal_q = total_q[:, :, 1:]  # volume, gsv, nsv, gp
    else:
        # No draws: every band collapses onto the central value exactly.
        volume_q = np.repeat(vol3[:1], 3, axis=0)
        portfolio_q = np.repeat(portfolio_c[None, :], 3, axis=0)
        focal_q = np.repeat(focal_c[None, :, :], 3, axis=0)
    if draws.k:
        gsv_q = _scale_quantiles(volume_q, price_final)
        nsv_q = _scale_quantiles(volume_q, nsv_unit)
        gp_q = _scale_quantiles(volume_q, gp_unit)
    else:
        gsv_q, nsv_q, gp_q = (np.repeat(c[None, :, :], 3, axis=0) for c in (gsv_c, nsv_c, gp_c))

    mh = _model_hash(draws)
    dh = _data_hash()
    rvh = spec_hash()

    # Bulk conversion to Python floats/ints: indexing numpy scalars cell by cell was the largest
    # per-scenario cost. tolist() yields the same values as float()/int() on each element.
    central = {"volume": vol3[0].tolist(), "gsv": gsv_c.tolist(), "nsv": nsv_c.tolist(), "gp": gp_c.tolist()}
    quant = {"volume": volume_q.tolist(), "gsv": gsv_q.tolist(), "nsv": nsv_q.tolist(), "gp": gp_q.tolist()}
    bridge_list = bridge_cents.tolist()
    total_bridge_list = total_bridge_cents.tolist()
    portfolio_central = portfolio_c.tolist()
    portfolio_quant = portfolio_q.tolist()
    focal_central = focal_c.tolist()  # (S, 4)
    focal_quant = focal_q.tolist()  # (3, S, 4)

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
    for si in range(len(expanded)):
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
                scenario_id=sid, status="REFUSED", focal={}, volume={}, gsv={}, nsv={}, gp={},
                portfolio_gp=None, bridge={}, retailer_risk_skus=[], result_hash=rh,
                refusal_reasons=[vars(reason) for reason in decision.reasons],
                nearest_supported_scenario=suggested,
            ))
            continue
        volume_bands, gsv_bands, nsv_bands, gp_bands, bridge = {}, {}, {}, {}, {}
        flagged = []
        outputs_quantized: dict[str, dict] = {}

        for ji, sku in enumerate(SKU_IDS):
            volume_bands[sku] = _band_from(central["volume"], quant["volume"], si, ji)
            gsv_bands[sku] = _band_from(central["gsv"], quant["gsv"], si, ji)
            nsv_bands[sku] = _band_from(central["nsv"], quant["nsv"], si, ji)
            gp_bands[sku] = _band_from(central["gp"], quant["gp"], si, ji)

            if decision.status == "EDGE":
                # Explicitly widen all reported intervals on sparse support.
                for bands in (volume_bands, gsv_bands, nsv_bands, gp_bands):
                    bands[sku] = _widen(bands[sku])

            bridge[sku] = Bridge(
                price_cents=bridge_list[0][si][ji],
                volume_cents=bridge_list[1][si][ji],
                cross_pack_cents=bridge_list[2][si][ji],
                promo_cents=bridge_list[3][si][ji],
                trade_cents=bridge_list[4][si][ji],
                cogs_cents=bridge_list[5][si][ji],
                total_cents=total_bridge_list[si][ji],
            )
            if retailer_risk_mask[si, ji]:
                flagged.append(sku)

            outputs_quantized[sku] = {
                "volume_centiunits": round(central["volume"][si][ji] * 100),
                "gsv_cents": round(central["gsv"][si][ji] * 100),
                "nsv_cents": round(central["nsv"][si][ji] * 100),
                "gp_cents": round(central["gp"][si][ji] * 100),
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

        focal = {
            name: Band(value=focal_central[si][mi], p10=focal_quant[0][si][mi],
                       p50=focal_quant[1][si][mi], p90=focal_quant[2][si][mi])
            for mi, name in enumerate(FOCAL_METRICS)
        }
        if decision.status == "EDGE":
            focal = {name: _widen(band) for name, band in focal.items()}

        results.append(
            ScenarioResult(
                scenario_id=sid,
                status=decision.status,
                focal=focal,
                volume=volume_bands,
                gsv=gsv_bands,
                nsv=nsv_bands,
                gp=gp_bands,
                portfolio_gp=Band(value=portfolio_central[si],
                                  p10=portfolio_quant[0][si],
                                  p50=portfolio_quant[1][si],
                                  p90=portfolio_quant[2][si]),
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
        # A refused result carries the caller's own name in its suggestion, so each request gets its
        # own copy of just the mutable parts (the maps are empty for a refusal).
        nearest = item.nearest_supported_scenario
        if nearest is not None:
            nearest = nearest.model_copy(update={"name": f"Nearest supported to {scenario.name}"[:80]})
        output.append(replace(
            item,
            volume=item.volume.copy(), gsv=item.gsv.copy(),
            nsv=item.nsv.copy(), gp=item.gp.copy(), bridge=item.bridge.copy(),
            retailer_risk_skus=item.retailer_risk_skus.copy(),
            refusal_reasons=[dict(reason) for reason in item.refusal_reasons],  # values are str/float/tuple
            nearest_supported_scenario=nearest,
        ))
    return output


def evaluate_one(scenario: Scenario, draws: ParamDraws) -> ScenarioResult:
    return evaluate_batch([scenario], draws)[0]
