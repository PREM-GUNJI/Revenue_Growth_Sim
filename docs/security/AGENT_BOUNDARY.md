# Agent permission boundary

Placeholder (Phase 18, draft now since the boundary is an architectural decision made in Phase 0/`docs/spec/DESIGN.md`).

## Runtime agent (the LLM orchestrator, `backend/agent/`)
- **Allowed:** calls to the typed tool functions in `backend/agent/tools.py` only (`get_envelope`, `get_assumptions`, `get_model_info`, `evaluate_scenarios`, `sweep`, `nearest_supported`, `explain_scenario`, `run_sensitivity`, `calc`, `save_scenario`, `pareto_flags`).
- **Denied:** filesystem access, network access beyond the Anthropic API call itself, engine-internals access, reading `.env*` or any secret, arbitrary code execution. `calc` is an AST-whitelisted arithmetic evaluator, not `eval`.
- **Network policy:** the agent process makes outbound calls only to the Anthropic API endpoint; no other egress.

## Build-time agents (Claude Code sessions building this repo)
- Governed by `.claude/settings.json`: permission `deny` rules block Edit/Write on `.env*`, `reports/*.md` (generated, not hand-edited) and `tests/**/golden/**`; a `PreToolUse` hook on Bash blocks `git push --force`/`-f` and `rm -rf` outside the repo or targeting `.git`.
- Full permission model (sandbox, network, credentials) to be documented here as it's configured in later phases.

## What happens if the LLM API key leaks
No secret store is wired up yet (deployment is Phase 19), so this is the intended mechanism per `docs/spec/DESIGN.md`'s deploy decisions (Docker + compose on a local VM/host, ADR-008), not evidence of a past incident:

1. **Revoke** the leaked key immediately in the Anthropic Console (console.anthropic.com) — this invalidates it for every caller, including the running deployment.
2. **Issue a new key** in the Anthropic Console and store it as: `ANTHROPIC_API_KEY` in GitHub Actions secrets for CI; on the deploy host, an untracked `.env` file (already `.gitignore`d) that only `docker compose` reads at container start — Claude Code and the runtime agent are denied read access to any `.env*` path.
3. **Redeploy**: `docker compose up -d` (or the Phase 19 `make rollback`/redeploy target) to restart the API container with the new key picked up from `.env`. Rollback = swap the image tag; the key itself is never baked into an image layer.
4. **Audit for exposure**: grep every `trace.jsonl` under the trace store for the leaked key value — it must return zero matches, since the key is only ever used in the outbound Anthropic SDK client (`backend/agent`) and is never logged, never placed in a tool result, and never part of the system prompt or trace record. Also check CI logs and any `reports/*.md` for the same reason. A match in a trace would itself be a defect (log it in `docs/agent-record/DEFECTS.md`), since it means the key crossed a boundary it's designed never to cross.
5. **Confirm**: hit `/healthz`/`/readyz` post-redeploy and run the smoke test (`make smoke`, Phase 19) to confirm the new key is live and the degraded-LLM state has cleared.
