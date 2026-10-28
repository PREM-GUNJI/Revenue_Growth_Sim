# ADR-019: pgvector for historical run similarity

## Status
Accepted

## Context
Operators want to find similar past scenario runs and agent-related summaries as the corpus of persisted evaluations grows. The product already uses PostgreSQL for `scenario_runs` and workspaces. Separately, `nearest_supported` and the support envelope must remain exact geometric / occupancy checks — approximate nearest-neighbour search must never soften `REFUSED` or invent commercial numbers.

## Decision
- Use a **native PostgreSQL** instance via `DATABASE_URL` with the **pgvector** extension (`CREATE EXTENSION vector`). Docker is not required for this feature; Compose remains optional for other workflows.
- Store `run_embeddings` beside `scenario_runs` (migration `007_pgvector_run_embeddings`).
- **Lever embeddings** are deterministic feature vectors from quantized levers and cost shocks (no neural net, nothing fitted on scanner data).
- **Text embeddings** are a deterministic bag-of-hashes over a compact summary string (offline; no external embedding API).
- Expose `POST /scenarios/similar` and the agent tool `find_similar_runs`. Retrieved rows are labelled **Observed** (prior persisted runs). Recommended claims still require a Modeled tool result from the current evaluation.
- **Do not** use pgvector for `nearest_supported`, envelope checks, or any refusal workaround.

## Consequences
- Operators install pgvector on their Postgres (OS package or build) and enable the extension once per database.
- Similarity quality is coarse by design; it is a retrieval aid, not a demand model.
- SQLite test migrations create a TEXT stand-in table; cosine ANN SQL requires real PostgreSQL + pgvector.
