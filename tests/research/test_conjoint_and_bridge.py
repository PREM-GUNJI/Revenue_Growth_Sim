"""AC-030..AC-032: conjoint simulation, the research -> RGM bridge, provenance and refusal."""

from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from backend.assumptions import registry
from backend.engine.batch import ENGINE_VERSION, evaluate_batch
from backend.engine.scenario import Scenario
from backend.model.spec import build_param_draws
from backend.research.evidence import (
    CONJOINT_STATEMENT,
    conjoint_simulation,
    default_conjoint_alternatives,
    generate_consumers,
    reference_price,
    research_to_scenarios,
    run_research,
)

CONSUMERS = generate_consumers(42, 250)


def _alts():
    return [
        {"brand": "Aurora", "pack": "pet_500ml", "price": 45, "promotion": "None"},
        {"brand": "Aurora", "pack": "pet_500ml", "price": 43, "promotion": "10% off"},
        {"brand": "Boreal", "pack": "pet_500ml", "price": 45, "promotion": "None"},
        {"brand": "Comet", "pack": "can_330ml", "price": 40, "promotion": "20% off"},
    ]


def test_ac030_conjoint_choice_probabilities_sum_to_100_percent():
    result = conjoint_simulation(CONSUMERS, _alts())
    shares = result.outputs["choice_share_pct"]
    assert abs(sum(shares) - 100) < 1e-6 and all(0 < s < 100 for s in shares)
    for segment_shares in result.outputs["choice_share_pct_by_segment"].values():
        assert abs(sum(segment_shares) - 100) < 0.1  # per-share rounding to 2 dp


def test_ac030_conjoint_is_deterministic_and_states_it_does_not_fit():
    a, b = conjoint_simulation(CONSUMERS, _alts()), conjoint_simulation(CONSUMERS, _alts())
    assert a == b and a.outputs["statement"] == CONJOINT_STATEMENT
    assert "does not estimate or fit consumer utilities" in CONJOINT_STATEMENT


def test_ac030_conjoint_uses_only_supplied_utilities():
    supplied = copy.deepcopy(registry.get("A-037").value)
    base = conjoint_simulation(CONSUMERS, _alts(), supplied).outputs["choice_share_pct"]
    assert (
        base == conjoint_simulation(CONSUMERS, _alts()).outputs["choice_share_pct"]
    )  # default = registry values
    supplied["brand"]["Boreal"] += (
        2.0  # the caller's utilities move the result; nothing is re-estimated
    )
    boosted = conjoint_simulation(CONSUMERS, _alts(), supplied).outputs["choice_share_pct"]
    assert boosted[2] > base[2]
    supplied["promotion"].pop("10% off")
    with pytest.raises(ValueError, match="no supplied utility"):
        conjoint_simulation(CONSUMERS, _alts(), supplied)


def test_ac030_lower_price_never_lowers_own_share():
    cheaper, dearer = _alts(), _alts()
    cheaper[0]["price"], dearer[0]["price"] = 41, 49
    assert (
        conjoint_simulation(CONSUMERS, cheaper).outputs["choice_share_pct"][0]
        > conjoint_simulation(CONSUMERS, dearer).outputs["choice_share_pct"][0]
    )


def test_ac030_default_alternatives_are_registry_derived_and_observed():
    alts = default_conjoint_alternatives("Aurora", "pet_500ml")
    assert alts[1]["price"] == reference_price("pet_500ml")
    assert all(a["pack"] == "pet_500ml" for a in alts)


def test_ac031_candidates_map_to_engine_scenarios_and_engine_owns_the_numbers():
    research = run_research("Willingness to Pay", CONSUMERS)
    rows = research_to_scenarios(research, "Aurora")
    assert len(rows) == len(research.candidates)
    for candidate, row in zip(research.candidates, rows, strict=True):
        lever = row["scenario"]["levers"]["Aurora-pet_500ml"]
        assert lever["price_index"] == pytest.approx(
            candidate["price"] / reference_price("pet_500ml")
        )
    direct = evaluate_batch(
        [Scenario.model_validate(rows[0]["scenario"])], build_param_draws(k=200, seed=42)
    )[0]
    assert (
        rows[0]["result_hash"] == direct.result_hash
        and rows[0]["portfolio_gp"]["value"] == direct.portfolio_gp.value
    )


def test_ac031_provenance_chain_is_complete():
    research = run_research("Gabor-Granger", CONSUMERS)
    for row in research_to_scenarios(research, "Aurora"):
        chain = row["provenance"]
        assert (
            chain["research_id"] == research.research_id
            and chain["methodology"] == research.methodology
        )
        assert chain["source_data_hash"] == CONSUMERS["data_hash"] and chain["sample_size"] == 250
        assert chain["research_result_hash"] == research.result_hash
        assert (
            chain["scenario_id"] == row["scenario_id"]
            and chain["result_hash"] == row["result_hash"]
        )
        assert (
            chain["model_version"] == ENGINE_VERSION
            and chain["label"] == "SYNTHETIC CONSUMER EVIDENCE"
        )
        assert chain["research_assumption_ids"] and chain["engine_assumption_ids"]
        assert set(chain["research_assumption_ids"]).isdisjoint(chain["engine_assumption_ids"])
        assert chain["candidate"] in research.candidates


def test_ac032_unsupported_candidate_is_refused_not_clamped_and_gets_a_separate_alternative():
    research = replace(
        run_research("Willingness to Pay", CONSUMERS),
        candidates=[
            {
                "pack": "pet_500ml",
                "price": 70.0,
                "promotion_depth_pct": 0.0,
                "source_metric": "illustrative out-of-range candidate",
            }
        ],
    )
    (row,) = research_to_scenarios(research, "Aurora")
    assert row["status"] == "REFUSED" and row["portfolio_gp"] is None and not row["volume"]
    assert row["scenario"]["levers"]["Aurora-pet_500ml"]["price_index"] == pytest.approx(
        70 / 45
    )  # never clamped
    nearest = row["nearest_supported_scenario"]
    assert nearest["levers"]["Aurora-pet_500ml"]["price_index"] < 70 / 45
    assert row["refusal_reasons"]


def test_ac031_unobserved_packs_and_brands_are_rejected():
    research = run_research("Willingness to Pay", CONSUMERS)
    bad_pack = replace(research, candidates=[{**research.candidates[0], "pack": "magnum_3l"}])
    with pytest.raises(ValueError):
        research_to_scenarios(bad_pack, "Aurora")
    with pytest.raises(ValueError):
        research_to_scenarios(research, "Phantom")


def test_ac031_conjoint_candidates_carry_promotion_and_bridge_to_the_engine():
    result = conjoint_simulation(CONSUMERS, _alts())
    assert {c["brand"] for c in result.candidates} == {"Aurora"}
    rows = research_to_scenarios(result)
    promo = next(r for r in rows if r["provenance"]["candidate"]["promotion_depth_pct"] == 10)
    assert promo["scenario"]["levers"]["Aurora-pet_500ml"]["mechanic"] == "TPR"
