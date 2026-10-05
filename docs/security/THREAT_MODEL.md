# Threat model (STRIDE-style)

Placeholder (Phase 18). Draft rows below; fill in mitigations as each phase lands.

| Threat | Category | Mitigation |
|---|---|---|
| Prompt injection via scenario names | Tampering/Elevation | Scenario names and tool output are treated as data, never instructions (`docs/spec/DESIGN.md` trust boundaries); tested with AC-019 |
| Tool-output injection (malicious content returned from a tool) | Tampering | Tools only return typed, schema-validated Pydantic results; no free-form tool output reaches the system prompt |
| LLM API key leakage | Information disclosure | Key held only in a secret manager / untracked `.env`; never logged or placed in `trace.jsonl` |
| Data tampering (modified Parquet/manifest) | Tampering | Data hash in the manifest is checked at `/readyz`; mismatch is a degraded-not-fatal health signal |
| Denial of service via large scenario batches | Denial of service | `/scenarios/evaluate` capped at 10,000; rate/size limits enforced at the API layer (Phase 6) |
| Secrets committed to the repo | Information disclosure | `gitleaks` in pre-commit and CI; `.gitignore` excludes `.env*` |
