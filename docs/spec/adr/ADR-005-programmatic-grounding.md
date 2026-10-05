# ADR-005: Programmatic (not LLM-judged) grounding

Status: accepted

Context: The grounding check (does every number in the agent's answer trace to a tool result?) is itself a claim the panel will stress-test ("what stops the agent making up a number?"). An LLM-as-judge grounding check is itself an LLM that can be fooled, miscounts decimals, or drifts between runs.

Options considered:
- A. LLM-as-judge: ask a second model "are all numbers in this answer grounded?"
- B. Deterministic parser: the agent writes numeric placeholders bound to tool-result paths; a renderer substitutes them; any literal number remaining in prose is parsed and matched by rounding tolerance against tool/`calc` leaves.

Decision: B, detailed in `simulator/agent/grounding.py` design notes in `docs/spec/DESIGN.md` and `PLAN.md` section 11.

Consequences: 100% reproducible pass/fail, no model-variance in the audit itself. It cannot catch *wrong reasoning expressed in correctly-grounded numbers* (e.g. citing a real number in a misleading frame) — this residual risk is stated in `docs/HONESTY.md` and mitigated separately by the Observed/Modeled/Assumed/Recommended label rules (ADR enforced by the Auditor, not this check).

Owner / date: C (agent owner) / 2026-10-05
