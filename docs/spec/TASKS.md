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
| 4 | Vectorised engine, margin waterfall/bridge, baseline, IDs | A/B | 3 | AC-006..009 | not started |
| 5 | Support envelope, refusal output, nearest-supported, 500+ labelled refusal set | A/B | 4 | AC-010, AC-011, AC-012, AC-013 | not started |
| 6 | API, hashing, export/import | A/B | 5 | AC-014, AC-015 | not started |
| 7 | Benchmarks and optimisation | A/B | 6 | AC-016 | not started |
| 10-13 | Agent tools, orchestrator (ScriptedLLM), grounding, labels, Auditor, trace+replay | C | contracts (parallel with 1-7) | AC-017, AC-018, AC-020, AC-022 | not started |
| 8 | React/shadcn comparison UI (tray, table, refusal cards, drawer) | D | contracts (parallel with 1-7) | AC-024 (partial: loser+refusal) | **shell scaffolded** (mock data; API wiring pending) |
| 14 | Real Claude, ~40 agent evals, oracle, baselines | C | 7, 10-13 | AC-019, AC-021, AC-023 | not started |
| 15 | Agent panel UI (chat, quick-start goals, Auditor badge, accept-to-board) | C | 8, 14 | AC-024 (agent board) | not started |
| 16-17 | README (generated examples), HONESTY.md, clean-clone CI, AC traceability test, eval gate, `demo/regression` branch | D | 14, 15 | AC-025, AC-026 | not started |
| 18 | Security scans (pip-audit, bandit, gitleaks, trivy), TRIAGE, AGENT_BOUNDARY, threat model | D | 16-17 | Scans clear/risk-accepted; key absent from repo/logs/traces | not started |
| 19 | Containerisation, non-prod deploy, health checks, rollback, runbook, smoke test | D | 18 | AC-027 | not started |
| V2 | Trade-off plane, waterfall, sweep heatmap, meeting-mode sliders, trace viewer, claim chips | D/C | cut first if time is short | — | not started |
| 20 | Submission pack, rubric evidence index, QA prep, rehearsal | all | 19 | Submission checklist complete | not started |
