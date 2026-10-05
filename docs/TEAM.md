# Team ownership (3-person variant)

Per `docs/plan/CAPSTONE_COMPLIANCE.md` section 2's 3-person variant: A and B are merged into one data+model+engine owner; the agent panel UI moves from D to C (see plan correction #12 in `docs/spec/DESIGN.md`'s history / the approved implementation plan).

| Member | Owns | Defends at the panel | Key artifacts |
|---|---|---|---|
| **A/B: Data, model and engine** | Synthetic generator, parametric demand spec, assumptions registry, back-test/sensitivity report, PII scan, batch engine, support envelope and refusal, API, hashing/reproducibility, benchmarks | "Why trust these numbers? Why synthetic, and is it realistic? How do you refuse correctly? Is it fast and deterministic?" | `simulator/data/`, `simulator/model/`, `simulator/assumptions/`, `simulator/engine/`, `simulator/api/`, refusal suite, benchmark gate |
| **C: Agent and evaluation** | Orchestrator, tools, Auditor, grounding and labels, traces and replay, agent evals, baselines, agent panel UI | "How do you know the agent never invents numbers? What happens under pressure or injection?" | `simulator/agent/`, `agent_evals/`, `reports/metrics.md` |
| **D: Platform, security, UI and ops** | Repo standards, CI/CD, hooks and permission boundary, scans, secrets, Docker and deployment, rollback and runbook, comparison UI (tray/table/refusal cards/drawer) | "Is it secure and operable? Show me rollback." | `.github/`, `deploy/`, `docs/security/`, `docs/ops/`, `simulator/web/` |

**Rule:** every PR names its owner and reviewer in `docs/agent-record/REVIEW_LOG.md`. The owner must be able to explain every line merged in their area without the agent — rehearse with a random-file walkthrough before submission.
