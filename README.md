# Revenue_Growth_Sim
Simulator for volume and margin across price, pack, and promotion scenarios using synthetic elasticity data. State assumptions in the UI and code, prioritize scenario comparisonâ€”including losersâ€”and explicitly block unsupported extrapolation beyond the data range.

Full spec: `docs/plan/PLAN.md` and `docs/plan/CAPSTONE_COMPLIANCE.md`. Architecture and stack decisions: `docs/spec/DESIGN.md` and `docs/spec/adr/`.

## Layout
- `backend/` â€” Python 3.11 engine, assumptions registry, API and agent (FastAPI).
- `frontend/` â€” React + Vite + TypeScript UI (Tailwind v4, shadcn/ui), calls the backend API.

## Quickstart (clean clone)

Two commands bring up the full demo (API + UI) from a fresh clone — this is
exactly what `.github/workflows/clean_clone.yml` runs headlessly on every
push/PR (AC-025):
```powershell
uv run python -m tasks demo
```
```powershell
npm --prefix frontend install ; npm --prefix frontend run dev
```
The API serves on `http://localhost:8000` (`/healthz`, `/assumptions`); the UI on `http://localhost:5173`.

## Dev setup

Run backend commands in PowerShell:
```powershell
uv sync --extra dev
uv run pytest -q
uv run uvicorn backend.api.main:app --reload
```

In a second PowerShell terminal, run the frontend:
```powershell
Set-Location frontend
npm install
npm run dev  # http://localhost:5173
```

Run the API with `uv run uvicorn backend.api.main:app --reload` (default: `http://localhost:8000`).
The backend supports assumptions and envelope inspection, scenario evaluation and sweeps, nearest-supported suggestions, and deterministic scenario export/import. Run `uv run python -m tasks bench` to measure the budgets in `docs/plan/PLAN.md` section 8.

Deployment (containerisation, rollback) is scheduled for a later phase; see `docs/HONESTY.md` for exactly what is real vs. scaffolded today. Demand outputs use documented assumptions and synthetic data; they are not fitted forecasts.

## Sign-in

The app requires sign-in (ADR-014). Users live in the `users` table; create or reset one with:

```powershell
python -m backend.dbsetup                      # applies migrations, including 002_users
python -m backend.auth_users someone@c5i.ai    # prompts for a password, stores only its Argon2 hash
```

Set `AUTH_SECRET_KEY` (see `.env.example`) for any shared deployment, and `AUTH_COOKIE_SECURE=1` behind HTTPS.

## Workspaces, governance pages and AI cost

After signing in, `/` is the hub: shared scenario workspaces (autosaved, with conflict protection). The sidebar also has the **Agent runs** history and the **Audit and AI usage** page. A workspace can be exported as a PowerPoint from its header. AI cost is tokens times the rates in `backend/ai_pricing.py`; update them (and `RATE_VERSION`) when the provider changes prices. See ADR-015.

## PostgreSQL and environment configuration

1. Copy `.env.example` to `.env` and replace the local database password (and add provider API keys only when needed).
2. Start PostgreSQL with `docker compose up -d db`.
3. Install/update backend dependencies with `uv sync --extra dev`.
4. Start the API with `uv run uvicorn backend.api.main:app --reload`.

The API loads `.env` for local development. `GET /database/health` reports connection status. `POST /scenario-runs` evaluates and saves one run; `GET /scenario-runs` lists the latest saved runs. The database tables are created on first use. OpenAI defaults to model `gpt-5.5`; provider integration remains a later phase.

## Synthetic consumer evidence (supporting layer)

The system uses synthetic consumer evidence as an upstream decision-support layer. Consumer research generates candidate prices/configurations, while the deterministic RGM engine remains the source of truth for modeled volume, revenue and margin.

```
Synthetic consumers -> WTP / Gabor-Granger / Van Westendorp / Conjoint simulation
  -> candidate price / pack / promotion -> support envelope -> deterministic engine
  -> volume / revenue / margin -> comparison board -> decision
```

- Code: `backend/research/evidence.py`. Research parameters are registry assumptions A-026..A-037; every research result carries a `research_id`, source data hash and result hash, and every candidate scenario carries the full provenance chain (research_id, methodology, sample/data hash, candidate, scenario_id, model version, assumptions, result_hash).
- API: `POST /pricing/consumer-summary`, `/pricing/research`, `/pricing/research-to-scenarios`, `/pricing/conjoint`, `/pricing/conjoint-to-scenarios`, `GET /pricing/conjoint/defaults`.
- Agent tools: `get_pricing_methodologies`, `get_consumer_evidence`, `run_wtp`, `run_gabor_granger`, `run_van_westendorp`, `run_conjoint_simulation`, `research_to_scenarios`. The agent cannot supply utilities or willingness-to-pay values.
- UI: Overview, Scenario simulator (Price, Pack, Promotion levers and joint presets), Comparison board, AI decision assistant, plus the supporting Pricing evidence and Conjoint simulation workspaces.
- Tests: `tests/research/`, `tests/agent/test_research_agent.py`, `tests/api/test_research_endpoints.py` (AC-028..AC-033). Decision record: `docs/spec/adr/ADR-013-synthetic-consumer-evidence-layer.md`.

Limitations, stated plainly:
- Consumer data is synthetic and so are the comments; they are not real customers or real research.
- Research outputs are illustrative. No real consumer research is claimed and no causal claims are made.
- Conjoint uses supplied utilities: it simulates choices and does not estimate or fit utilities.
- No ML demand model is used. Nothing is trained or fitted.
- The existing support-envelope limits still apply, so some research candidates are REFUSED with no numbers.
- Research prices are in INR and indexed to a registry reference price per pack; the engine's currency is abstract.

## Worked examples

<!-- BEGIN GENERATED WORKED EXAMPLES -->
### Engine: price vs. promo on one SKU

Generated by `scripts/generate_readme_examples.py` against the real engine (`evaluate_batch`, K=200 draws, seed=1000). Figures are Modeled, not observed — every number traces to `backend.engine.batch.evaluate_batch`.

| Scenario | Status | Portfolio GP (central / p10 / p90) |
|---|---|---|
| Baseline | SUPPORTED | 19,727 (p10 19,727 / p90 19,727) |
| +5% price on Aurora can | SUPPORTED | 19,734 (p10 19,722 / p90 19,782) |
| 20% TPR promo on Aurora can | SUPPORTED | 19,942 (p10 19,801 / p90 20,108) |
| Price index 3.0 on Aurora can (out of range) | REFUSED | no numeric fields (Aurora-can_330ml: price_index 1.8 outside observed 1st-99th percentile [0.9459, 1.1200]) |

### Agent: same scenarios, through the agent loop

Generated by the same script, running the scripted deterministic agent (`AgentOrchestrator` + `ScriptedLLM`, same tools a live Claude/OpenAI run uses) over the same four scenarios. Every claim below is grounded and labelled by the real Auditor, not typed by hand.

- Auditor verdict: **PASSED**

| Claim | Label |
|---|---|
| the top-ranked scenario has modeled portfolio gross profit 19941.9. | Modeled |
| Prefer the top-ranked scenario when portfolio gross profit is the priority. | Recommended |

<!-- END GENERATED WORKED EXAMPLES -->
