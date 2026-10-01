# First prompt for Claude Code (Phases 1 and 2)

Setup: create an empty repo, put `PLAN.md` and `CLAUDE.md` in the root, start Claude Code there, and paste the prompt below.

---

Read PLAN.md and CLAUDE.md fully before doing anything. This is an agentic AI project: the data and model phases exist only to give the agent a trustworthy, simple engine to call, so keep them lean. We are building phase by phase. Start with Phase 1 (Data) and Phase 2 (Model) only.

**Step 0: Phase 0 first.** Read CAPSTONE_COMPLIANCE.md. Before any feature code, set up: repo standards (ruff, pre-commit, gitleaks), `.claude/settings.json` with permission deny rules (`.env*`, secrets, generated data and golden files) and hooks, docs/spec/ BRD v1 with testable AC IDs, DESIGN v1, first ADRs, TASKS.md, TEAM.md, REVIEW_LOG.md and DEFECTS.md templates, and a CI skeleton that runs green. Stop and show me before continuing.

**Step 0b: scaffold**
- Create the repo structure from PLAN.md section 17 (empty packages are fine for later phases).
- Set up `pyproject.toml` (Python 3.11; numpy, pandas, pyarrow, pydantic, fastapi, pytest, hypothesis, pytest-benchmark) and a `Makefile` with targets `generate`, `backtest`, `test`, `bench`, `evaluate`, `serve` (unimplemented ones can echo "not yet").

**Phase 1: Data**
- Implement `simulator/data/generator.py` following PLAN.md section 3 (CPG beverage category, fictional brands, 12 SKUs, retail-scanner format): 12 SKUs, 104 weeks, 3 regions, the ground-truth log-log demand model, own-price elasticities from -0.8 to -2.5 (larger packs less elastic), a cross-elasticity matrix (within-brand stronger than across-brand), saturating promo response with a 15-25% post-promo pull-forward dip, and cost columns.
- Observed ranges: price index 0.88-1.12, promo depth 0-30% in steps, 4 pack sizes.
- Deliberately create joint-support gaps (e.g., no rows with promo depth above 20% and price index above 1.06). Document exactly which gaps exist in the generator docstring and in the manifest.
- Define the elasticity, promo and cost parameters once, in a single structured spec (`simulator/assumptions/assumptions.py`) imported by both the generator and the engine. Each parameter has a value, plausible range, source and rationale. Phase 3 adds the registry access layer and read tracking on top.
- All randomness through a seeded `numpy.random.Generator` passed explicitly.
- Output Parquet plus `data_manifest.json` (seed, generator version, row count, SHA-256 of the Parquet, list of deliberate gaps).
- Tests: same seed gives identical SHA-256 (run in-process and in a subprocess); different seed gives a different hash; observed ranges respected; the deliberate gaps really are empty.
- An EDA notebook or script that plots price vs promo coverage so the gaps are visible.

**Phase 2: Parametric engine spec (no fitting)**
- Implement `simulator/model/spec.py`: the parametric demand function (own-price, cross-price, saturating promo lift with mechanic multiplier, pull-forward dip, discrete format baselines), vectorised over scenarios. Nothing is trained or fitted and no ML libraries are used.
- Compute descriptive statistics from the dataset only: baseline volume per SKU (last 13 weeks), per-lever supported ranges, and the binned joint-coverage count table (price index x promo depth x format x mechanic) for the Phase 5 support check.
- Draw K=200 assumption sets (each assumption within its plausible range, fixed seed) and save to `draws.npz` with a manifest including the data hash and a spec hash.
- Generate `reports/model_backtest.md`: engine vs held-out observations (last 13 weeks, error and band coverage) and a one-at-a-time sensitivity (tornado) ranking of assumptions. State that the generator shares the assumption set, so near-noise error is expected and is a consistency check, not a validation of real-world accuracy.
- Tests: back-test error within a stated tolerance, results reproducible from the seed, sensitivity ranking stable across seeds.

**Rules while working**
- Never hardcode parameters outside the single assumption spec; Phase 3 wraps it in the registry.
- When both phases pass their acceptance checks (PLAN.md section 18), stop and report: what you built, test results, the validation report headline numbers, and any design decisions I should review. Do not start Phase 3.

---

# Later prompts (use after each phase passes)

**Phases 3-4:** "Phase 1-2 are accepted. Implement Phase 3 (assumptions registry with read-tracking and `GET /assumptions`, coverage test) and Phase 4 (vectorised batch engine, margin, baseline, property tests). Same rules. Stop and report after Phase 4."

**Phases 5-7:** "Implement Phase 5 (support envelope, per-lever and joint checks, refusal output with nearest-supported, labelled refusal suite of 500+ points), Phase 6 (API, result hashing, export/import, determinism tests) and Phase 7 (benchmarks and optimisation to hit all budgets). Report timing tables."

**Phases 8-9:** "Implement the comparison-first UI per PLAN.md section 8 and the sweep heatmap, waterfall and README. Run the Playwright smoke test and `make evaluate` for the four engine metrics."

**Phases 10-13 (agent, fake LLM):** "Implement the agent tool layer, orchestrator loop with Planner/Executor/Auditor, numeric grounding checker, structured final output, and trace/replay, using a scripted fake LLM so everything runs offline. Include tests for refusal re-planning, ungrounded-answer rejection and replay hash matching."

**Phases 14-15 (real LLM):** "Wire in the real model, build the ~40-task `agent_evals/` suite with programmatic checkers, run it, then build the agent UI (panel, trace viewer, claim chips, accept-to-board). Update `make evaluate` so `reports/metrics.md` covers engine and agent metrics."
