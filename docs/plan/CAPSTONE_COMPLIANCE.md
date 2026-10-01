# Capstone Compliance Addendum

Companion to `PLAN.md`. PLAN.md defines *what the system is*; this file defines *what must be delivered and defended* under the program rules (synthetic data only, "engineered not prompted", measured, secure, operable, honest).

**Important change to the cut line in PLAN.md section 2:** security, deployment, the specification pack and the agent engineering record are now mandatory MVP items. UI polish (V2) is what gets trimmed, never these.

---

## 1. Requirement traceability matrix

| Program requirement | How this project satisfies it | Evidence artifact | Phase |
|---|---|---|---|
| Synthetic or public data only, real format, volume that makes engineering decisions real | Generated FMCG sales data (about 31k weekly rows, 12 SKUs, 3 regions) in retailer-POS-style format; PII/PHI scan test | `data/` generator, manifest, `tests/data/test_no_pii.py` | 1 |
| Runs end-to-end from a clean clone | `make bootstrap && make demo` builds data, fits the engine, starts API and UI; clean-clone CI job proves it | README, `ci/clean_clone.yml` | 16 |
| Engineered, not prompted | Instruction files, skills, hooks, BRD, design, ADRs, task plan, review log, all in git | `docs/`, `.claude/`, `docs/agent-record/` | 0, 16 |
| Measured vs baseline, with a CI eval gate that can block a merge | `make evaluate` against defined baselines (section 4); CI fails below thresholds | `reports/metrics.md`, `.github/workflows/eval-gate.yml` | 14, 17 |
| Secure | Scans clear or risk-accepted; secrets in a manager; stated agent permission boundary | `docs/security/` | 18 |
| Operable | Non-prod deployment, health checks, demonstrated rollback, runbook | `docs/ops/`, `deploy/` | 19 |
| Honest | Limitations, residual risk and refusals stated up front | `docs/HONESTY.md`, UI "Limitations" panel | 16 |
| Every member owns and defends an area | Ownership map (section 2) | `docs/TEAM.md` | 0 |
| Competencies across all ten days, not one technique repeated | Competency map (section 3) | `docs/COMPETENCY_MAP.md` | 0 |
| Pre-pitch deliverables submitted | Checklist (section 12) | `docs/SUBMISSION.md` | 20 |

---

## 2. Team ownership (4 members; 3-person variant below)

Each member owns an area end to end: spec, code review, tests, metrics and defence. Agents write the code; the owner reviews every merge in their area and logs it.

| Member | Owns | Defends at the panel | Key artifacts |
|---|---|---|---|
| **A: Data and model truth** | Synthetic generator, parametric demand spec, assumptions registry, back-test and sensitivity report, PII scan | "Why trust these numbers? What are the assumptions? Why synthetic and is it realistic?" | `data/`, `model/`, `assumptions/`, validation report |
| **B: Engine, guardrails and performance** | Batch engine, support envelope and refusal, API, hashing and reproducibility, benchmarks | "How do you refuse correctly? Is it fast and deterministic?" | `engine/`, `api/`, refusal suite, benchmark gate |
| **C: Agent and evaluation** | Orchestrator, tools, Auditor, grounding and labels, traces and replay, agent evals, baselines | "How do you know the agent never invents numbers? What happens under pressure or injection?" | `agent/`, `agent_evals/`, `reports/metrics.md` |
| **D: Platform, security, UI and ops** | Repo standards, CI/CD, hooks and permission boundary, scans, secrets, Docker and deployment, rollback and runbook, comparison UI | "Is it secure and operable? Show me rollback." | `.github/`, `deploy/`, `docs/security`, `docs/ops`, `web/` |

**3-person variant:** merge A and B (data, model and engine) and keep C and D unchanged. Move the PII scan to D.

**Rule:** every PR names its owner and reviewer. The owner must be able to explain every line merged in their area without the agent. Rehearse this: pick any file at random and have the owner walk through it.

---

## 3. Competency map (anti "one technique ten times")

