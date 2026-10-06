"""Database migrations are idempotent and create the scenario-run and users schema."""

from sqlalchemy import create_engine, inspect

from backend.migrations.runner import upgrade_database


def test_initial_migration_creates_schema_once():
    engine = create_engine("sqlite://")

    assert upgrade_database(engine) == ["001_initial_scenario_runs", "002_users", "003_workspaces", "004_ai_usage_cached_tokens"]
    assert upgrade_database(engine) == []

    tables = set(inspect(engine).get_table_names())
    assert {"schema_migrations", "scenario_runs", "users", "workspaces", "workspace_state", "activity_log", "ai_usage"} <= tables
