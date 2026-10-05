# ADR-001: Agent never computes numbers; engine is the sole source of truth

Status: accepted

Context: An LLM agent that reasons over pricing/margin tradeoffs is tempted to do arithmetic in prose, which is unverifiable and occasionally wrong. The business and program requirement is that every number be defensible.

Options considered:
- A. Let the LLM compute freely and spot-check with a judge model.
- B. Force every number through typed tools over a deterministic engine, with a programmatic grounding check.
- C. Hybrid: LLM computes simple deltas, tools for everything else.

Decision: B. The LLM never computes, estimates or recalls a number; every number traces to a tool result or a whitelisted `calc` over tool results (`docs/plan/PLAN.md` section 11).

Consequences: Harder prompt engineering (the agent must be steered to call tools for trivial arithmetic), but grounding becomes mechanically checkable rather than judgment-based. This is the single most load-bearing decision in the project and is enforced by the Auditor.

Owner / date: C (agent owner) / 2026-10-05
