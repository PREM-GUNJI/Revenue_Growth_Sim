# Case hub + workbench UX (industry polish)

## Status
Implemented (hub starters + stepped New case; workbench KPI/step rail/board/recommend). Verified: `tsc -b`, oxlint (no new errors), e2e smoke 5 passed.

## Goal
Raise visual impact and guided creation for the Revenue Growth Simulator without changing engine behaviour. Keep C5i purple + navy ink.

## Phase A — Home + New case
- Example starter chips that pre-fill market / template / pack / cost.
- New case as Market → Decision → Details steps with option-count preview.
- Richer case cards: market badge, hero GP when available, clearer meta.

## Phase B — Workbench
- Stronger sticky decision-step rail.
- Situation KPI strip already present — tighten visual weight (hero GP card).
- Comparison board: clearer winner/refusal hierarchy.
- Recommend: keep ink hero; improve spacing and case meta.

## References
Linear (calm density), Stripe (hierarchy), Amplitude (starters), Datadog (KPI + status colour).

## Out of scope
New markets, engine changes, full dark-mode flip of the workbench.
