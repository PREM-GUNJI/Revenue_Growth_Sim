"""Phase 5 acceptance checks for refusal integrity and nearest alternatives."""

from backend.assumptions.assumptions import SKU_IDS
from backend.engine.batch import evaluate_batch
from backend.engine.scenario import Lever, Scenario
from backend.model.spec import build_param_draws

DRAWS = build_param_draws(k=0, seed=7)


def test_out_of_range_refuses_whole_scenario_without_numeric_outputs():
    result = evaluate_batch(
        [Scenario(levers={SKU_IDS[0]: Lever(price_index=1.5)})], DRAWS
    )[0]
    assert result.status == "REFUSED"
    assert result.volume == result.gsv == result.nsv == result.gp == {}
    assert result.portfolio_gp is None
    assert result.bridge == {}
    assert result.refusal_reasons
    assert result.nearest_supported_scenario is not None


def test_nearest_supported_returns_separate_supported_scenario():
    from backend.engine.batch import _support_envelope

    original = Scenario(levers={SKU_IDS[0]: Lever(price_index=1.5)})
    before = original.model_dump(mode="json")
    from backend.engine.support import nearest_supported

    nearest = nearest_supported(original, _support_envelope())
    assert _support_envelope().check(nearest.scenario).status != "REFUSED"
    assert original.model_dump(mode="json") == before
    assert nearest.scenario != original
    assert nearest.distance > 0


def test_labelled_refusal_set_has_full_out_of_range_recall_and_precision():
    """500 deterministic labels exercise refusal recall and false-positive rate."""
    cases = []
    labels = []
    for i in range(250):
        sku = SKU_IDS[i % len(SKU_IDS)]
        price = 1.5 + (i % 50) / 1000
        cases.append(Scenario(levers={sku: Lever(price_index=price)}))
        labels.append("REFUSED")
    for _ in range(250):
        cases.append(Scenario())
        labels.append("SUPPORTED")
    from backend.engine.batch import _support_envelope

    decisions = [_support_envelope().check(scenario) for scenario in cases]
    tp = sum(label == "REFUSED" and result.status == "REFUSED" for label, result in zip(labels, decisions, strict=True))
    fp = sum(label == "SUPPORTED" and result.status == "REFUSED" for label, result in zip(labels, decisions, strict=True))
    assert tp / labels.count("REFUSED") == 1.0
    assert tp / (tp + fp) >= 0.95
