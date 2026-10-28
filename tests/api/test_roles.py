"""Roles are enforced on the server: viewers are read-only, only admins see governance (ADR-017)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import auth, db
from backend.api.main import app
from backend.migrations.runner import upgrade_database

pytestmark = pytest.mark.real_auth

PASSWORD = "correct-horse-battery"
BASELINE = {"schema_version": 1, "name": "Baseline", "levers": {},
            "cost_shock": {"aluminium_pct": 0, "pet_resin_pct": 0, "sugar_pct": 0}}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    db.Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "get_session_factory", lambda: sessionmaker(bind=engine, expire_on_commit=False))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key")
    auth._failures.clear()
    for role in auth.ROLES:
        auth.upsert_user(f"{role}@example.com", PASSWORD, role.title(), role)
    return TestClient(app)


def sign_in(client: TestClient, role: str) -> None:
    client.cookies.clear()
    assert client.post("/auth/login", json={"email": f"{role}@example.com", "password": PASSWORD}).status_code == 200


def make_case(client: TestClient) -> str:
    sign_in(client, "analyst")
    response = client.post("/workspaces", json={"name": "Roles case", "description": "", "scenarios": [BASELINE]})
    assert response.status_code == 201
    return response.json()["id"]


def test_me_reports_the_role(client: TestClient) -> None:
    for role in auth.ROLES:
        sign_in(client, role)
        assert client.get("/auth/me").json()["user"]["role"] == role


def test_viewer_can_read_evaluate_and_export_but_not_write(client: TestClient) -> None:
    case = make_case(client)
    sign_in(client, "viewer")
    assert client.get("/workspaces").status_code == 200
    assert client.get(f"/workspaces/{case}").status_code == 200
    assert client.get(f"/workspaces/{case}/scenarios").status_code == 200
    assert client.post("/scenarios/evaluate", json={"scenarios": [BASELINE], "k": 0, "seed": 42}).status_code == 200
    assert client.post(f"/workspaces/{case}/export").status_code == 200
    assert client.post(f"/workspaces/{case}/brief").status_code == 200

    assert client.post("/workspaces", json={"name": "No", "description": "", "scenarios": [BASELINE]}).status_code == 403
    assert client.patch(f"/workspaces/{case}", json={"name": "Renamed"}).status_code == 403
    assert client.put(f"/workspaces/{case}/scenarios", json={"scenarios": [BASELINE], "version": 1}).status_code == 403
    assert client.post("/agent/run", json={"goal": "Find a winner"}).status_code == 403
    assert client.post("/pricing/research", json={"methodology": "Willingness to Pay", "pack": "can_330ml"}).status_code == 403
    assert client.post("/pricing/personas/design", json={"brief": "students"}).status_code == 403


def test_analyst_writes_but_cannot_see_governance(client: TestClient) -> None:
    case = make_case(client)
    assert client.put(f"/workspaces/{case}/scenarios", json={"scenarios": [BASELINE], "version": 1}).status_code == 200
    for path in ("/audit/log", "/audit/ai-usage", "/agent/runs", "/agent/runs/" + "0" * 32):
        assert client.get(path).status_code == 403, path


def test_admin_sees_governance(client: TestClient) -> None:
    sign_in(client, "admin")
    for path in ("/audit/log", "/audit/ai-usage", "/agent/runs"):
        assert client.get(path).status_code == 200, path


def test_upsert_keeps_role_unless_told_and_rejects_unknown_roles(client: TestClient) -> None:
    auth.upsert_user("viewer@example.com", "new-password-1", "Viewer")
    with db.get_session_factory()() as session:
        assert session.query(db.User).filter_by(email="viewer@example.com").one().role == "viewer"
    with pytest.raises(ValueError):
        auth.upsert_user("x@example.com", PASSWORD, "X", "owner")


def test_migration_005_adds_role_to_an_existing_users_table() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(64) PRIMARY KEY, email VARCHAR(320), display_name VARCHAR(200), "
                                "password_hash VARCHAR(255), is_active BOOLEAN, created_at TIMESTAMP)"))
        connection.execute(text("INSERT INTO users VALUES ('u1', 'old@example.com', 'Old', 'x', 1, CURRENT_TIMESTAMP)"))
    upgrade_database(engine)
    assert "role" in {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT role FROM users WHERE id = 'u1'")).scalar_one() == "analyst"
