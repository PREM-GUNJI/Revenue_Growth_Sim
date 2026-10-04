# Security scan triage

Each finding from `pip-audit`, `bandit`, `gitleaks`, `trivy` gets one row: fixed, or explicitly risk-accepted with rationale, owner and expiry. `trivy` (container scan) has no row yet — it scans the built image, which lands in Phase 19.

Scans run 2026-10-05 against this branch (`uv run bandit -r backend -c pyproject.toml`, `uv run pip-audit`):

| Tool | Finding | Severity | Status | Rationale / expiry | Owner |
|---|---|---|---|---|---|
| bandit 1.9.4 | B101 `assert_used` at `backend/model/spec.py:47` — `assert len(DRAWABLE_ASSUMPTION_IDS) == len(set(DRAWABLE_ASSUMPTION_IDS)) == 12` | Low (confidence High) | **Fixed** (Phase 4) | Replaced the `assert` with an explicit `if ... : raise ValueError(...)`, so the invariant still holds under `python -O`. | A/B (model) |
| pip-audit 2.9.0 | None — `No known vulnerabilities found` across all resolved dependencies | — | Clear | Re-run on every `security` CI job (see `.github/workflows/ci.yml`); `revenue-growth-sim` itself is skipped from the PyPI check since it's the local project, not a published dependency — expected, not a gap | — |
| gitleaks v8.18.4 | None found in pre-commit runs to date; CI step added this phase (`gitleaks/gitleaks-action@v3.0.0`) so secret scanning isn't local-only | — | Clear | CI step scans full git history (`fetch-depth: 0`) on every push/PR, not just pre-commit's staged diff | D |
