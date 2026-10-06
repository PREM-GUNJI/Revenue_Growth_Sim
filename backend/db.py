"""Optional PostgreSQL persistence for evaluated scenario runs."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import DateTime, Integer, String, create_engine, select
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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
