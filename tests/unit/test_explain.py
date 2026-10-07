from __future__ import annotations

import pytest

from backend.assumptions.assumptions import ASSUMPTIONS
from backend.engine.batch import evaluate_batch
from backend.engine.explain import assumption_ids_for, focal_bridge
from backend.engine.scenario import Lever, Scenario
from backend.model.spec import build_param_draws

CAN, BOTTLE = "Aurora-can_330ml", "Aurora-bottle_1500ml"


def test_baseline_depends_only_on_costs_trade_support_and_declared_limits() -> None:
    result = set(assumption_ids_for(Scenario(name="base")))
    assert {"A-013", "A-015", "A-016", "A-014a", "A-014d", "A-018", "A-021", "A-022", "A-023"} <= result
    assert not result & {"A-001", "A-002", "A-005", "A-007", "A-008"}  # nothing moved, so no demand response


def test_a_price_move_brings_in_that_formats_elasticity_and_cross_effects() -> None:
    result = set(assumption_ids_for(Scenario(name="s", levers={CAN: Lever(price_index=1.04)})))
    assert {"A-001", "A-005", "A-006", "A-017", "A-017b"} <= result
    assert "A-003" not in result and "A-007" not in result  # bottle elasticity and promo curve are not involved


def test_a_promotion_brings_in_the_promo_curve_and_its_mechanic_only() -> None:
    lever = Lever(promo_depth_pct=15, mechanic="feature_display", promo_weeks_per_month=2)
    result = set(assumption_ids_for(Scenario(name="s", levers={BOTTLE: lever})))
    assert {"A-007", "A-008", "A-012", "A-010"} <= result
    assert "A-009" not in result and "A-011" not in result
    assert "A-003" not in result  # price did not move


def test_every_id_returned_is_a_registered_assumption() -> None:
    scenario = Scenario(name="s", levers={CAN: Lever(price_index=1.02, promo_depth_pct=10, mechanic="BOGO", promo_weeks_per_month=1)})
    assert set(assumption_ids_for(scenario)) <= set(ASSUMPTIONS)
    assert assumption_ids_for(scenario) == sorted(assumption_ids_for(scenario))


def test_focal_bridge_adds_up_exactly_and_major_units_are_rupees() -> None:
    scenario = Scenario(name="s", levers={CAN: Lever(price_index=0.97), BOTTLE: Lever(price_index=1.03)})
    result = evaluate_batch([scenario], build_param_draws(k=0, seed=42))[0]
    minor, major = focal_bridge(result), focal_bridge(result, major_units=True)
    parts = ("price_cents", "volume_cents", "cross_pack_cents", "promo_cents", "trade_cents", "cogs_cents")
    assert sum(minor[p] for p in parts) == minor["total_cents"]
    assert major["total"] == pytest.approx(minor["total_cents"] / 100)
    assert set(major) == {"price", "volume", "cross_pack", "promo", "trade", "cogs", "total"}


def test_focal_bridge_is_none_for_a_refused_scenario() -> None:
    result = evaluate_batch([Scenario(name="s", levers={CAN: Lever(price_index=1.9)})], build_param_draws(k=0, seed=42))[0]
    assert focal_bridge(result) is None
