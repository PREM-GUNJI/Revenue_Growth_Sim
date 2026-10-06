"""AC-031/AC-032 at the API boundary: research candidates flow through the engine."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_ac031_research_endpoint_returns_candidates_with_provenance_and_engine_results():
    body = client.post("/pricing/research-to-scenarios",
                       json={"methodology": "Willingness to Pay", "pack": "pet_500ml"}).json()
    assert body["label"] == "SYNTHETIC CONSUMER EVIDENCE" and body["research"]["research_id"].startswith("RES-")
    for row in body["scenarios"]:
        assert row["provenance"]["research_id"] == body["research"]["research_id"]
        assert row["status"] in {"SUPPORTED", "EDGE", "REFUSED"} and row["result_hash"]


def test_ac032_refused_research_candidate_has_no_numbers_over_the_api():
    body = client.post("/pricing/research-to-scenarios",
                       json={"methodology": "Van Westendorp Price Sensitivity Meter", "pack": "pet_500ml"}).json()
    refused = [r for r in body["scenarios"] if r["status"] == "REFUSED"]
    assert refused and all(r["portfolio_gp"] is None and not r["volume"] for r in refused)
    assert all(r["nearest_supported_scenario"] for r in refused)


def test_ac030_conjoint_endpoint_states_supplied_utilities_and_rejects_unknown_levels():
    defaults = client.get("/pricing/conjoint/defaults").json()
    ok = client.post("/pricing/conjoint", json={"alternatives": defaults["default_alternatives"]}).json()
    assert abs(sum(ok["outputs"]["choice_share_pct"]) - 100) < 1e-6
    assert "does not estimate or fit consumer utilities" in ok["statement"]
    bad = client.post("/pricing/conjoint", json={"alternatives": [
        {"brand": "Aurora", "pack": "pet_500ml", "price": 45, "promotion": "50% off"}]})
    assert bad.status_code == 422
