"""AC-005: GET /assumptions lists the full registry."""

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.assumptions.assumptions import ASSUMPTIONS, SKU_IDS
from backend.engine.scenario import Lever, Scenario

client = TestClient(app)


def test_list_assumptions_returns_every_registered_id():
    resp = client.get("/assumptions")
    assert resp.status_code == 200
    body = resp.json()
    assert {a["id"] for a in body} == set(ASSUMPTIONS.keys())


def test_list_assumptions_every_entry_has_a_rationale():
    resp = client.get("/assumptions")
    for a in resp.json():
        assert a["rationale"]


def test_model_info_and_envelope_are_exposed():
    assert client.get("/model/info").json()["deterministic"] is True
    envelope = client.get("/envelope").json()
    assert set(envelope["price_index_p1_p99"]) == set(SKU_IDS)
    assert envelope["minimum_local_rows"] >= 1


def test_evaluate_and_nearest_supported_endpoints():
    base = Scenario()
    evaluated = client.post("/scenarios/evaluate", json={
        "scenarios": [base.model_dump(mode="json")], "k": 0, "seed": 8
    })
    assert evaluated.status_code == 200
    assert evaluated.json()[0]["status"] in {"SUPPORTED", "EDGE"}

    refused = Scenario(levers={SKU_IDS[0]: Lever(price_index=1.5)})
    nearest = client.post("/scenarios/nearest_supported", json={
        "scenario": refused.model_dump(mode="json")
    })
    assert nearest.status_code == 200
    assert nearest.json()["status"] in {"SUPPORTED", "EDGE"}
