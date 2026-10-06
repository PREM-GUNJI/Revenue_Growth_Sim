"""Create the users table used for sign-in (password hashes only)."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from backend.db import User


def upgrade(connection: Connection) -> None:
    User.__table__.create(connection, checkfirst=True)
