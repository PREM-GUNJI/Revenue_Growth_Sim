"""AC-008: the margin bridge's components (price, volume, cross-pack, promo
net of pull-forward, trade, COGS) sum exactly to the total change in gross
profit, for every scenario."""

from hypothesis import given, settings

from backend.assumptions.assumptions import SKU_IDS
from backend.engine.batch import evaluate_one
from backend.model.spec import build_param_draws
from tests.property._strategies import scenario_strategy

DRAWS = build_param_draws(k=0, seed=1)


@settings(max_examples=100, deadline=None)
@given(scenario=scenario_strategy())
def test_bridge_components_sum_to_total(scenario):
    result = evaluate_one(scenario, DRAWS)
    for sku in SKU_IDS:
        b = result.bridge[sku]
        parts = (
            b.price_cents
            + b.volume_cents
            + b.cross_pack_cents
            + b.promo_cents
            + b.trade_cents
            + b.cogs_cents
        )
        assert parts == b.total_cents
