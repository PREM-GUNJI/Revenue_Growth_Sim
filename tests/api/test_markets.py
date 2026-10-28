"""Market packs on workspaces and situation currency (ADR-018)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import db
from backend.api.main import app

client = TestClient(app)


@pytest.fixture()
def factory(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    db.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db, "get_session_factory", lambda: session_factory)
    return session_factory


def test_list_markets() -> None:
    response = client.get("/markets")
    assert response.status_code == 200
    ids = [m["id"] for m in response.json()]
    assert ids[0] == "in"
    assert set(ids) == {"in", "us", "eu"}
    codes = {m["id"]: m["currency"]["code"] for m in response.json()}
    assert codes == {"in": "INR", "us": "USD", "eu": "EUR"}


def test_situation_us_returns_usd() -> None:
    response = client.get("/situation?market=us")
    assert response.status_code == 200
    body = response.json()
    assert body["market_id"] == "us"
    assert body["currency"]["code"] == "USD"
    can = next(s for s in body["skus"] if s["format"] == "can_330ml" and s["is_focal"])
    assert abs(can["price"] - 1.49) < 0.01


def test_workspace_locks_market(factory) -> None:  # noqa: ARG001
    created = client.post("/workspaces", json={"name": "US case", "market_id": "us", "description": "Take price?"})
    assert created.status_code == 201
    body = created.json()
    assert body["market_id"] == "us"
    assert body["currency"]["code"] == "USD"
    patched = client.patch(f"/workspaces/{body['id']}", json={"market_id": "eu"})
    assert patched.status_code == 422
    again = client.get(f"/workspaces/{body['id']}")
    assert again.json()["market_id"] == "us"


def test_evaluate_respects_market_query() -> None:
    scenario = {
        "schema_version": 1,
        "name": "Baseline",
        "levers": {},
        "cost_shock": {"aluminium_pct": 0, "pet_resin_pct": 0, "sugar_pct": 0},
    }
    india = client.post("/scenarios/evaluate?market=in", json={"scenarios": [scenario], "k": 0, "seed": 42})
    us = client.post("/scenarios/evaluate?market=us", json={"scenarios": [scenario], "k": 0, "seed": 42})
    assert india.status_code == 200 and us.status_code == 200
    gp_in = india.json()[0]["focal"]["gp"]["value"]
    gp_us = us.json()[0]["focal"]["gp"]["value"]
    assert gp_in > gp_us * 5  # INR weekly GP is a larger absolute number than USD
