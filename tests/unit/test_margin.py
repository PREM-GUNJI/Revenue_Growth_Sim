"""Margin building blocks: COGS, trade spend, and the retailer-risk flag."""

from backend.engine.ids import QuantizedLever
from backend.engine.margin import cogs_per_unit, retailer_risk, trade_spend
from backend.engine.scenario import CostShock


def test_cogs_increases_with_shock():
    base = cogs_per_unit("can_330ml", CostShock())
    shocked = cogs_per_unit("can_330ml", CostShock(aluminium_pct=20.0))
    assert shocked > base


def test_cogs_pet_resin_shock_does_not_affect_can():
    base = cogs_per_unit("can_330ml", CostShock())
    shocked = cogs_per_unit("can_330ml", CostShock(pet_resin_pct=50.0))
    assert shocked == base


def test_trade_spend_zero_promo_is_fixed_terms_only():
    lever = QuantizedLever(price_bp=1000, depth_pct=0, mechanic="none", weeks_per_month=0)
    spend = trade_spend(price=1.0, volume=100.0, lever=lever)
    assert spend > 0  # fixed trade terms still apply
    deeper = trade_spend(
        price=1.0,
        volume=100.0,
        lever=QuantizedLever(price_bp=1000, depth_pct=20, mechanic="TPR", weeks_per_month=2),
    )
    assert deeper > spend


def test_retailer_risk_fires_on_price_increase_with_partial_pass_through():
    assert retailer_risk(1.0) is False
    assert retailer_risk(1.5) is True
