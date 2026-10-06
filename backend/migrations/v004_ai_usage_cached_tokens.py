"""Record cached input tokens separately, so cost can use the cheaper cached rate."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection


def upgrade(connection: Connection) -> None:
    # Databases that ran migration 003 before this column existed need it; fresh ones already have it.
    columns = {column["name"] for column in inspect(connection).get_columns("ai_usage")}
    if "cached_input_tokens" not in columns:
        connection.exec_driver_sql("ALTER TABLE ai_usage ADD COLUMN cached_input_tokens INTEGER NOT NULL DEFAULT 0")
