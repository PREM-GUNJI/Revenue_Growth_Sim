"""Lock each workspace to a market pack (currency and synthetic data)."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection


def upgrade(connection: Connection) -> None:
    columns = {column["name"] for column in inspect(connection).get_columns("workspaces")}
    if "market_id" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE workspaces ADD COLUMN market_id VARCHAR(16) NOT NULL DEFAULT 'in'"
        )
