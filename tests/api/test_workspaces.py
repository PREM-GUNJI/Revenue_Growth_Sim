from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import db
from backend.api.main import app

SCENARIO = {"schema_version": 1, "name": "Baseline", "levers": {}, "cost_shock": {}}


@pytest.fixture()
def factory(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    db.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db, "get_session_factory", lambda: session_factory)
    return session_factory


@pytest.fixture()
def client(factory) -> TestClient:  # noqa: ARG001 - factory patches the database for the app
    return TestClient(app)


def create(client: TestClient, name: str = "Pricing review", **extra):
    return client.post("/workspaces", json={"name": name, **extra})


def actions(factory) -> list[str]:
    with factory() as session:
        return list(session.scalars(select(db.ActivityLog.action).order_by(db.ActivityLog.id)))


def test_create_list_and_get(client: TestClient) -> None:
    created = create(client, description="  Q3 pack-price work  ", scenarios=[SCENARIO]).json()
    assert created["name"] == "Pricing review" and created["description"] == "Q3 pack-price work"
    assert created["created_by"] == created["updated_by"] == "test@example.com"
    assert created["scenario_count"] == 1 and created["archived"] is False
    assert [w["id"] for w in client.get("/workspaces").json()] == [created["id"]]
    assert client.get(f"/workspaces/{created['id']}").json()["name"] == "Pricing review"


@pytest.mark.parametrize("payload", [{"name": ""}, {"name": "   "}, {"name": "x" * 121},
                                     {"name": "ok", "scenarios": [{"name": 5, "levers": {}}]},
                                     {"name": "ok", "scenarios": [{"name": "a"}]}])
def test_create_rejects_bad_input(client: TestClient, payload) -> None:
    assert client.post("/workspaces", json=payload).status_code == 422


def test_unknown_workspace_is_404(client: TestClient) -> None:
    assert client.get("/workspaces/nope").status_code == 404
    assert client.get("/workspaces/nope/scenarios").status_code == 404
    assert client.patch("/workspaces/nope", json={"name": "x"}).status_code == 404


def test_scenarios_roundtrip_and_version_bump(client: TestClient) -> None:
    wid = create(client).json()["id"]
    assert client.get(f"/workspaces/{wid}/scenarios").json() == {"scenarios": None, "version": 1}
    saved = client.put(f"/workspaces/{wid}/scenarios", json={"scenarios": [SCENARIO, {**SCENARIO, "name": "B"}], "version": 1})
    assert saved.json() == {"version": 2, "scenario_count": 2}
    loaded = client.get(f"/workspaces/{wid}/scenarios").json()
    assert loaded["version"] == 2 and [s["name"] for s in loaded["scenarios"]] == ["Baseline", "B"]


def test_stale_version_is_rejected_not_overwritten(client: TestClient) -> None:
    wid = create(client, scenarios=[SCENARIO]).json()["id"]
    assert client.put(f"/workspaces/{wid}/scenarios", json={"scenarios": [SCENARIO], "version": 1}).status_code == 200
    stale = client.put(f"/workspaces/{wid}/scenarios", json={"scenarios": [{**SCENARIO, "name": "lost"}], "version": 1})
    assert stale.status_code == 409 and "reload" in stale.json()["detail"]
    assert client.get(f"/workspaces/{wid}/scenarios").json()["scenarios"][0]["name"] == "Baseline"


def test_too_many_scenarios_rejected(client: TestClient) -> None:
    wid = create(client).json()["id"]
    body = {"scenarios": [SCENARIO] * 201, "version": 1}
    assert client.put(f"/workspaces/{wid}/scenarios", json=body).status_code == 422


def test_rename_archive_and_restore(client: TestClient) -> None:
    wid = create(client).json()["id"]
    assert client.patch(f"/workspaces/{wid}", json={"name": "  Renamed "}).json()["name"] == "Renamed"
    assert client.patch(f"/workspaces/{wid}", json={"name": "  "}).status_code == 422
    assert client.patch(f"/workspaces/{wid}", json={"archived": True}).json()["archived"] is True
    assert client.get("/workspaces").json() == []
    assert [w["id"] for w in client.get("/workspaces?include_archived=true").json()] == [wid]
    blocked = client.put(f"/workspaces/{wid}/scenarios", json={"scenarios": [SCENARIO], "version": 1})
    assert blocked.status_code == 409 and "archived" in blocked.json()["detail"]
    client.patch(f"/workspaces/{wid}", json={"archived": False})
    assert client.put(f"/workspaces/{wid}/scenarios", json={"scenarios": [SCENARIO], "version": 1}).status_code == 200


def test_audit_rows_are_written_and_autosaves_coalesce(client: TestClient, factory) -> None:
    wid = create(client).json()["id"]
    for version in (1, 2, 3):
        client.put(f"/workspaces/{wid}/scenarios", json={"scenarios": [SCENARIO], "version": version})
    client.patch(f"/workspaces/{wid}", json={"name": "Renamed"})
    client.patch(f"/workspaces/{wid}", json={"archived": True})
    assert actions(factory) == ["workspace.create", "workspace.edit", "workspace.update", "workspace.archive"]
    with factory() as session:
        row = session.scalar(select(db.ActivityLog).where(db.ActivityLog.action == "workspace.create"))
        assert row.user_email == "test@example.com" and row.workspace_id == wid and row.detail == {"name": "Pricing review"}


@pytest.mark.real_auth
def test_every_workspace_route_requires_sign_in(factory) -> None:  # noqa: ARG001
    anon = TestClient(app)
    calls = [anon.get("/workspaces"), anon.post("/workspaces", json={"name": "x"}), anon.get("/workspaces/a"),
             anon.patch("/workspaces/a", json={"name": "x"}), anon.get("/workspaces/a/scenarios"),
             anon.put("/workspaces/a/scenarios", json={"scenarios": [], "version": 1})]
    assert [call.status_code for call in calls] == [401] * 6
