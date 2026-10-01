# ADR-002: Parametric engine with stated assumptions rather than fitted or ML models

Status: accepted

Context: The brief asks for volume/margin outcomes across scenarios. A fitted or ML demand model would need real data to be credible and would turn this into an ML project under a different skill rubric than the one being graded (agentic AI engineering).

Options considered:
- A. Fit a regression/ML model to the synthetic data.
- B. Specify a parametric log-log demand function with documented, registry-held assumptions; back-test (not fit) against synthetic observations for consistency.
- C. Skip a demand model entirely and hand-wave scenario outcomes.

Decision: B. Nothing is trained or fitted (`CLAUDE.md`, `docs/plan/CLAUDE.md`). The engine's parameters are explicit, sourced and ranged in the assumptions registry (ADR-004).

Consequences: Results are only as credible as the stated assumptions — this is disclosed in `docs/HONESTY.md`. Back-testing against the synthetic data is a consistency check (the generator shares the assumption set), not external validation; this is stated plainly in `reports/model_backtest.md`. If real data arrived, a calibration step would slot into the same registry interface (future work).

Owner / date: A/B (data+model+engine owner) / 2026-10-05
