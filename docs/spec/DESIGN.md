# Solution Design (v1)

Full behavioural spec is `docs/plan/PLAN.md`; program requirements are `docs/plan/CAPSTONE_COMPLIANCE.md`. This document records the concrete architecture and the stack decisions made with the user (see ADR-010), and is updated whenever a decision changes.

## Architecture diagram

```
                         ┌─────────────────────────────┐
                         │   React + Vite + shadcn/ui    │  frontend/
                         │  (tray, comparison table,    │
                         │   refusal cards, agent panel)│
                         └──────────────┬───────────────┘
                                        │ HTTP
                         ┌──────────────▼───────────────┐
                         │          FastAPI API          │  backend/api
                         │ /scenarios/evaluate|sweep|... │
                         │ /assumptions /envelope /info  │
                         │ /healthz /readyz /metrics     │
                         └───┬───────────────────┬───────┘
                             │                   │
              ┌──────────────▼──────┐   ┌────────▼─────────────┐
              │   Engine (pure,      │   │   Agent orchestrator  │  backend/agent
              │   deterministic)     │   │   Planner→Executor→   │
              │  backend/engine      │   │   Auditor over tools  │
              │  backend/model       │   │  calls engine via the │
              │  backend/assumptions │   │  same typed tool layer│
              └──────────┬───────────┘   └────────┬──────────────┘
                         │                         │
              ┌──────────▼───────────┐   ┌─────────▼─────────────┐
              │  Parquet + manifest   │   │  Anthropic / Scripted /│
              │  backend/data         │   │  Replay LLM client     │
              └───────────────────────┘   └────────────────────────┘
```

## Component responsibilities
- **`backend/data`**: generates the synthetic scanner dataset from a known model; owns the data manifest and hash.
- **`backend/assumptions`**: the single source of parameter truth (`assumptions.py`) plus the read-tracking registry (`registry.py`).
- **`backend/model`**: the parametric demand function, descriptive statistics (baselines, supported ranges, joint-coverage counts), and the K=200 Monte Carlo draws. No fitting.
- **`backend/engine`**: vectorised batch evaluation, margin waterfall/bridge, support-envelope checks, nearest-supported search, canonical IDs and result hashing. Pure functions; no I/O except reading the registry/draws/envelope artifacts.
- **`backend/api`**: FastAPI routes, Pydantic schemas, health/readiness/metrics endpoints. Thin — delegates all computation to `engine`.
- **`backend/agent`**: orchestrator (Planner/Executor/Auditor loop), typed tools wrapping the engine API, grounding/label/calc checks, trace writer and replay.
- **`frontend/`**: React + Vite + TypeScript app styled with Tailwind v4 and shadcn/ui components; calls the FastAPI backend over HTTP (proxied at `/api` in dev). No business logic.

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

## Stack decisions (deviate from `docs/plan/PLAN.md`'s default stack — see ADR-009, ADR-010)
- Backend: Python 3.11 via `uv`, FastAPI, Pydantic, in `backend/`.
- Frontend: React + Vite + TypeScript, Tailwind v4, shadcn/ui components, in `frontend/`. Calls the FastAPI backend over HTTP.
- LLM: Anthropic Claude via tool use; `ScriptedLLM`/`ReplayLLM` for deterministic offline tests (Phase 10-13), real Anthropic client wired in Phase 14.
- Deploy: Docker + docker compose on a local VM/host (no cloud account required); rollback = redeploy by git-SHA image tag.
- No `make` on Windows dev machines: `Makefile` targets forward to `uv run python -m tasks <target>` (`tasks.py`), so Windows and Linux CI run identically.

## Phase 0.5 spike results (throwaway scripts, not shipped)

**(a) Engine perf at 10k scenarios x 201 draws (central + K=200) x 12 SKUs.** The GEMM-based design (cross-price term as one matmul, chunked over S, bands computed only on scenario aggregates) is feasible but the 10k budget (<2s) has real margin, not huge headroom, on this dev laptop:

| Scenarios | best-of-5 | worst-of-5 | budget |
|---|---|---|---|
| 1 | 0.4ms | 0.8ms | <5ms |
| 100 | 5.6ms | 7.5ms | <50ms |
| 1,000 | 52.7ms | 58.8ms | <250ms |
| 10,000 | 540ms | 1,387ms | <2,000ms |

