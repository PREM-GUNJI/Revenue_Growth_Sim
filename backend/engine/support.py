"""Deterministic support-envelope checks for scenario refusal (Phase 5).

The envelope uses observed 1st--99th price percentiles and a local occupancy
count from the synthetic data. The local window includes adjacent bins so a
boundary does not change status merely because of bin alignment. Thresholds
are explicit configuration values and are surfaced as assumptions in the
return values rather than hidden model fitting.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.assumptions import registry
from backend.assumptions.assumptions import SKU_IDS, SKUS
from backend.engine.scenario import Scenario
from backend.model.baselines import Baselines
from backend.model.envelope_build import N_PRICE_BINS, JointCoverage


@dataclass(frozen=True)
class SupportReason:
    sku_id: str
    lever: str
    requested: float | str
    supported_range: tuple[float, float] | tuple[str, ...]
    message: str


@dataclass(frozen=True)
class SupportDecision:
    status: str
    reasons: tuple[SupportReason, ...]
    local_rows: dict[str, int]


@dataclass(frozen=True)
class NearestSupported:
    scenario: Scenario
    distance: float


class SupportEnvelope:
    """Checks each SKU and refuses the whole scenario if any lever is unsafe."""

    def __init__(self, baselines: Baselines, coverage: JointCoverage):
        self.baselines = baselines
        self.coverage = coverage
        self._format_index = {v: i for i, v in enumerate(coverage.formats)}
        self._mechanic_index = {v: i for i, v in enumerate(coverage.mechanics)}
        self._depth_index = {v: i for i, v in enumerate(coverage.depth_steps)}
        self._decision_cache: dict[tuple, SupportDecision] = {}

    def _local_count(self, fmt: str, mechanic: str, depth: int, price: float) -> int:
        fi = self._format_index.get(fmt)
        mi = self._mechanic_index.get(mechanic)
        di = self._depth_index.get(depth)
        if fi is None or mi is None or di is None:
            return 0
        edges = self.coverage.price_bin_edges
        pi = int(np.clip(np.digitize(price, edges[1:-1]), 0, N_PRICE_BINS - 1))
        # Adjacent price bins are included per PLAN.md section 6.
        lo, hi = max(0, pi - 1), min(N_PRICE_BINS, pi + 2)
        return int(self.coverage.counts[fi, mi, di, lo:hi].sum())

    def check(self, scenario: Scenario) -> SupportDecision:
        # A cached decision must still register its governing assumptions as read.
        registry.get("A-022")
        registry.get("A-023")
        cache_limit = registry.get("A-025").value
        key = []
        for sku in SKU_IDS:
            lever = scenario.levers.get(sku)
            if lever is None:
                key.append((sku, 1.0, 0.0, "none", 0.0))
            else:
                key.append((sku, lever.price_index, lever.promo_depth_pct,
                            lever.mechanic, lever.promo_weeks_per_month))
        cache_key = tuple(key)
        cached = self._decision_cache.get(cache_key)
        if cached is not None:
            return cached
        decision = self._check_key(cache_key)
        if len(self._decision_cache) >= cache_limit:
            self._decision_cache.clear()
        self._decision_cache[cache_key] = decision
        return decision

    def _check_key(self, key: tuple) -> SupportDecision:
        reasons: list[SupportReason] = []
        local_rows: dict[str, int] = {}
        for sku, price, depth, mechanic, _weeks in key:
            lo, hi = self.baselines.price_index_p1_p99[sku]
            if price < lo or price > hi:
                reasons.append(SupportReason(sku, "price_index", price, (lo, hi),
                    f"{sku}: price_index {price:g} outside observed 1st-99th percentile [{lo:.4f}, {hi:.4f}]"))
            if depth not in self.baselines.promo_depth_observed:
                reasons.append(SupportReason(sku, "promo_depth_pct", depth,
                    tuple(map(float, self.baselines.promo_depth_observed)),
                    f"{sku}: promo_depth_pct {depth:g} is not an observed depth"))
            # SKU format lookup is local data metadata, not a modeled quantity.
            fmt = next(row["format"] for row in SKUS if row["sku_id"] == sku)
            count = self._local_count(fmt, mechanic, int(round(depth)), price)
            local_rows[sku] = count
            if count < registry.get("A-022").value:
                reasons.append(SupportReason(sku, "joint_support", float(count),
                    (f"at least {registry.get('A-022').value} local row",),
                    f"{sku}: requested price/promo combination has no local observations (count={count})"))
        status = "REFUSED" if reasons else (
            "EDGE" if any(n < registry.get("A-023").value for n in local_rows.values()) else "SUPPORTED"
        )
        return SupportDecision(status, tuple(reasons), local_rows)


def nearest_supported(scenario: Scenario, envelope: SupportEnvelope) -> NearestSupported:
    """Offer a separate nearest candidate; never evaluates or alters the request."""
    from backend.assumptions.assumptions import PROMO_DEPTH_STEPS
    from backend.engine.scenario import Lever

    candidate = scenario.model_copy(deep=True)
    for sku in SKU_IDS:
        lever = candidate.levers.get(sku, Lever())
        lo, hi = envelope.baselines.price_index_p1_p99[sku]
        price = min(max(lever.price_index, lo), hi)
        depth = min(PROMO_DEPTH_STEPS, key=lambda x: abs(x - lever.promo_depth_pct))
        if depth == 0:
            mechanic = "none"
        elif lever.mechanic == "none":
            mechanic = "TPR"
        else:
            mechanic = lever.mechanic
        candidate.levers[sku] = Lever(price_index=price, promo_depth_pct=float(depth),
            mechanic=mechanic, promo_weeks_per_month=lever.promo_weeks_per_month if depth else 0.0)
    decision = envelope.check(candidate)
    # If the independently suggested point still falls in a deliberate joint gap,
    # step the price down by observed bin increments until it is supported.
    step = float(np.median(np.diff(envelope.coverage.price_bin_edges)))
    for _ in range(N_PRICE_BINS):
        if decision.status != "REFUSED":
            break
        for sku in SKU_IDS:
            lv = candidate.levers[sku]
            lo, hi = envelope.baselines.price_index_p1_p99[sku]
            lv.price_index = max(lo, min(hi, lv.price_index - step))
        decision = envelope.check(candidate)
    if decision.status == "REFUSED":
        # The untouched baseline is the guaranteed fallback suggestion.
        defaults = {
            sku: Lever(promo_weeks_per_month=0.0)
            for sku in SKU_IDS
        }
        candidate = Scenario(name=f"Nearest supported to {scenario.name}"[:80],
                             levers=defaults, cost_shock=scenario.cost_shock)
        decision = envelope.check(candidate)
    if decision.status == "REFUSED":
        raise RuntimeError("support envelope contains no evaluable baseline scenario")
    original = scenario.model_copy(deep=True)
    distance = 0.0
    for sku in SKU_IDS:
        a, b = original.levers.get(sku, Lever()), candidate.levers[sku]
        distance += abs(a.price_index - b.price_index) + abs(a.promo_depth_pct - b.promo_depth_pct) / 100
    return NearestSupported(candidate, distance)
