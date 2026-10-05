"""AC-006: a scenario with zero lever changes evaluates to exactly the
baseline (bit-for-bit after quantization)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.assumptions.assumptions import SKU_IDS
from backend.engine.batch import evaluate_one
from backend.engine.scenario import Scenario
from backend.model.spec import build_param_draws


# deadline=None: the first example pays for the one-time _baseline() cache
# warm-up (generates the dataset), which is slow relative to every later
# call; that's a fixed cost, not a per-example performance regression.
@settings(deadline=None)
@given(k=st.integers(min_value=0, max_value=20), seed=st.integers(min_value=1, max_value=10_000))
def test_empty_scenario_matches_baseline_volume_exactly(k, seed):
    draws = build_param_draws(k=k, seed=seed)
    result = evaluate_one(Scenario(), draws)

    from backend.engine.batch import _baseline

    baseline_volume = _baseline().baseline_volume
    for sku in SKU_IDS:
        assert result.volume[sku].value == baseline_volume[sku]
        # no price/promo change => zero variance across draws regardless of seed
        assert result.volume[sku].p10 == result.volume[sku].p90 == baseline_volume[sku]


def test_empty_scenario_bridge_is_all_zero():
    draws = build_param_draws(k=5, seed=1)
    result = evaluate_one(Scenario(), draws)
    for sku in SKU_IDS:
        b = result.bridge[sku]
        assert (b.price_cents, b.volume_cents, b.cross_pack_cents, b.promo_cents) == (0, 0, 0, 0)
        assert (b.trade_cents, b.cogs_cents, b.total_cents) == (0, 0, 0)
