"""Market packs and registry overlays."""

from __future__ import annotations

from backend.assumptions import registry
from backend.markets import list_markets, load_market, use_market


def test_three_shipping_markets_load():
    markets = {m.id: m for m in list_markets()}
    assert list(markets)[:1] == ["in"]
    assert set(markets) == {"in", "us", "eu"}
    assert markets["in"].currency.code == "INR"
    assert markets["us"].currency.code == "USD"
    assert markets["eu"].currency.code == "EUR"


def test_india_overlay_leaves_base_values_unchanged():
    base = registry.get("A-028").value
    with use_market(load_market("in")):
        assert registry.get("A-028").value == base
        assert registry.get("A-028").unit == "INR"


def test_us_overlay_changes_money_and_unit():
    with use_market(load_market("us")):
        price = registry.get("A-028")
        assert price.value == 1.49
        assert price.unit == "USD"
        assert "USD" in price.label
        assert registry.get("A-013").value == 0.12
        assert registry.get("A-001").value == -2.1


def test_eu_overlay_is_independent_of_us():
    with use_market(load_market("us")):
        assert registry.get("A-028").value == 1.49
    with use_market(load_market("eu")):
        assert registry.get("A-028").value == 1.29
        assert registry.get("A-028").unit == "EUR"
    assert registry.get("A-028").value == 40.0
