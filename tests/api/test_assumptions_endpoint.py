"""AC-005: GET /assumptions lists the full registry."""

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.assumptions.assumptions import ASSUMPTIONS

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
