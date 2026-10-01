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
To be filled in Phase 18 alongside the secrets-handling section — expected answer: rotate the key in the secret manager, redeploy, and check `trace.jsonl` files for the key (it must never appear there since it's never passed to the model or logged).
