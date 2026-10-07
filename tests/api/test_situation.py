from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.assumptions.assumptions import ASSUMPTIONS, FOCAL_BRAND
from backend.situation import build_situation

client = TestClient(app)
CAN = "Aurora-can_330ml"


def lever(price: float = 1.0) -> dict:
    return {"price_index": price, "promo_depth_pct": 0, "mechanic": "none", "promo_weeks_per_month": 0}


def scenario(name: str, levers: dict | None = None) -> dict:
    return {"schema_version": 1, "name": name, "levers": levers or {}, "cost_shock": {"aluminium_pct": 0, "pet_resin_pct": 0, "sugar_pct": 0}}


# ---- /situation ------------------------------------------------------------------------------

def test_situation_is_deterministic_and_in_inr() -> None:
    first = client.get("/situation").json()
    assert first == client.get("/situation").json() == build_situation()
    assert first["currency"] == "INR" and first["focal_brand"] == FOCAL_BRAND
    assert {"Observed", "Modeled", "Assumed"} <= set(first["labels"].values())


def test_baseline_totals_add_up_and_exclude_competitors_from_the_focal_view() -> None:
    s = client.get("/situation").json()
    focal = [r for r in s["skus"] if r["is_focal"]]
    assert len(s["skus"]) == 20 and len(focal) == 4 and all(r["brand"] == FOCAL_BRAND for r in focal)
    assert s["totals"]["focal"]["gp"] == pytest.approx(sum(r["baseline_gp"] for r in focal))
    assert s["totals"]["market"]["gp"] == pytest.approx(sum(r["baseline_gp"] for r in s["skus"]))
    assert s["totals"]["market"]["gp"] > s["totals"]["focal"]["gp"]
    assert 0 < s["totals"]["focal_value_share_pct"] < 100
    for r in s["skus"]:  # the P&L walks down exactly: revenue - trade = net sales; net sales - costs = profit
        assert r["baseline_gsv"] - r["baseline_trade"] == pytest.approx(r["baseline_nsv"])
        assert r["baseline_nsv"] - r["baseline_cogs"] == pytest.approx(r["baseline_gp"])
        assert r["price_per_litre"] == pytest.approx(r["price"] / r["pack_size_l"])


def test_focal_prices_are_the_inr_reference_prices_and_gaps_are_against_competitors() -> None:
    s = client.get("/situation").json()
    by_sku = {r["sku_id"]: r for r in s["skus"]}
    assert by_sku[CAN]["price"] == pytest.approx(ASSUMPTIONS["A-028"].value, rel=1e-3)
    gaps = by_sku[CAN]["price_gap_vs_competitors_pct"]
    assert set(gaps) == {"Boreal", "Comet", "Delta", "Ember"}
    assert gaps["Boreal"] == pytest.approx((by_sku[CAN]["price"] / by_sku["Boreal-can_330ml"]["price"] - 1) * 100)
    assert by_sku["Boreal-can_330ml"]["price_gap_vs_competitors_pct"] is None  # competitor rows carry no gap


def test_probes_are_engine_scenarios_compared_with_the_baseline() -> None:
    s = client.get("/situation").json()
    can = next(r for r in s["skus"] if r["sku_id"] == CAN)
    probe = can["price_probe"]
    assert probe["status"] != "REFUSED"
    direct = client.post("/scenarios/evaluate", json={"scenarios": [scenario("base"), scenario("up", {CAN: lever(1.03)})], "k": 200, "seed": 42}).json()
    assert probe["scenario_id"] == direct[1]["scenario_id"]
    assert probe["focal_gp_change"] == pytest.approx(direct[1]["focal"]["gp"]["value"] - direct[0]["focal"]["gp"]["value"])
    assert can["promo_probe"]["focal_volume_pct"] > 0  # a promotion lifts volume
    assert s["cost_shock_probe"]["focal_gp_change"] < 0  # higher input costs reduce profit


# ---- evaluate and sweep carry the explanations -------------------------------------------------

def test_evaluate_returns_focal_totals_assumption_ids_and_an_exact_bridge() -> None:
    body = {"scenarios": [scenario("base"), scenario("up", {CAN: lever(1.04)})], "k": 50, "seed": 42}
    base, up = client.post("/scenarios/evaluate", json=body).json()
    assert set(up["focal"]) == {"volume", "gsv", "nsv", "gp"}
    assert set(up["focal"]["gp"]) == {"value", "p10", "p50", "p90"}
    assert "A-001" in up["assumption_ids"] and "A-001" not in base["assumption_ids"]  # own elasticity only once the price moves
    bridge = up["focal_bridge"]
    parts = ("price_cents", "volume_cents", "cross_pack_cents", "promo_cents", "trade_cents", "cogs_cents")
    assert sum(bridge[p] for p in parts) == bridge["total_cents"]  # integers, so the walk is exact
    assert bridge["total_cents"] == round((up["focal"]["gp"]["value"] - base["focal"]["gp"]["value"]) * 100)


def test_a_refused_scenario_has_no_focal_numbers_or_bridge() -> None:
    body = {"scenarios": [scenario("far", {CAN: lever(1.9)})], "k": 20, "seed": 42}
    result = client.post("/scenarios/evaluate", json=body).json()[0]
    assert result["status"] == "REFUSED" and result["focal"] == {} and result["focal_bridge"] is None
    assert result["assumption_ids"]  # still says which assumptions the refusal rests on


def test_evaluate_reports_server_side_engine_time_in_a_header() -> None:
    response = client.post("/scenarios/evaluate", json={"scenarios": [scenario("base")], "k": 20, "seed": 42})
    assert response.status_code == 200
    assert float(response.headers["X-Engine-Ms"]) >= 0  # lets the page show compute time apart from the round trip


def test_sweep_results_also_carry_explanations() -> None:
    body = {"scenario": scenario("s"), "sku_id": CAN, "lever": "price_index", "values": [0.98, 1.02], "k": 0, "seed": 42}
    rows = client.post("/scenarios/sweep", json=body).json()
    assert len(rows) == 2 and all(r["focal"] and r["assumption_ids"] for r in rows)


@pytest.mark.real_auth
def test_situation_requires_sign_in() -> None:
    assert TestClient(app).get("/situation").status_code == 401
