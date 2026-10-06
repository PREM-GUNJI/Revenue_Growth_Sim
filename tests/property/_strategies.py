"""Shared hypothesis strategies for engine property tests."""

from hypothesis import strategies as st

from backend.assumptions.assumptions import SKU_IDS
from backend.engine.batch import _baseline
from backend.engine.scenario import CostShock, Lever, Scenario

_BASELINES = _baseline()
SUPPORTED_PRICE_LO = max(v[0] for v in _BASELINES.price_index_p1_p99.values())
SUPPORTED_PRICE_HI = min(v[1] for v in _BASELINES.price_index_p1_p99.values())
PRICE_INDEX = st.floats(min_value=SUPPORTED_PRICE_LO, max_value=SUPPORTED_PRICE_HI, allow_nan=False)
PCT_SHOCK = st.floats(min_value=-50.0, max_value=200.0, allow_nan=False)

lever_strategy = st.one_of(st.just(Lever()), st.builds(Lever, price_index=PRICE_INDEX))

cost_shock_strategy = st.builds(
    CostShock, aluminium_pct=PCT_SHOCK, pet_resin_pct=PCT_SHOCK, sugar_pct=PCT_SHOCK
)


@st.composite
def scenario_strategy(draw):
    skus = draw(st.lists(st.sampled_from(SKU_IDS), unique=True, max_size=len(SKU_IDS)))
    levers = {sku: draw(lever_strategy) for sku in skus}
    cost_shock = draw(cost_shock_strategy)
    return Scenario(levers=levers, cost_shock=cost_shock)
