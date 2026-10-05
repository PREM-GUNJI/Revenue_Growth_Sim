# Solution Design (v1)

Full behavioural spec is `docs/plan/PLAN.md`; program requirements are `docs/plan/CAPSTONE_COMPLIANCE.md`. This document records the concrete architecture and the stack decisions made with the user (see ADR-009), and is updated whenever a decision changes.

## Architecture diagram

```
                         ┌─────────────────────────────┐
                         │        HTMX + Jinja2 UI      │  simulator/web
                         │  (tray, comparison table,    │
                         │   refusal cards, agent panel)│
                         └──────────────┬───────────────┘
                                        │ HTTP
                         ┌──────────────▼───────────────┐
                         │          FastAPI API          │  simulator/api
                         │ /scenarios/evaluate|sweep|... │
                         │ /assumptions /envelope /info  │
                         │ /healthz /readyz /metrics     │
                         └───┬───────────────────┬───────┘
                             │                   │
              ┌──────────────▼──────┐   ┌────────▼─────────────┐
              │   Engine (pure,      │   │   Agent orchestrator  │  simulator/agent
              │   deterministic)     │   │   Planner→Executor→   │
              │  simulator/engine    │   │   Auditor over tools  │
              │  simulator/model     │   │  calls engine via the │
              │  simulator/assumptions│  │  same typed tool layer│
              └──────────┬───────────┘   └────────┬──────────────┘
                         │                         │
              ┌──────────▼───────────┐   ┌─────────▼─────────────┐
              │  Parquet + manifest   │   │  Anthropic / Scripted /│
              │  simulator/data       │   │  Replay LLM client     │
              └───────────────────────┘   └────────────────────────┘
```

## Component responsibilities
- **`simulator/data`**: generates the synthetic scanner dataset from a known model; owns the data manifest and hash.
- **`simulator/assumptions`**: the single source of parameter truth (`assumptions.py`) plus the read-tracking registry (`registry.py`).
- **`simulator/model`**: the parametric demand function, descriptive statistics (baselines, supported ranges, joint-coverage counts), and the K=200 Monte Carlo draws. No fitting.
- **`simulator/engine`**: vectorised batch evaluation, margin waterfall/bridge, support-envelope checks, nearest-supported search, canonical IDs and result hashing. Pure functions; no I/O except reading the registry/draws/envelope artifacts.
- **`simulator/api`**: FastAPI routes, Pydantic schemas, health/readiness/metrics endpoints. Thin — delegates all computation to `engine`.
- **`simulator/web`**: server-rendered HTMX/Jinja2 UI that calls the API. No business logic.
- **`simulator/agent`**: orchestrator (Planner/Executor/Auditor loop), typed tools wrapping the engine API, grounding/label/calc checks, trace writer and replay.

## Data flow (one scenario evaluation)
1. UI or agent tool call sends a `Scenario` to `POST /scenarios/evaluate`.
2. API expands omitted SKUs to baseline, quantizes levers, computes `scenario_id`.
3. Engine checks the support envelope (precomputed lookup); if `REFUSED`, returns the reason and a `nearest_supported` suggestion — no numeric fields.
4. If `SUPPORTED`/`EDGE`, engine runs the vectorised demand + margin computation (central value plus K=200 draws for bands), computes `result_hash`.
5. API returns the result; the agent (if the caller is the Executor) attaches the result to its tool-result history for grounding.

## Trust boundaries (what the agent can and cannot touch)
- The agent has **no** filesystem, network or engine-internals access. It only calls the typed tool functions listed in `docs/plan/PLAN.md` section 9, which wrap the same HTTP API the UI uses.
- Tool outputs and scenario names are treated as data, never as instructions (prompt-injection hygiene, AC-019).
- The Auditor is deterministic code, not a second LLM call, for the checks that have a right answer (grounding, labels, refusal integrity).
- Full detail in `docs/security/AGENT_BOUNDARY.md` (Phase 18).

## Failure modes
- **LLM API down or rate-limited**: the engine and UI keep working; the agent panel shows a degraded-but-explicit state (never a silent retry loop). Replay mode (recorded traces + fake LLM) is the demo fallback.
- **Hash mismatch on replay**: replay fails loudly and names the first divergent tool call; it is never silently ignored.
- **Support envelope miss (false SUPPORTED)**: caught by the refusal suite's precision/recall gate in CI before merge.
- **Performance budget miss**: benchmarks gate CI; a regression blocks the PR.

## Stack decisions (deviate from `docs/plan/PLAN.md`'s default stack — see ADR-009)
- Backend: Python 3.11 via `uv`, FastAPI, Pydantic.
- UI: FastAPI + Jinja2 + HTMX, server-rendered, no React/Node/npm in the shipped app. Chosen so a 3-person team works in one language end to end.
- LLM: Anthropic Claude via tool use; `ScriptedLLM`/`ReplayLLM` for deterministic offline tests (Phase 10-13), real Anthropic client wired in Phase 14.
- Deploy: Docker + docker compose on a local VM/host (no cloud account required); rollback = redeploy by git-SHA image tag.
- No `make` on Windows dev machines: `Makefile` targets forward to `uv run python -m tasks <target>` (`tasks.py`), so Windows and Linux CI run identically.

## Team ownership (3-person variant, per `docs/plan/CAPSTONE_COMPLIANCE.md` section 2)
See `docs/TEAM.md`.
