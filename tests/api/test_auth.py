from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import auth, db
from backend.api.main import app

pytestmark = pytest.mark.real_auth

EMAIL, PASSWORD = "tester@example.com", "correct-horse-battery"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    db.Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "get_session_factory", lambda: sessionmaker(bind=engine, expire_on_commit=False))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key")
    auth._failures.clear()
    auth.upsert_user(EMAIL, PASSWORD, "Test User")
    return TestClient(app)


def login(client: TestClient, email: str = EMAIL, password: str = PASSWORD, remember: bool = False):
    return client.post("/auth/login", json={"email": email, "password": password, "remember_me": remember})


def test_api_requires_sign_in(client: TestClient) -> None:
    assert client.get("/assumptions").status_code == 401
    assert client.get("/auth/me").status_code == 401
    assert client.post("/scenarios/evaluate", json={}).status_code == 401


def test_health_endpoints_stay_public(client: TestClient) -> None:
    assert client.get("/healthz").status_code == 200


def test_login_sets_httponly_cookie_and_unlocks_api(client: TestClient) -> None:
    response = login(client)
    assert response.status_code == 200
    assert response.json()["user"] == {"email": EMAIL, "display_name": "Test User"}
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/auth/me").json()["user"]["email"] == EMAIL
    assert client.get("/assumptions").status_code == 200


def test_login_is_case_insensitive_on_email(client: TestClient) -> None:
    assert login(client, email="  TESTER@Example.com ").status_code == 200


def test_wrong_password_and_unknown_user_look_identical(client: TestClient) -> None:
    wrong = login(client, password="nope")
    unknown = login(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "set-cookie" not in wrong.headers


def test_lockout_after_repeated_failures(client: TestClient) -> None:
    for _ in range(auth.MAX_FAILURES):
        assert login(client, password="bad").status_code == 401
    assert login(client, password="bad").status_code == 429
    assert login(client).status_code == 429  # even the right password is blocked while locked


def test_logout_clears_session(client: TestClient) -> None:
    login(client)
    assert client.post("/auth/logout").status_code == 200
    client.cookies.clear()
    assert client.get("/assumptions").status_code == 401


def test_tampered_cookie_is_rejected(client: TestClient) -> None:
    login(client)
    client.cookies.set(auth.COOKIE_NAME, client.cookies[auth.COOKIE_NAME] + "x")
    assert client.get("/assumptions").status_code == 401


def test_deactivated_user_is_locked_out_immediately(client: TestClient) -> None:
    login(client)
    with db.get_session_factory()() as session:
        session.query(db.User).update({"is_active": False})
        session.commit()
    assert client.get("/assumptions").status_code == 401


def test_password_is_stored_only_as_argon2_hash(client: TestClient) -> None:
    with db.get_session_factory()() as session:
        stored = session.query(db.User).one().password_hash
    assert stored.startswith("$argon2") and PASSWORD not in stored


def test_upsert_resets_password(client: TestClient) -> None:
    assert auth.upsert_user(EMAIL, "new-password-1", "Test User") == "updated"
    assert login(client).status_code == 401
    assert login(client, password="new-password-1").status_code == 200


def test_sign_in_attempts_are_audited_without_secrets(client: TestClient) -> None:
    login(client, password="wrong")
    login(client)
    client.post("/auth/logout")
    with db.get_session_factory()() as session:
        rows = session.query(db.ActivityLog).order_by(db.ActivityLog.id).all()
    assert [(row.action, row.user_email) for row in rows] == [
        ("auth.login_failed", EMAIL), ("auth.login", EMAIL), ("auth.logout", EMAIL)]
    assert all(row.detail is None for row in rows)  # nothing but who and what: no password, no token
