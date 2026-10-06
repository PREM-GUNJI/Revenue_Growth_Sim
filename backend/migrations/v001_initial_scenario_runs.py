"""Create persistent scenario-run history."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from backend.db import ScenarioRun


def upgrade(connection: Connection) -> None:
    ScenarioRun.__table__.create(connection, checkfirst=True)
