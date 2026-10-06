"""AC-007: raising a SKU's price index, holding promo constant, never
increases that SKU's modeled volume."""

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.assumptions.assumptions import SKU_IDS
from backend.engine.batch import evaluate_one
from backend.engine.scenario import Lever, Scenario
from backend.model.spec import build_param_draws
from tests.property._strategies import SUPPORTED_PRICE_HI, SUPPORTED_PRICE_LO

DRAWS = build_param_draws(k=0, seed=1)  # central-only: isolates the deterministic formula


@settings(deadline=None)
@given(
    sku=st.sampled_from(SKU_IDS),
    p_low=st.floats(min_value=SUPPORTED_PRICE_LO, max_value=SUPPORTED_PRICE_HI - 0.001, allow_nan=False),
    delta=st.floats(min_value=0.001, max_value=0.05, allow_nan=False),
)
def test_higher_price_never_increases_own_volume(sku, p_low, delta):
    p_high = min(p_low + delta, SUPPORTED_PRICE_HI)
    if p_high <= p_low:
        return
    vol_low = (
        evaluate_one(Scenario(levers={sku: Lever(price_index=p_low)}), DRAWS).volume[sku].value
    )
    vol_high = (
        evaluate_one(Scenario(levers={sku: Lever(price_index=p_high)}), DRAWS).volume[sku].value
    )
    assert vol_high <= vol_low
