"""Enable pgvector and create run_embeddings for historical similarity search."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from backend.similarity import LEVER_DIM, TEXT_DIM


def upgrade(connection: Connection) -> None:
    dialect = connection.dialect.name
    if dialect == "postgresql":
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        connection.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS run_embeddings (
                run_id VARCHAR(64) PRIMARY KEY,
                scenario_id VARCHAR(64) NOT NULL,
                workspace_id VARCHAR(64),
                status VARCHAR(16) NOT NULL,
                market_id VARCHAR(16) NOT NULL DEFAULT 'in',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                lever_embedding vector({LEVER_DIM}) NOT NULL,
                text_embedding vector({TEXT_DIM}) NOT NULL,
                summary_text TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_run_embeddings_scenario_id ON run_embeddings (scenario_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_run_embeddings_workspace_id ON run_embeddings (workspace_id)"
        )
        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_run_embeddings_lever_hnsw
            ON run_embeddings USING hnsw (lever_embedding vector_cosine_ops)
            """
        )
        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_run_embeddings_text_hnsw
            ON run_embeddings USING hnsw (text_embedding vector_cosine_ops)
            """
        )
        return

    # SQLite / other: JSON text stand-ins so migrations stay testable without pgvector.
    connection.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS run_embeddings (
            run_id VARCHAR(64) PRIMARY KEY,
            scenario_id VARCHAR(64) NOT NULL,
            workspace_id VARCHAR(64),
            status VARCHAR(16) NOT NULL,
            market_id VARCHAR(16) NOT NULL DEFAULT 'in',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            lever_embedding TEXT NOT NULL,
            text_embedding TEXT NOT NULL,
            summary_text TEXT NOT NULL DEFAULT ''
        )
        """
    )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_run_embeddings_scenario_id ON run_embeddings (scenario_id)"
    )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_run_embeddings_workspace_id ON run_embeddings (workspace_id)"
    )
