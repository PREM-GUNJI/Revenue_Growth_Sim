"""AC-009: evaluating a batch of N scenarios produces the same per-scenario
results, in the same order, as evaluating each one individually."""

from dataclasses import asdict

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.engine.batch import evaluate_batch, evaluate_one
from backend.model.spec import build_param_draws
from tests.property._strategies import scenario_strategy

DRAWS = build_param_draws(k=10, seed=1)


def _comparable(result):
    return {
        "scenario_id": result.scenario_id,
        "result_hash": result.result_hash,
        "volume": {sku: asdict(b) for sku, b in result.volume.items()},
        "gp": {sku: asdict(b) for sku, b in result.gp.items()},
        "bridge": {sku: asdict(b) for sku, b in result.bridge.items()},
    }


@settings(max_examples=25, deadline=None)
@given(scenarios=st.lists(scenario_strategy(), min_size=1, max_size=6))
def test_batch_matches_sequential_single_evaluation(scenarios):
    batch_results = evaluate_batch(scenarios, DRAWS)
    single_results = [evaluate_one(s, DRAWS) for s in scenarios]

    assert len(batch_results) == len(single_results) == len(scenarios)
    for b, s in zip(batch_results, single_results, strict=True):
        assert _comparable(b) == _comparable(s)
