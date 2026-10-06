# ADR-012: OpenAI as the live agent provider; optional PostgreSQL persistence for scenario runs

Status: accepted

Context: `CLAUDE.md` names "LLM: Anthropic Claude via tool use, with a scripted fake LLM and a replay LLM for offline/deterministic tests," and names no database (the engine's inputs are Parquet files via the assumptions registry). For phases 10-14, the user chose OpenAI's structured-output API (`responses.parse`) as the live model provider instead of Claude, and added PostgreSQL to persist evaluated scenario runs for later retrieval, neither of which CLAUDE.md or `docs/spec/DESIGN.md` anticipated.

Options considered:
- A. Follow CLAUDE.md literally: wire only Anthropic Claude for the live path, keep no database. Rejected — contradicts the user's explicit choice of provider and infra, and the capstone format wraps DESIGN.md/CLAUDE.md as a starting agreement, not an immutable constraint, with an ADR as the mechanism to record a deliberate departure.
- B. Swap Claude for OpenAI everywhere, including the deterministic test path. Rejected — this would break the "phases 10-13 use a scripted fake LLM so tests are offline and deterministic" rule; CI/tests must not depend on network calls or non-deterministic model output.
- C. Keep the model provider pluggable: `ScriptedLLM` (in `backend/agent/orchestrator.py`) remains the only provider used by `AgentOrchestrator`'s offline tests, grounding tests and replay tests; `backend/agent/openai_llm.py`'s `OpenAILLM` implements the same `plan()`/`draft()` interface and is only ever constructed on the live `POST /agent/run` endpoint. Add `backend/db.py` (SQLAlchemy + psycopg) as an optional persistence layer, gated entirely on the `DATABASE_URL` env var: absent it, `/scenario-runs` returns 503 and nothing else in the engine, agent or its tests touches a database.

Decision: C.

Consequences:
- No test imports or calls `OpenAILLM` against a live network; `tests/agent/test_openai_llm.py` exercises it against a fake `OpenAI` client only, matching the "scripted fake LLM" determinism rule in spirit for the provider's own unit coverage.
- The engine, agent tools, grounding, labels and Auditor remain provider-agnostic — every number in agent output still traces to a tool result regardless of which LLM drafted the summary (CLAUDE.md's agent rules are unaffected by the provider swap).
- Postgres is infrastructure for run history/audit retrieval only; it is never a source of engine parameters (those remain in the assumptions registry) and is never required for the engine, agent loop or any existing test suite to pass. `compose.yaml` adds a `db` service for local/non-prod use; `.env.example` documents `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`.
- `CLAUDE.md`'s stack line ("LLM: Anthropic Claude...") is superseded for the live agent path only; this ADR, `docs/spec/DESIGN.md` and `CLAUDE.md` together are the source of truth going forward — if they conflict, this ADR governs the OpenAI/Postgres decision specifically.

Owner / date: user / 2026-10-06
