"""AC-028..AC-030: synthetic consumer evidence and the non-estimating research methods."""

from __future__ import annotations

import re

import numpy as np
import pytest

from backend.assumptions.assumptions import ASSUMPTIONS, FORMATS
from backend.research.evidence import (
    METHODOLOGIES,
    ResearchResult,
    generate_consumers,
    run_research,
    summarize_consumers,
)

ALLOWED_FIELDS = {
    "respondent_id",
    "segment",
    "age_band",
    "region",
    "current_brand",
    "current_pack",
    "current_price",
    "purchase_frequency",
    "price_sensitivity",
    "promotion_sensitivity",
    "pack_preference",
    "willingness_to_pay",
    "vw_too_cheap",
    "vw_cheap",
    "vw_expensive",
    "vw_too_expensive",
    "comment",
}


def _evidence(wtp: list[float], pack: str = "pet_500ml") -> dict:
    rows = [
        {
            "respondent_id": f"SYN-{i:05d}",
            "current_pack": pack,
            "willingness_to_pay": float(v),
            "vw_too_cheap": v * 0.7,
            "vw_cheap": v * 0.85,
            "vw_expensive": v * 1.1,
            "vw_too_expensive": v * 1.3,
        }
        for i, v in enumerate(wtp)
    ]
    return {"respondents": rows, "data_hash": "h" * 64, "label": "SYNTHETIC CONSUMER EVIDENCE"}


def test_ac028_consumer_generation_is_deterministic_and_hash_reproducible():
    a, b = generate_consumers(7, 120), generate_consumers(7, 120)
    assert a == b and a["data_hash"] == b["data_hash"]
    assert generate_consumers(8, 120)["data_hash"] != a["data_hash"]
    assert a["label"] == "SYNTHETIC CONSUMER EVIDENCE"


def test_ac028_consumers_carry_no_pii_and_only_documented_fields():
    rows = generate_consumers(42, 200)["respondents"]
    assert all(set(row) == ALLOWED_FIELDS for row in rows)
    assert all(re.fullmatch(r"SYN-\d{5}", row["respondent_id"]) for row in rows)
    text = " ".join(row["comment"] for row in rows)
    assert not re.search(r"@|\+?\d{10}|https?://", text)


def test_ac028_consumer_values_are_in_valid_ranges_and_comments_match_attributes():
    rows = generate_consumers(42, 400)["respondents"]
    for row in rows:
        assert 0 <= row["price_sensitivity"] <= 1 and 0 <= row["promotion_sensitivity"] <= 1
        assert row["current_pack"] in FORMATS and row["willingness_to_pay"] > 0
        assert (
            row["vw_too_cheap"] <= row["vw_cheap"] <= row["vw_expensive"] <= row["vw_too_expensive"]
        )
        if row["segment"] == "deal_responsive":
            assert "promotion" in row["comment"]
        if "small price increase" in row["comment"]:
            assert row["price_sensitivity"] < 0.35


def test_ac028_sample_size_comes_from_the_registry_and_is_bounded():
    assert generate_consumers()["sample_size"] == ASSUMPTIONS["A-026"].value
    with pytest.raises(ValueError):
        generate_consumers(1, 0)


def test_ac028_agent_summary_has_no_respondent_rows_and_labels_comments_as_qualitative():
    summary = summarize_consumers(generate_consumers(42, 100), comment_sample=3)
    assert "respondents" not in summary and len(summary["sample_comments"]) == 3
    assert (
        summary["label"] == "SYNTHETIC CONSUMER EVIDENCE"
        and "not demand observations" in summary["note"]
    )


@pytest.mark.parametrize("method", METHODOLOGIES)
def test_ac029_research_is_deterministic_and_fully_described(method):
    evidence = generate_consumers(42, 250)
    a, b = run_research(method, evidence), run_research(method, evidence)
    assert isinstance(a, ResearchResult) and a == b
    assert a.research_id == "RES-" + a.result_hash[:12].upper()
    assert (
        a.methodology == method
        and a.sample_size == 250
        and a.source_data_hash == evidence["data_hash"]
    )
    assert a.inputs and a.outputs and a.candidates and a.assumptions and a.limitations
    assert set(a.assumption_ids) <= set(ASSUMPTIONS)
    assert all(c["price"] > 0 and c["pack"] == "pet_500ml" for c in a.candidates)


def test_ac029_wtp_known_example():
    result = run_research("Willingness to Pay", _evidence([40, 42, 44, 46, 48]))
    assert (
        result.outputs["p25"] == 42.0
        and result.outputs["p50"] == 44.0
        and result.outputs["p75"] == 46.0
    )
    assert [c["source_metric"] for c in result.candidates] == ["P25 WTP", "P50 WTP", "P75 WTP"]


def test_ac029_gabor_granger_known_example():
    result = run_research("Gabor-Granger", _evidence([40, 42, 44, 46, 48]), prices=[40, 44, 48])
    assert result.outputs["acceptance_share_by_price"] == {"40.0": 1.0, "44.0": 0.6, "48.0": 0.2}
    assert result.outputs["revenue_index_maximum_price"] == 40.0
    assert {c["price"] for c in result.candidates} == {40.0, 44.0}


def test_ac029_van_westendorp_points_are_ordered():
    out = run_research(
        "Van Westendorp Price Sensitivity Meter", generate_consumers(42, 250)
    ).outputs
    assert out["pmc"] < out["opp"] < out["ipp"] < out["pme"]


def test_ac029_research_is_scoped_to_observed_packs_and_known_methods():
    evidence = generate_consumers(42, 250)
    with pytest.raises(ValueError):
        run_research("Willingness to Pay", evidence, pack="magnum_3l")
    with pytest.raises(ValueError):
        run_research("Conjoint estimation", evidence)


def test_ac030_research_module_contains_no_fitting_or_ml_imports():
    import backend.research.evidence as module

    source = open(module.__file__, encoding="utf-8").read()
    assert not re.search(
        r"^\s*(import|from)\s+(sklearn|scipy|statsmodels|torch|tensorflow|xgboost)", source, re.M
    )
    assert not np.isnan(
        run_research("Willingness to Pay", generate_consumers(1, 100)).outputs["mean"]
    )
