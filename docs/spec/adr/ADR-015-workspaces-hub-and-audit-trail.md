# ADR-015: Shared scenario workspaces, a project hub homepage, and an audit trail

Status: accepted (fully built)

Context: The app held one implicit scenario set per browser tab and had no landing page. The user asked for a central homepage with multiple scenario workspaces, usable by business users and reviewers, with the audit trail and AI usage cost on a separate page rather than the homepage.

Decision:
- Workspaces are named scenario sets, **shared by every signed-in user** (creator and last editor recorded). Archive instead of delete, so nothing is lost.
- Scenario edits autosave one second after the last change with an optimistic `version`; a stale save gets HTTP 409 and the UI stops saving and says who changed it, rather than overwriting.
- An `activity_log` table records who did what (sign-in, failed sign-in, workspace create/rename/archive/edit). It stores actions and ids only, never scenario contents, passwords or tokens. Autosaves are coalesced to one row per user and workspace per 15 minutes. A failure to write an audit row is logged and never breaks the request.
- The homepage (`/`) shows workspaces only; the AI decision assistant lives inside each workspace. Audit rows and AI cost are deliberately kept off it; they live on `/audit`.
- Navigation moves to a left sidebar with real URLs (`react-router-dom`): `/`, `/w/:id/{simulator,board,assistant,evidence,conjoint}`.
- Homepage status reads existing artefacts: `reports/agent_evals.json` is judged with the same rule as `agent_evals/run_evals.py`, and `reports/engine_bench.md` is reported as written. Failing benchmark sizes are shown, not hidden.

Consequences:
- The database is required for workspaces, as it already is for sign-in. Engine, agent and the engine tests still run without it.
- A workspace card's headline margin is computed by calling the engine on its saved scenarios; the UI never calculates it. REFUSED scenarios cannot become a headline.
- Collaboration is last-writer-protected, not merged: two people editing the same workspace at once will see a conflict, not a combined result.
- The docs and evidence library was built and then removed at the owner's request; there is no library page or endpoint.
- **Agent run history** (`/agent/runs`, `/agent/runs/{id}`): lists runs from the audit trail and returns a trimmed saved trace (tool names, ids and hashes, the labelled answer and the auditor's verdict, never raw tool results). The id must be 32 lowercase hex characters and the resolved file must sit directly inside the trace directory.
- **AI usage and cost** (`/audit/ai-usage`): `OpenAILLM` adds up the tokens of every call a run makes; `/agent/run` writes one `ai_usage` row even when a later call fails. Cost is tokens times the rates in `backend/ai_pricing.py` (gpt-5.5 Standard tier, $5.00 input, $0.50 cached input, $30.00 output per 1M tokens, from the provider's pricing page fetched 2026-10-07), computed server-side and stored with its `rate_version`. A model with no rate is stored with cost NULL and shown as "rate not set", never as $0. Scripted runs record 0 tokens.
- **Export** (`POST /workspaces/{id}/export`): a PowerPoint built from `evaluate_batch` at request time. A refused scenario appears with its refusal reasons and no figures; if the baseline is refused there are no comparisons at all. Scenario ids and result hashes are on a traceability slide.
- Rates change. Update `RATES` and bump `RATE_VERSION` when they do; old rows keep the version they were priced with. The pricing summary came from a fetched page, so check it against the provider's page before relying on a figure for billing.
- The audit and AI-usage pages are visible to every signed-in user until roles exist.

Owner / date: user / 2026-10-07