Fill in the exact day-to-competency mapping from your program schedule. The plan already spans these capability families, so map each to evidence:

| Capability family | Where it shows up |
|---|---|
| Spec-driven development (BRD, design, task plan) | `docs/spec/`, acceptance criteria linked to tests |
| Agent instruction engineering (CLAUDE.md, skills, hooks) | `.claude/`, `CLAUDE.md` |
| Agentic system design (tools, roles, guardrails) | `agent/` |
| Evaluation and baselines | `agent_evals/`, `reports/metrics.md` |
| Guardrails and safe failure | Support envelope, Auditor, refusal integrity |
| Observability and reproducibility | Traces, hashes, replay, health endpoints |
| Security (scanning, secrets, permission boundary, prompt injection) | `docs/security/`, injection evals |
| CI/CD and gates | `.github/workflows/` |
| Deployment and operations | `deploy/`, `docs/ops/` |
| Multi-agent / parallel delegation and tool comparison | Cloud agent tasks, Codex comparison (section 6) |

---

## 4. Baselines (the "measured against what" question)

The rubric asks for real numbers *and the baseline they are compared to*. Define these on day one so evaluation is designed in:

| Metric | Baseline | How measured |
|---|---|---|
| Time to answer a what-if question | Manual spreadsheet process: have a team member build 5 representative scenarios in a spreadsheet, timed, and record the minutes. Compare to the simulator's wall-clock for the same 5 | Timed trial, logged in `reports/baseline_manual.md` |
| Numeric grounding / hallucination | **Ungrounded LLM**: same model, same questions, no tools, asked for the numbers directly | Run the eval set both ways; report the grounding rate and the error vs engine truth |
| Refusal correctness | **Naive range check** (per-lever min/max only, as in a simple guardrail) vs envelope with joint-density check | Labelled refusal set; compare recall on joint-gap cases |
| Scenario throughput | Single-scenario Python loop vs vectorised engine | Benchmarks |
| Agent search quality | Random search with the same tool-call budget | Optimality gap vs oracle |
| Cross-tool comparison (optional) | Same tasks via Codex | Section 6 |

Report every metric as `baseline -> system -> delta`, with the evaluation set committed to the repo.

---

## 5. Specification pack (`docs/spec/`)

All in version control, written *before* the code it governs, and updated when decisions change.

- **`BRD.md`**: business problem, users, in/out of scope, and **testable acceptance criteria** with IDs (`AC-001`...). Each AC maps to a named test. A CI check fails if an AC has no linked test (`tests/test_ac_traceability.py` parses the BRD).
  Example ACs: `AC-004` "A scenario with price index outside the observed 1st-99th percentile returns status REFUSED and no numeric fields"; `AC-011` "100 scenarios evaluate in under 50 ms p95".
- **`DESIGN.md`**: architecture diagram, component responsibilities, data flow, trust boundaries (what the agent can and cannot touch), failure modes.
- **`adr/`**: decision records (template below). Suggested first set:
  1. Agent never computes numbers; engine is the sole source of truth
  2. Parametric engine with stated assumptions rather than fitted or ML models
  3. Refusal over extrapolation, with a joint-density check
  4. Registry-only parameter access
  5. Programmatic (not LLM-judged) grounding
  6. Function calling vs MCP for the tool layer
  7. Hashing and canonical JSON for reproducibility
  8. Deployment target and rollback strategy
- **`TASKS.md`**: sequenced task plan (the phases in PLAN.md section 18 broken into tasks with owner, dependency, acceptance criterion, status).

**ADR template**
```
# ADR-00N: Title
Status: proposed | accepted | superseded
Context: what forced the decision
Options considered: A, B, C with trade-offs
Decision: what and why
Consequences: what gets easier or harder, risks
Owner / date
```

---

## 6. Agent engineering record (`.claude/` and `docs/agent-record/`)

