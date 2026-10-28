"""Give every user a role (viewer, analyst or admin). Existing users become analysts, which is today's access."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection


def upgrade(connection: Connection) -> None:
    # Fresh databases create `users` from the current model in migration 002 and already have the column.
    columns = {column["name"] for column in inspect(connection).get_columns("users")}
    if "role" not in columns:
        connection.exec_driver_sql("ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'analyst'")
