# ADR-008: Deployment target and rollback strategy

Status: accepted

Context: The program requires a demonstrated non-prod deployment with health checks and a rollback. The team has no cloud billing account set up and wants to avoid that dependency for a capstone (vs. a production system).

Options considered:
- A. Cloud Run / Render / Fly.io (first-class revision-based rollback, but needs a cloud account and billing).
- B. Local VM / host running docker compose, rollback by swapping the image tag.

Decision: B, chosen with the user. Images are tagged by git SHA (`model/info` reports the running model/data hash so every deployed version is identifiable); `make rollback VERSION=<sha>` redeploys the prior tag via compose.

Consequences: Weaker "real infra" evidence than a cloud revision rollback, but fully sufficient to demonstrate the required rollback mechanics (deploy v2 with a deliberately bad change that fails `/readyz`, roll back to v1, confirm via smoke test) without a cloud dependency. Recorded in `docs/ops/ROLLBACK_EVIDENCE.md`.

Owner / date: D (platform owner) / 2026-10-05
