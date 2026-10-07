"""Assumption-documentation coverage: every registered assumption states a rationale and where a
reader can check it (or says plainly that no external source exists), and the engine's money scale
matches the INR reference prices the pricing-research layer uses."""

from __future__ import annotations

import pytest

from backend.assumptions.assumptions import (
    ASSUMPTIONS,
    CURRENCY_CODE,
    REFERENCE_PRICE_BY_FORMAT,
    SKUS,
)
from backend.engine.batch import _baseline


@pytest.mark.parametrize("aid", sorted(ASSUMPTIONS))
def test_every_assumption_has_rationale_and_reference(aid: str) -> None:
    a = ASSUMPTIONS[aid]
    assert a.rationale.strip(), f"{aid} has no rationale"
    assert a.reference and a.reference.strip(), f"{aid} has no reference or no-source statement"


def test_references_never_claim_a_fit() -> None:
    for aid, a in ASSUMPTIONS.items():
        text = (a.reference or "").lower()
        assert "fitted from" not in text and "estimated from our data" not in text, aid


def test_money_assumptions_are_labelled_in_the_app_currency() -> None:
    for a in ASSUMPTIONS.values():
        if a.unit and ("/L" in a.unit or "/unit" in a.unit):
            assert a.unit.startswith(CURRENCY_CODE), f"{a.id} unit {a.unit!r} is not in {CURRENCY_CODE}"


def test_engine_reference_price_matches_the_inr_reference_price_of_the_focal_brand() -> None:
    """Regression for the '$ in the engine, INR in the UI' mismatch: Aurora's baseline price in the
    engine equals the reference shelf price (A-028..A-031) the evidence layer converts against."""
    baseline = _baseline()
    for sku in SKUS:
        if sku["brand"] != "Aurora":
            continue
        engine_price = baseline.reference_price[sku["sku_id"]]
        registry_price = REFERENCE_PRICE_BY_FORMAT[sku["format"]].value
        assert engine_price == pytest.approx(registry_price, rel=1e-3), sku["sku_id"]
