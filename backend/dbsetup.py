"""Apply database migrations for the configured DATABASE_URL."""

from __future__ import annotations

from backend.db import get_engine
from backend.migrations.runner import upgrade_database


def main() -> int:
    engine = get_engine()
    if engine is None:
        print("DATABASE_URL is not configured; no migration was applied.")
        return 1
    applied = upgrade_database(engine)
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("Database is already at the latest migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