Sweep/oracle mode (`bands=false`, K=1) at 10,000 scenarios: 8.2ms — confirms the oracle (Phase 14, brute-force over ~1e6 points, run in chunks) is cheap. A follow-up micro-benchmark isolated the band computation: three separate `np.percentile` calls (one per P10/P50/P90) cost ~75ms at S=10,000/K=201 per metric; sorting once and indexing three times costs ~56ms (~25% faster) — adopt sort-once-per-metric in Phase 4/7 rather than three `np.percentile` calls, since there are 3 metrics (volume, NSV, GP) needing bands, not 1.

**(b) Claude tool-use shape.** No `ANTHROPIC_API_KEY` in this sandbox, so no live call; instead validated that `BaseModel.model_json_schema()` converts cleanly to an Anthropic `input_schema`, and that the SDK's typed params (`MessageCreateParamsNonStreaming`) accept a forced `tool_choice={"type":"tool","name":"submit_plan"}` without error. Two cosmetic fixes needed in the real `to_anthropic_tool()` helper (Phase 10): strip the per-property `"title"` keys Pydantic adds, and don't duplicate the model docstring as both the tool `description` and a nested schema `description`. The real end-to-end call (does the model actually return the forced tool with sane arguments) is exercised in Phase 14 as planned — this spike only de-risks the schema plumbing, not the model's behavior.

**(c) Hash quantization across platforms.** Confirmed quantize-then-hash (money/values to integer cents before canonical JSON + SHA-256) is stable across repeated fresh Windows processes (3/3 identical). **Not independently re-verified against a Linux container in this spike** — Docker Desktop was not running on this machine and starting it was out of scope for a quick spike. The mitigation (ADR-007: quantized integer outputs, golden files generated inside the Linux CI container, `OPENBLAS_NUM_THREADS=1`) is unchanged; real cross-platform parity will be proven by the `determinism` test suite running in GitHub Actions (`ubuntu-latest`) once Phase 6 lands, which is the actual gate that matters.

**Decision from the spikes:** proceed to Phase 1 as planned. No architecture change; the only adjustments are the two implementation notes above (sort-once-per-metric bands; strip title/dedupe description in the tool-schema converter).

## Phase 4 engine design notes

- **Reference price is data-derived, not a new assumption.** The generator's `unit_price = list_price_by_format * brand_price_multiplier * price_index` (no noise on price itself), so `unit_price / price_index` recovers each SKU's $ price at `price_index=1.0` exactly (division, not a fit). `backend/model/baselines.py`'s `Baselines.reference_price` computes this the same way `baseline_volume` already was in Phase 2, rather than promoting `GENERATOR_SEED["list_price_by_format"]` to a registry assumption the engine would otherwise need.
- **Margin bridge (AC-008)** decomposes GP into 6 stages — baseline -> +own-price&volume -> +cross-pack -> +promo (net of pull-forward) -> +trade -> +COGS — using the exact algebraic identity `price_final*vol1 - price_base*vol0 = (price_final-price_base)*vol0 + price_final*(vol1-vol0)` to split "price" from "volume". Components are rounded to cents independently; any residual versus the independently-rounded `GP_final - GP_base` is forced onto whichever component is largest in magnitude (`backend/engine/margin.py::build_bridge`), so the parts sum exactly to the total by construction, not by hoping float rounding cooperates.
- **RETAILER_RISK** needed a concrete formula the original plan didn't fully specify. `price_index` is treated as the manufacturer's own invoice-price lever (consistent with Phases 1-2, where it's also what demand responds to — this system has no separate shelf-price concept). Baseline retailer markup is assumed calibrated so the baseline margin equals the hurdle (A-017) exactly, so the flag is inert at `price_index=1.0` and reachable within the lever's bounds; without `pass_through` (A-017b) <1.0, manufacturer and shelf price would move 1:1 and the flag could never fire.
- **Known Phase 7 TODO, not fixed now:** Phase 0.5 spike (a) found sort-once-per-metric beats 3 separate `np.percentile` calls by ~25%; `backend/engine/batch.py::_band` still does 3 calls per (scenario, SKU) pair. Correctness-first for Phase 4's Hypothesis-property acceptance check; Phase 7 is where this gets benchmarked and optimised if the 10k-scenario budget is at risk.

## Team ownership (3-person variant, per `docs/plan/CAPSTONE_COMPLIANCE.md` section 2)
See `docs/TEAM.md`.
