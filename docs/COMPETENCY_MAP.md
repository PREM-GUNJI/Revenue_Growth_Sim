# Competency map

Maps the program's capability families to where they show up in this build (`docs/plan/CAPSTONE_COMPLIANCE.md` section 3). Fill in the exact day-to-competency mapping from the program schedule once available.

| Capability family | Where it shows up | Status |
|---|---|---|
| Spec-driven development (BRD, design, task plan) | `docs/spec/` | done (Phase 0) |
| Agent instruction engineering (CLAUDE.md, skills, hooks) | `CLAUDE.md`, `.claude/` | done (Phase 0) |
| Agentic system design (tools, roles, guardrails) | `simulator/agent/` | pending (Phase 10-13) |
| Evaluation and baselines | `agent_evals/`, `reports/metrics.md` | pending (Phase 14) |
| Guardrails and safe failure | Support envelope, Auditor, refusal integrity | pending (Phase 5, 12) |
| Observability and reproducibility | Traces, hashes, replay, health endpoints | pending (Phase 6, 13) |
| Security (scanning, secrets, permission boundary, prompt injection) | `docs/security/` | pending (Phase 18) |
| CI/CD and gates | `.github/workflows/` | started (Phase 0 skeleton) |
| Deployment and operations | `deploy/`, `docs/ops/` | pending (Phase 19) |
| Multi-agent / parallel delegation and tool comparison | cloud-agent tasks (optional), Codex comparison (optional) | not planned by default — see `docs/spec/TASKS.md` |
