"""Workspaces, their autosaved scenario state, the audit log and AI usage; tag saved runs with a workspace."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from backend.db import ActivityLog, AiUsage, Workspace, WorkspaceState


def upgrade(connection: Connection) -> None:
    for model in (Workspace, WorkspaceState, ActivityLog, AiUsage):
        model.__table__.create(connection, checkfirst=True)
    # Databases created by migration 001 before this column existed need it added; fresh ones already have it.
    columns = {column["name"] for column in inspect(connection).get_columns("scenario_runs")}
    if "workspace_id" not in columns:
        connection.exec_driver_sql("ALTER TABLE scenario_runs ADD COLUMN workspace_id VARCHAR(64)")
        connection.exec_driver_sql("CREATE INDEX ix_scenario_runs_workspace_id ON scenario_runs (workspace_id)")
