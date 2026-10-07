"""The deck shows the same Aurora-only rupee figures as the app, and nothing for a refused scenario."""

from __future__ import annotations

import pytest

from backend.export import _inr, evaluate, summary_rows

CAN, BOTTLE = "Aurora-can_330ml", "Aurora-bottle_1500ml"


def scenario(name: str, levers: dict | None = None) -> dict:
    return {"schema_version": 1, "name": name, "levers": levers or {},
            "cost_shock": {"aluminium_pct": 0, "pet_resin_pct": 0, "sugar_pct": 0}}


def lever(price: float) -> dict:
    return {"price_index": price, "promo_depth_pct": 0, "mechanic": "none", "promo_weeks_per_month": 0}


@pytest.mark.parametrize(("value", "expected"), [
    (235585.7, "₹2,35,586"), (999, "₹999"), (1000, "₹1,000"), (123456789, "₹12,34,56,789"), (0, "₹0"), (-1548.4, "-₹1,548"), (None, "n/a"),
])
def test_rupees_use_indian_grouping(value: float | None, expected: str) -> None:
    assert _inr(value) == expected


def test_signed_rupees_show_an_explicit_sign() -> None:
    assert _inr(10440.2, signed=True) == "+₹10,440" and _inr(-1548.4, signed=True) == "-₹1,548" and _inr(0.2, signed=True) == "₹0"


def test_summary_rows_are_focal_brand_figures_and_refused_has_none() -> None:
    scenarios, results = evaluate([scenario("Baseline"), scenario("Bottle +3%", {BOTTLE: lever(1.03)}),
                                   scenario("Far", {CAN: lever(1.9)})])
    base, moved, refused = summary_rows(scenarios, results)
    assert base["gp"] == pytest.approx(results[0]["focal"]["gp"]["value"])
    assert moved["gp"] == pytest.approx(results[1]["focal"]["gp"]["value"])
    assert moved["gp_change"] == pytest.approx(moved["gp"] - base["gp"])
    assert moved["gp_pct"] == pytest.approx((moved["gp"] / base["gp"] - 1) * 100)
    assert moved["gp"] < results[1]["portfolio_gp"]["value"]  # not the all-brand total
    assert refused["status"] == "REFUSED"
    assert all(refused[key] is None for key in ("units", "revenue", "gp", "gp_change", "volume_pct", "revenue_pct", "gp_pct"))
