"""The focal brand's totals carry bands computed from per-draw sums.

Adding per-SKU quantiles together is not a quantile of the sum, so the engine builds the focal brand's
(Aurora's) volume, revenue, net sales and gross-profit bands from each draw's own total. This checks
them against a brute-force reference: evaluate every draw on its own, sum the focal SKUs yourself, then
take percentiles of those true sums.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from backend.assumptions.assumptions import FOCAL_BRAND, SKUS
from backend.engine.batch import FOCAL_METRICS, evaluate_batch
from backend.engine.scenario import CostShock, Lever, Scenario
from backend.model.spec import ParamDraws, build_param_draws

CAN, PET, BOTTLE = "Aurora-can_330ml", "Aurora-pet_500ml", "Aurora-bottle_1500ml"
FOCAL_SKUS = [s["sku_id"] for s in SKUS if s["brand"] == FOCAL_BRAND]
K = 60


def one_draw(draws: ParamDraws, j: int) -> ParamDraws:
    """Central row plus draw j only, so the single non-central draw's values come back unaggregated."""
    pick = [0, j]
    return replace(
        draws, k=1, elasticity=draws.elasticity[pick], promo_k=draws.promo_k[pick], promo_b=draws.promo_b[pick],
        pull_forward_share=draws.pull_forward_share[pick],
        mech_mult={name: arr[pick] for name, arr in draws.mech_mult.items()},
    )


SCENARIOS = {
    "baseline": Scenario(name="baseline"),
    "price": Scenario(name="price", levers={CAN: Lever(price_index=1.04)}),
    "promo": Scenario(name="promo", levers={PET: Lever(promo_depth_pct=15, mechanic="TPR", promo_weeks_per_month=2)}),
    "mixed + cost": Scenario(
        name="mixed",
        levers={CAN: Lever(price_index=0.97), BOTTLE: Lever(price_index=1.03, promo_depth_pct=10,
                                                              mechanic="feature_display", promo_weeks_per_month=1)},
        cost_shock=CostShock(aluminium_pct=10, pet_resin_pct=5, sugar_pct=8),
    ),
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_focal_bands_match_brute_force_per_draw_sums(name: str) -> None:
    scenario = SCENARIOS[name]
    draws = build_param_draws(k=K, seed=42)
    result = evaluate_batch([scenario], draws)[0]
    assert result.status != "REFUSED"

    per_draw = {metric: [] for metric in FOCAL_METRICS}
    portfolio = []
    for j in range(1, K + 1):
        single = evaluate_batch([scenario], one_draw(draws, j))[0]
        for metric in FOCAL_METRICS:
            per_draw[metric].append(sum(getattr(single, metric)[sku].p50 for sku in FOCAL_SKUS))
        portfolio.append(single.portfolio_gp.p50)

    for metric in FOCAL_METRICS:
        p10, p50, p90 = np.percentile(per_draw[metric], (10, 50, 90))
        band = result.focal[metric]
        assert band.p10 == pytest.approx(p10, rel=1e-9), (metric, "p10")
        assert band.p50 == pytest.approx(p50, rel=1e-9), (metric, "p50")
        assert band.p90 == pytest.approx(p90, rel=1e-9), (metric, "p90")
        # The central value is exactly the focal SKUs' central values added up.
        assert band.value == pytest.approx(sum(getattr(result, metric)[sku].value for sku in FOCAL_SKUS), rel=1e-12)
    p10, p50, p90 = np.percentile(portfolio, (10, 50, 90))
    assert result.portfolio_gp.p10 == pytest.approx(p10, rel=1e-9)
    assert result.portfolio_gp.p90 == pytest.approx(p90, rel=1e-9)


def test_focal_total_excludes_competitor_skus() -> None:
    result = evaluate_batch([Scenario(name="baseline")], build_param_draws(k=0, seed=42))[0]
    competitor_gp = sum(b.value for sku, b in result.gp.items() if sku not in FOCAL_SKUS)
    assert competitor_gp > 0
    assert result.portfolio_gp.value == pytest.approx(result.focal["gp"].value + competitor_gp, rel=1e-12)


def test_a_competitor_price_cut_moves_focal_volume_only_through_cross_elasticity() -> None:
    boreal_can = "Boreal-can_330ml"
    base, cut = evaluate_batch(
        [Scenario(name="base"), Scenario(name="cut", levers={boreal_can: Lever(price_index=0.95)})],
        build_param_draws(k=0, seed=42),
    )
    assert cut.focal["volume"].value < base.focal["volume"].value  # Aurora loses a little volume
    assert cut.focal["volume"].value > 0.97 * base.focal["volume"].value  # across-brand effect is weak


def test_refused_scenario_has_no_focal_numbers() -> None:
    refused = evaluate_batch([Scenario(name="x", levers={CAN: Lever(price_index=1.9)})], build_param_draws(k=20, seed=42))[0]
    assert refused.status == "REFUSED" and refused.focal == {}


def test_with_no_draws_the_bands_collapse_onto_the_value() -> None:
    result = evaluate_batch([SCENARIOS["price"]], build_param_draws(k=0, seed=42))[0]
    for band in result.focal.values():
        assert band.p10 == band.p50 == band.p90 == band.value
