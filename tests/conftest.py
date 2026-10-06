"""Shared fixtures. Existing API tests exercise the engine, not sign-in, so they run
as an authenticated user; tests marked `real_auth` keep the real session check."""

from __future__ import annotations

import pytest

from backend import db
from backend.api.main import app
from backend.auth import current_user, require_user


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "real_auth: run with the real session check (no auth override)")


@pytest.fixture(autouse=True)
def _signed_in(request: pytest.FixtureRequest):
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    app.dependency_overrides[require_user] = lambda: None
    app.dependency_overrides[current_user] = lambda: db.User(
        id="test-user", email="test@example.com", display_name="Test User", password_hash="x", is_active=True)
    yield
    app.dependency_overrides.pop(require_user, None)
    app.dependency_overrides.pop(current_user, None)