### 6.1 Instruction files and skills
- `CLAUDE.md` (root) holds project rules; keep it short and enforceable. Add nested `CLAUDE.md` files in `engine/`, `agent/` and `web/` with area-specific rules.
- `.claude/skills/` holds reusable skills, for example: `add-assumption` (create a registry entry with rationale, valid range and test), `add-refusal-case` (add a labelled boundary case), `add-agent-eval` (task plus programmatic checker), `write-adr`, `review-checklist`.
- `.claude/agents/` holds subagent definitions where useful, for example a `reviewer` agent with read-only tools and a `security-reviewer`.

### 6.2 Hooks (version-controlled in `.claude/settings.json`)
| Hook | Purpose |
|---|---|
| PreToolUse on Edit/Write | Block edits to protected paths: `reports/` generated files, `.env*`, golden files without an explicit flag |
| PreToolUse on Bash | Block destructive commands (`rm -rf` outside the workspace, `git push --force`, network egress beyond an allowlist) |
| PostToolUse on Edit/Write | Run formatter and linter (`ruff`, `eslint`) |
| Stop / pre-commit | Run fast tests plus the secret scan; refuse commit on failure |
| UserPromptSubmit (optional) | Inject current phase and active ACs as context |

### 6.3 CI gates (`.github/workflows/`)
`lint` -> `unit+property` -> `refusal suite` -> `determinism` -> `benchmark gate` -> `agent eval gate (fake LLM + recorded traces)` -> `security scans` -> `AC traceability` -> `build image`. Any failure blocks merge (branch protection on `main`).

### 6.4 Review log (`docs/agent-record/REVIEW_LOG.md`)
One entry per agent-generated change set. This is your evidence for "you own the result".

```
| PR | Area/owner | Tool (Claude Code / cloud agent / Codex) | Task | What agent produced | Reviewer | Defects found | Action | Tests added |
```
Also keep `DEFECTS.md`: each defect the review or CI caught, how it was caught, and what rule or hook you added to prevent recurrence. Aim to record real defects honestly (e.g., "agent clamped an out-of-range price instead of refusing, caught by refusal suite, added hook and test"). A log with zero defects is not credible.

