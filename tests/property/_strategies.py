"""Shared hypothesis strategies for engine property tests."""

from hypothesis import strategies as st

from backend.assumptions.assumptions import PROMO_MECHANICS, SKU_IDS
from backend.engine.scenario import CostShock, Lever, Scenario

PRICE_INDEX = st.floats(min_value=0.5, max_value=2.0, allow_nan=False)
DEPTH_PCT = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)
WEEKS = st.floats(min_value=0.0, max_value=4.0, allow_nan=False)
PCT_SHOCK = st.floats(min_value=-50.0, max_value=200.0, allow_nan=False)

non_none_mechanics = [m for m in PROMO_MECHANICS if m != "none"]

lever_strategy = st.one_of(
    st.just(Lever()),
    st.builds(
        Lever,
        price_index=PRICE_INDEX,
        promo_depth_pct=DEPTH_PCT,
        mechanic=st.sampled_from(non_none_mechanics),
        promo_weeks_per_month=WEEKS,
    ),
)

cost_shock_strategy = st.builds(
    CostShock, aluminium_pct=PCT_SHOCK, pet_resin_pct=PCT_SHOCK, sugar_pct=PCT_SHOCK
)


@st.composite
def scenario_strategy(draw):
    skus = draw(st.lists(st.sampled_from(SKU_IDS), unique=True, max_size=len(SKU_IDS)))
    levers = {sku: draw(lever_strategy) for sku in skus}
    cost_shock = draw(cost_shock_strategy)
    return Scenario(levers=levers, cost_shock=cost_shock)
