from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import db, hub
from backend.api.main import app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db, "get_session_factory", lambda: factory)
    monkeypatch.setattr(db, "database_status", lambda: "ok")
    return TestClient(app)


def test_summary_shape_and_workspace_counts(client: TestClient) -> None:
    client.post("/workspaces", json={"name": "A"})
    archived = client.post("/workspaces", json={"name": "B"}).json()["id"]
    client.patch(f"/workspaces/{archived}", json={"archived": True})
    body = client.get("/hub/summary").json()
    assert body["database"] == "ok" and body["workspaces"] == {"active": 1, "archived": 1}
    assert body["governance"]["assumptions"] > 0 and body["governance"]["adrs"] >= 14


def test_agent_eval_gate_matches_the_committed_report() -> None:
    result = hub.agent_evals()
    assert result is not None and result["tasks"] == 43
    # The report in the repo passes its own gate (agent_evals/run_evals.py); the hub must agree.
    assert result["passed"] is True and all(result["checks"].values())


def test_agent_eval_gate_fails_when_a_rate_misses_budget(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = json.loads(hub.EVALS_FILE.read_text(encoding="utf-8"))
    report["metrics"]["grounding_rate"] = 0.9
    fake = tmp_path / "agent_evals.json"
    fake.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(hub, "EVALS_FILE", fake)
    result = hub.agent_evals()
    assert result["passed"] is False and result["checks"]["grounding_rate"] is False


def test_benchmark_rows_are_reported_as_they_are() -> None:
    bench = hub.benchmarks()
    assert bench is not None and bench["total"] == len(bench["rows"]) >= 4
    assert bench["within_budget"] == sum(row["result"] == "PASS" for row in bench["rows"])  # failures are not hidden


@pytest.mark.real_auth
def test_summary_requires_sign_in() -> None:
    assert TestClient(app).get("/hub/summary").status_code == 401
