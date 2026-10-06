"""Minimal ordered migration runner for the optional PostgreSQL database."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Column, DateTime, MetaData, String, Table, func, select
from sqlalchemy.engine import Connection, Engine

from backend.migrations import (
    v001_initial_scenario_runs,
    v002_users,
    v003_workspaces,
    v004_ai_usage_cached_tokens,
)

Migration = tuple[str, Callable[[Connection], None]]
metadata = MetaData()
migration_table = Table(
    "schema_migrations",
    metadata,
    Column("version", String(128), primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
MIGRATIONS: tuple[Migration, ...] = (
    ("001_initial_scenario_runs", v001_initial_scenario_runs.upgrade),
    ("002_users", v002_users.upgrade),
    ("003_workspaces", v003_workspaces.upgrade),
    ("004_ai_usage_cached_tokens", v004_ai_usage_cached_tokens.upgrade),
)


def upgrade_database(engine: Engine) -> list[str]:
    """Apply each unapplied migration inside a transaction."""
    with engine.begin() as connection:
        migration_table.create(connection, checkfirst=True)
        applied = set(connection.execute(select(migration_table.c.version)).scalars())
        newly_applied = []
        for version, upgrade in MIGRATIONS:
            if version in applied:
                continue
            upgrade(connection)
            connection.execute(migration_table.insert().values(version=version))
            newly_applied.append(version)
    return newly_applied
