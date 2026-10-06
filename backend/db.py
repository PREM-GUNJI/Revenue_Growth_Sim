"""Optional PostgreSQL persistence for evaluated scenario runs."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import JSON

load_dotenv()


class Base(DeclarativeBase):
    pass


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    result_hash: Mapped[str] = mapped_column(String(64), index=True)
    k: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    scenario: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    result: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    workspace_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class User(Base):
    """A person allowed to sign in. Only the Argon2 hash of the password is stored."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class Workspace(Base):
    """A named scenario workspace, shared by all signed-in users."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(320))
    updated_by: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class WorkspaceState(Base):
    """The autosaved scenario list of a workspace. `version` guards against silent overwrites."""

    __tablename__ = "workspace_state"

    workspace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenarios: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ActivityLog(Base):
    """Audit trail: who did what, when. Holds actions and ids only, never secrets or scenario contents."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)


class AiUsage(Base):
    """One row per agent run: provider, model, tokens and the cost computed from the rate table."""

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_version: Mapped[str | None] = mapped_column(String(64), nullable=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine | None:
    url = os.getenv("DATABASE_URL")
    return create_engine(url, pool_pre_ping=True) if url else None


def get_session_factory() -> sessionmaker | None:
    engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False) if engine else None


def initialize_database() -> bool:
    engine = get_engine()
    if engine is None:
        return False
    from backend.migrations.runner import upgrade_database

    upgrade_database(engine)
    return True


def database_status() -> str:
    engine = get_engine()
    if engine is None:
        return "not_configured"
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return "ok"
    except Exception:
        return "unavailable"


def save_run(record: dict[str, Any]) -> None:
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    initialize_database()
    with factory() as session:
        session.add(ScenarioRun(**record))
        session.commit()


def list_runs(limit: int = 100) -> list[ScenarioRun]:
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    initialize_database()
    with factory() as session:
        return list(session.scalars(select(ScenarioRun).order_by(ScenarioRun.created_at.desc()).limit(limit)))
