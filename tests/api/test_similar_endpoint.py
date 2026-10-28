"""POST /scenarios/similar validation (DB optional)."""

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.assumptions.assumptions import SKU_IDS
from backend.engine.scenario import Lever, Scenario

client = TestClient(app)


def test_similar_requires_scenario_or_query():
    response = client.post("/scenarios/similar", json={"limit": 5})
    assert response.status_code == 422


def test_similar_without_database_is_503_or_ok():
    body = {
        "scenario": Scenario(
            name="sim", levers={SKU_IDS[0]: Lever(price_index=1.0)}
        ).model_dump(mode="json"),
        "limit": 5,
    }
    response = client.post("/scenarios/similar", json=body)
    # Without DATABASE_URL the endpoint reports 503; with pgvector it returns a list.
    assert response.status_code in {200, 503}
    if response.status_code == 200:
        assert isinstance(response.json(), list)
