# Runbook

Placeholder (Phase 19). Fill in with real commands once `deploy/` exists.

- **Start/stop:** `docker compose up -d` / `docker compose down` (TBD, Phase 19).
- **Deploy:** `make deploy VERSION=<git-sha>` (TBD).
- **Rollback:** `make rollback VERSION=<prior-git-sha>` (TBD) — see `docs/ops/ROLLBACK_EVIDENCE.md`.
- **Health interpretation:** `/healthz` = process alive; `/readyz` = model/registry/envelope loaded and data hash matches manifest (LLM reachability is a degraded-not-fatal check).
- **Common failures:**
  - LLM API down or rate-limited: engine and UI keep working; agent panel shows an explicit outage state.
  - Hash mismatch: `/readyz` fails; check `model/info` against the manifest.
  - Slow responses: check `reports/metrics.md` benchmark deltas before assuming infra.
  - Auditor failure spike: check `trace.jsonl` for the failing run; replay it with `make replay`.
- **Config and secrets rotation:** TBD, Phase 18/19.
- **Contact:** project owners in `docs/TEAM.md`.
