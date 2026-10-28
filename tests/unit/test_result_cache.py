"""Content-addressed result cache (A-038) returns identical hashes on hit."""

from backend.assumptions.assumptions import SKU_IDS
from backend.engine.batch import clear_result_cache, evaluate_batch, evaluate_one
from backend.engine.scenario import Lever, Scenario
from backend.model.spec import build_param_draws

_SKU = SKU_IDS[0]


def test_cache_hit_same_result_hash():
    clear_result_cache()
    draws = build_param_draws(k=5, seed=7)
    scenario = Scenario(
        name="cache-probe",
        levers={_SKU: Lever(price_index=1.02, promo_depth_pct=0.0)},
    )
    first = evaluate_one(scenario, draws)
    second = evaluate_one(scenario, draws)
    assert first.result_hash == second.result_hash
    assert first.scenario_id == second.scenario_id
    assert first is second  # same cached object


def test_different_seed_busts_cache():
    clear_result_cache()
    scenario = Scenario(name="seed-bust", levers={_SKU: Lever(price_index=1.01)})
    a = evaluate_one(scenario, build_param_draws(k=5, seed=1))
    b = evaluate_one(scenario, build_param_draws(k=5, seed=2))
    assert a.result_hash != b.result_hash


def test_batch_dedup_matches_single():
    clear_result_cache()
    draws = build_param_draws(k=5, seed=3)
    scenario = Scenario(name="dup", levers={_SKU: Lever(price_index=0.98)})
    batch = evaluate_batch([scenario, scenario], draws)
    single = evaluate_one(scenario, draws)
    assert batch[0].result_hash == batch[1].result_hash == single.result_hash