### 6.5 Parallel and comparative tooling
- **Claude cloud agent (delegated/parallel):** give it bounded, well-specified, independent tasks: generate the 500+ labelled refusal cases, write the 40 agent-eval tasks and checkers, scaffold the UI against the API schema, draft runbook sections from the deploy config. Each returns a PR that the area owner reviews.
- **OpenAI Codex (comparison):** run one or two identical tasks through both tools (suggested: the batch engine from the spec, and the Auditor's grounding checker). Record time, defects, test pass rate and review effort in `docs/agent-record/TOOL_COMPARISON.md`. State the finding honestly even if it is "no meaningful difference".

---

## 7. Evaluation (`reports/` and `agent_evals/`)

- Evaluation set committed: labelled refusal set (500+), agent tasks (about 40), reproducibility golden files, benchmark scenarios.
- `make evaluate` produces `reports/metrics.md` with `baseline -> system -> delta` for every metric in PLAN.md section 16.
- **CI eval gate:** thresholds in `eval_thresholds.yaml` (for example grounding = 100%, refusal recall = 100%, replay fidelity = 100%, optimality gap median <= 2%, p95 budgets). CI runs the deterministic subset (fake LLM and recorded traces) on every PR, and the real-LLM suite on a schedule or manual trigger, with results committed. A PR that regresses a threshold cannot merge. **Demonstrate this live:** have a prepared branch that deliberately regresses a metric and show the gate blocking it.

---

## 8. Security (`docs/security/`)

| Item | What to produce |
|---|---|
| Dependency scanning | `pip-audit` and `npm audit` output |
| Static analysis | `bandit` (Python), optionally `semgrep` |
| Secret scanning | `gitleaks` in pre-commit and CI |
| Container scanning | `trivy` on the built image |
| Triage | `TRIAGE.md`: each finding fixed, or explicitly **risk-accepted** with rationale, owner and expiry |
| Secrets handling | LLM API key lives in a secret manager (GitHub Actions secrets for CI; cloud secret manager or the platform's secret store for deploy; local dev via an untracked `.env` that Claude Code is denied from reading). Show that the key never appears in the repo, logs, traces or agent context |
| Agent access boundary | `docs/security/AGENT_BOUNDARY.md` stating: allowed tools and paths, denied paths (`.env*`, secrets), network policy, what the runtime agent (typed tools only) versus the build agents (Claude Code permissions in `.claude/settings.json`) can do |
| Threat model | Short STRIDE-style table including prompt injection via scenario names, tool-output injection, key leakage, data tampering, and denial of service via large scenario batches (rate and size limits) |
| Data safety | Test asserting no PII/PHI patterns in generated data; synthetic data banner in the UI and README |

---

## 9. Deployment and operations (`deploy/`, `docs/ops/`)

- **Containers:** multi-stage Dockerfile for API (and one for web), `docker-compose.yml` for local, non-root user, pinned dependencies.
- **Non-production target:** pick one and commit the config: Cloud Run, Render, Fly.io, or a small VM with compose. Document the choice in an ADR.
- **Health checks:** `GET /healthz` (liveness) and `GET /readyz` (model loaded, registry loaded, envelope loaded, data hash matches manifest, LLM reachable as a degraded-not-fatal check). Expose `GET /metrics` (latency, refusal counts, audit failures) if time allows.
- **Versioned releases:** images tagged by git SHA; `model/info` reports model hash and data hash so every deployed version is identifiable.
- **Demonstrated rollback:** deploy v1, deploy v2 (with a deliberately bad change that fails a readiness check or the smoke test), roll back to v1 with one command (`make rollback VERSION=...`), and show `model/info` confirming the version and a smoke test passing. Record it (script plus terminal capture or screen recording) in `docs/ops/ROLLBACK_EVIDENCE.md`.
- **Post-deploy smoke test:** `make smoke` hits `/healthz`, runs a fixed scenario and checks its known `result_hash`, and verifies a refusal case still refuses.
- **Runbook (`docs/ops/RUNBOOK.md`):** start/stop, deploy, rollback, health interpretation, common failures (LLM API down or rate-limited, hash mismatch, slow responses, Auditor failure spike), config and secrets rotation, who to contact, and what the system does in each degraded mode (for example LLM down: the engine and UI still work; the agent panel shows a clear outage state rather than guessing).

---

## 10. Honesty (`docs/HONESTY.md` and in-UI panel)

State before the panel asks:
- **Limitations:** synthetic data, so no claim about real markets; simple elasticity model; no competitor reaction, distribution changes, brand effects or causal claims; intervals reflect parameter uncertainty only, not model misspecification.
- **What it deliberately refuses:** extrapolation, joint combinations never observed, non-observed pack sizes, ballpark estimates for refused scenarios, overriding assumptions outside valid range, following instructions found in scenario names or tool output.
- **Residual risk:** LLM could misinterpret an objective (mitigated by showing the parsed objective for confirmation); grounding check validates numbers but not whether prose reasoning is sound (mitigated by labels and the "Recommended" rule); the EDGE band thresholds are modelling choices.
- **Known defects and open items**, with honest numbers (for example plan stability is 80%, not 100%).

---

## 11. Added phases (extend PLAN.md section 18)

| # | Deliverable | Acceptance check |
|---|---|---|
| 0 | **Before any code:** repo standards (lint, format, pre-commit), `CLAUDE.md`, `.claude/settings.json` permissions and hooks, BRD v1 with ACs, DESIGN v1, first ADRs, TASKS.md, TEAM.md, CI skeleton | CI runs green on an empty skeleton; hooks demonstrably block a protected-path edit |
| 16 | README (setup, run, architecture diagram), HONESTY.md, clean-clone job, AC traceability test | Fresh clone to running demo with two commands, verified in CI |
| 17 | Eval gate in CI, baselines run, `reports/metrics.md` with baseline deltas, gate-blocks-regression demo | Deliberate regression branch is blocked |
| 18 | Security scans, triage, secrets in manager, agent boundary doc, threat model | Scans clear or risk-accepted; key absent from repo and logs |
| 19 | Containerisation, non-prod deploy, health checks, rollback, runbook, smoke test | Rollback demonstrated end to end |
| 20 | Submission pack and defence rehearsal | Section 12 checklist complete; two timed dry runs |

**Rough sequencing** (adapt to your calendar): Phase 0 first, then engine core (1-7) while D builds CI/Docker in parallel, then agent (10-13) while cloud agents generate eval and refusal sets, then evals (14, 17), then security and deploy (18, 19), with UI (8, 15) in parallel from the API schema. Freeze features a few days before the pitch; use the remainder for 16, 20 and rehearsal.

---

## 12. Pre-pitch submission checklist (`docs/SUBMISSION.md`)

Anything not submitted cannot be claimed, so verify each:

- [ ] Repository builds and runs from a clean clone; README has setup, run instructions and architecture diagram
- [ ] Spec pack: BRD with testable ACs, solution design, ADRs, sequenced task plan
- [ ] Agent engineering record: CLAUDE.md files, skills, hooks, CI gates in version control; review log and defect log
- [ ] Evaluation report: metrics, baselines, the evaluation set itself
- [ ] Security evidence: scan output and triage, secrets handling, agent access boundary
- [ ] Deployment evidence: non-prod deployment, health checks, demonstrated rollback, runbook
- [ ] Honesty statement (limitations, residual risk, deliberate refusals)
- [ ] Tool comparison note (Claude Code vs Codex), if claimed

---

## 13. Defence plan (20 minutes: 15 present, 5 Q&A; every member presents)

| Min | Segment | Presenter | Content |
|---|---|---|---|
| 0-2 | Business case | D (or whoever is strongest on business) | The decision-latency problem, who benefits, baseline (manual spreadsheet time) |
| 2-5 | **Live demo from a clean clone** | C drives | Goal to board, losing scenario, refusal under pressure, grounded badge. Have a recorded fallback clip in case of network failure |
| 5-8 | Engine and guardrails | B | Support envelope, joint-gap refusal vs naive baseline, determinism, performance numbers vs budget |
| 8-10 | Trust and data | A | Assumptions registry, validation, synthetic-data realism and limits |
| 10-12 | Agent and evaluation | C | Auditor, grounding, label scheme, eval results vs baselines, CI gate blocking a regression |
| 12-14 | Engineering, security, ops | D | Agent record (hooks blocking a bad edit, review log, defects caught), scan results, rollback demo |
| 14-15 | Honesty and close | A or D | Limitations, residual risk, what it refuses, V2/V3 |
| 15-20 | Q&A | All | Questions go to the owner of the area |

**Rehearsal rules:** two timed dry runs; each member answers three hostile questions on their own area without notes; practice "I don't know, here is how I'd find out" rather than bluffing. Likely panel challenges: "Why should I trust the synthetic data?", "What stops the agent making up a number?", "Show me a defect the agent introduced and how you caught it", "What happens when the LLM API is down?", "Why not just use a better ML model?", "How would this change with real client data?", "What did you change after review that the agent got wrong?"

---

## 14. Risk register (team-level)

| Risk | Mitigation |
|---|---|
| Scope too big for the calendar | Tiering and cut line (UI polish first to go); weekly checkpoint against TASKS.md |
| Live demo failure | Clean-clone rehearsal, recorded fallback, pre-warmed deployment, fake-LLM replay mode as a fallback |
| LLM API outage or rate limits | Replay mode from recorded traces; cached eval runs; degrade gracefully |
| Member can't explain code they merged | Ownership rule, random-file walkthrough drills |
| Evidence missing at submission | Phase 0 creates the empty evidence files; each phase's acceptance check includes updating them |
| Agents produce plausible but wrong code | Property tests, refusal suite, review log, hooks; record defects honestly |
