# Task plan

Sequenced phases, derived from `docs/plan/PLAN.md` section 18 and amended by `docs/plan/CAPSTONE_COMPLIANCE.md` section 11 (security/deploy/spec-pack/agent-record moved into MVP). Full technical design for each phase is in the approved plan file this build started from; this table tracks owner, dependency and status. Update `status` as work lands; do not start a phase until the previous phase's acceptance check (PLAN.md section 18, or the AC in `docs/spec/BRD.md`) passes.

| # | Deliverable | Owner | Depends on | Acceptance check | Status |
|---|---|---|---|---|---|
| 0 | Repo standards, CLAUDE.md, `.claude/settings.json` + hooks, BRD v1, DESIGN v1, ADRs 1-9, TASKS, TEAM, empty evidence files, CI skeleton | D | — | CI green; hook demonstrably blocks a protected-path edit | **in progress** |
| 0.5 | Spikes: engine at 10k×200×12 perf, Claude tool-use with forced `submit_*`, Windows/Linux hash quantization | A/B, C | 0 | Numbers recorded in DESIGN | **done** — see DESIGN.md "Phase 0.5 spike results" |
| — | Freeze Scenario/Result/tool Pydantic schemas + stub engine | A/B | 0.5 | Schema tests pass | not started |
| 1 | Data generator, Parquet, manifest, EDA, no-PII test | A/B | contracts | AC-001, AC-002, AC-003 | **done** — 29,952 rows (12 SKU x 3 region x 104 wk x 8 store), 13 tests green |
| 2 | Demand spec, baselines, envelope inputs, draws.npz, backtest+tornado report | A/B | 1 | AC-004 | **done** — MAPE 5.3%, band coverage 57.1%, tornado ranking stable across seeds, 20 tests green |
| 3 | Assumptions registry, read-tracking, `GET /assumptions` | A/B | 2 | AC-005 | **done** — 12 drawable ids at 100% coverage via the model pipeline; cost (A-013..A-017b) and qualitative (A-018..A-021) ids explicitly exempted pending Phase 4; 7 tests green |
| 4 | Vectorised engine, margin waterfall/bridge, baseline, IDs | A/B | 3 | AC-006..009 | **done** — `backend/engine/{scenario,ids,margin,batch}.py`; 4 Hypothesis property tests (AC-006..009) + unit tests, 58 total green |
| 5 | Support envelope, refusal output, nearest-supported, 500+ labelled refusal set | A/B | 4 | AC-010, AC-011, AC-012, AC-013 | **done** — per-SKU percentile/depth/joint checks; REFUSED results contain no metrics; separate nearest suggestion; sparse EDGE bands widened; 500 labelled cases, refusal/property suite green |
| 6 | API, hashing, export/import | A/B | 5 | AC-014, AC-015 | **done** — evaluate/sweep/nearest/envelope/model-info APIs; versioned export/import recomputes and verifies hashes; 67 full-suite tests green |
| 7 | Benchmarks and optimisation | A/B | 6 | AC-016 | **open** — reproducible K=200 benchmark on distinct in-support scenarios (2026-10-07): p95 1.0/38/334/3,772 ms at 1/100/1k/10k against <5/50/250/2,000 ms; passes 1 and 100, misses 1k and 10k. An earlier "passes all" result used only 13 distinct scenarios (see `docs/performance/OPTIMIZATION.md`) |
| 8 | React/shadcn comparison UI (tray, table, refusal cards, drawer) | D | contracts (parallel with 1-7) | AC-024 (partial: loser+refusal) | **done** — Playwright smoke verifies loser tag, refused card, and nearest-supported action; final production build passes |
| 9 | Trade-off plane, margin waterfall, price/promo heatmap | D | 8 | AC-024 analytics extension | **done** — analytics views are wired to evaluated outputs and covered by the Playwright smoke; final production build passes |
| 10-13 | Agent tools, orchestrator (ScriptedLLM), grounding, labels, Auditor, trace+replay | C | contracts (parallel with 1-7) | AC-017, AC-018, AC-020, AC-022 | **done** — scripted Planner/Executor/Auditor, tools, grounding, labels, trace/replay; see Phase 10-13 REVIEW_LOG entry |
| 14 | OpenAI live provider (ADR-012 deviation from Claude-only plan), ~43 agent evals, oracle, baselines | C | 7, 10-13 | AC-019, AC-021, AC-023 | **done** — grounding/refusal integrity/injection resistance/label correctness 100%, optimality gap median 0.0% (budget <=2%); `agent_evals/` |
| 15 | Agent panel UI (chat, quick-start goals, Auditor badge, accept-to-board) | C | 8, 14 | AC-024 (agent board) | **done** — `frontend/src/components/agent-panel.tsx` wired to live `/agent/run` |
| 16-17 | README (generated examples), HONESTY.md, clean-clone CI, AC traceability test, eval gate, `demo/regression` branch | D | 14, 15 | AC-025, AC-026 | **done** — `tests/test_ac_traceability.py` (25/27 ACs covered, 2 logged gaps), `docs/HONESTY.md`, generated README worked examples, `eval_thresholds.yaml` + eval-gate CI, `clean_clone.yml`; `demo/regression` branch not pushed (left uncommitted/local per instruction) |
| 18 | Security scans (pip-audit, bandit, gitleaks, trivy), TRIAGE, AGENT_BOUNDARY, threat model | D | 16-17 | Scans clear/risk-accepted; key absent from repo/logs/traces | **in progress** — pip-audit/bandit/gitleaks CI and documented STRIDE model are present; Trivy awaits a runnable Docker daemon and built image |
| 19 | Containerisation, non-prod deploy, health checks, rollback, runbook, smoke test | D | 18 | AC-027 | **in progress** — non-root API/web Dockerfiles, compose stack, `/readyz`, and fixed-hash smoke verifier added; rollback demonstration awaits Docker Desktop activation |
| 21 | Synthetic consumer evidence layer: consumers, WTP/GG/VW, conjoint simulation, research-to-RGM bridge + provenance, agent evidence tools, Price/Pack/Promotion lever views | all | 14, 15 | AC-028..AC-033 | **done** - `backend/research/evidence.py`, registry A-026..A-037, `/pricing/*` endpoints, agent research plan + label rules, `tests/research/`, `tests/agent/test_research_agent.py`, `tests/api/test_research_endpoints.py`; see ADR-013 |
| V2 | Trade-off plane, waterfall, sweep heatmap, meeting-mode sliders, trace viewer, claim chips | D/C | cut first if time is short | — | not started |
| 20 | Submission pack, rubric evidence index, QA prep, rehearsal | all | 19 | Submission checklist complete | not started |



