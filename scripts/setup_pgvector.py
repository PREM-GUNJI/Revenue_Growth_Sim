"""Enable pgvector on DATABASE_URL and apply migrations (uses existing system install)."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def main() -> int:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set in .env")
        return 1

    engine = create_engine(url)
    with engine.connect() as conn:
        version = conn.execute(text("SHOW server_version")).scalar()
        database = conn.execute(text("SELECT current_database()")).scalar()
        print(f"connected database={database} server={version}")

        available = conn.execute(
            text(
                "SELECT name, default_version, installed_version "
                "FROM pg_available_extensions WHERE name = 'vector'"
            )
        ).fetchone()
        print(f"pg_available_extensions.vector={available}")
        if available is None:
            print(
                "ERROR: extension 'vector' is not available to this Postgres instance. "
                "Install files into this server's share/extension and lib, then retry."
            )
            return 2

        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        installed = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        print(f"CREATE EXTENSION ok version={installed}")

    from backend.db import get_engine, initialize_database

    get_engine.cache_clear()
    ok = initialize_database()
    print(f"initialize_database={ok}")

    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name IN "
                "('run_embeddings', 'scenario_runs', 'schema_migrations') "
                "ORDER BY 1"
            )
        ).scalars().all()
        print(f"tables={tables}")
        migrations = conn.execute(
            text("SELECT version FROM schema_migrations ORDER BY version")
        ).scalars().all()
        print(f"migrations={migrations}")
        has_vector_cols = conn.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'run_embeddings' AND data_type = 'USER-DEFINED'"
            )
        ).scalar()
        print(f"run_embeddings_user_defined_cols={has_vector_cols}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
