"""Canonical quantization and hashing (PLAN.md section 9).

`scenario_id` must be stable across platforms, so every lever is quantized
to an int before hashing: price to basis points (0.001 steps), depth/weeks
to whole units. `name` is display-only and is never part of the hash.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

from backend.assumptions.assumptions import SKU_IDS
from backend.engine.scenario import Lever, Scenario


@lru_cache(maxsize=65536)  # pure in (value, step); lever values repeat heavily across a batch
def _quantize(value: float, step: str) -> int:
    return int((Decimal(str(value)) / Decimal(step)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def quantize_price_bp(price_index: float) -> int:
    return _quantize(price_index, "0.001")


def quantize_pct(pct: float) -> int:
    return _quantize(pct, "1")


def quantize_tenth_pct(pct: float) -> int:
    return _quantize(pct, "0.1")


@dataclass(frozen=True)
class QuantizedLever:
    price_bp: int
    depth_pct: int
    mechanic: str
    weeks_per_month: int


@dataclass(frozen=True)
class ExpandedScenario:
    schema_version: int
    levers: dict[str, QuantizedLever]  # every SKU_ID present
    cost_shock: dict[str, int]  # tenths-of-percent


def _quantize_lever(lever: Lever) -> QuantizedLever:
    return QuantizedLever(
        price_bp=quantize_price_bp(lever.price_index),
        depth_pct=quantize_pct(lever.promo_depth_pct),
        mechanic=lever.mechanic,
        weeks_per_month=quantize_pct(lever.promo_weeks_per_month),
    )


_BASELINE_LEVER = _quantize_lever(Lever())  # frozen, so one shared instance is safe


def expand_scenario(scenario: Scenario) -> ExpandedScenario:
    """Fills in every omitted SKU with the baseline (no-change) Lever and
    quantizes every value to an int, so hashing never sees a float."""
    levers = {}
    for sku in SKU_IDS:
        lever = scenario.levers.get(sku)
        if lever is None:  # omitted SKUs are the baseline lever; quantise it once, not per scenario
            levers[sku] = _BASELINE_LEVER
            continue
        levers[sku] = _quantize_lever(lever)
    cost_shock = {
        "aluminium_pct": quantize_tenth_pct(scenario.cost_shock.aluminium_pct),
        "pet_resin_pct": quantize_tenth_pct(scenario.cost_shock.pet_resin_pct),
        "sugar_pct": quantize_tenth_pct(scenario.cost_shock.sugar_pct),
    }
    return ExpandedScenario(
        schema_version=scenario.schema_version, levers=levers, cost_shock=cost_shock
    )


def canonical_json(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _expanded_payload(expanded: ExpandedScenario) -> dict:
    return {
        "schema_version": expanded.schema_version,
        "levers": {
            sku: {
                "price_bp": lv.price_bp,
                "depth_pct": lv.depth_pct,
                "mechanic": lv.mechanic,
                "weeks_per_month": lv.weeks_per_month,
            }
            for sku, lv in expanded.levers.items()
        },
        "cost_shock": dict(expanded.cost_shock),
    }


def scenario_id(expanded: ExpandedScenario) -> str:
    return hashlib.sha256(canonical_json(_expanded_payload(expanded))).hexdigest()


def result_hash(
    *,
    scenario_id_: str,
    engine_version: str,
    model_hash: str,
    data_hash: str,
    registry_values_hash: str,
    k: int,
    seed: int,
    status: str,
    reasons: list[str],
    outputs_quantized: dict,
) -> str:
    """Hash of everything that determines a result bit-for-bit, so two runs
    producing the same hash are provably reproducing the same computation."""
    payload = {
        "scenario_id": scenario_id_,
        "engine_version": engine_version,
        "model_hash": model_hash,
        "data_hash": data_hash,
        "registry_values_hash": registry_values_hash,
        "k": k,
        "seed": seed,
        "status": status,
        "reasons": sorted(reasons),
        "outputs": outputs_quantized,
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()
