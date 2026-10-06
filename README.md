# Revenue_Growth_Sim
Simulator for volume and margin across price, pack, and promotion scenarios using synthetic elasticity data. State assumptions in the UI and code, prioritize scenario comparisonâ€”including losersâ€”and explicitly block unsupported extrapolation beyond the data range.

Full spec: `docs/plan/PLAN.md` and `docs/plan/CAPSTONE_COMPLIANCE.md`. Architecture and stack decisions: `docs/spec/DESIGN.md` and `docs/spec/adr/`.

## Layout
- `backend/` â€” Python 3.11 engine, assumptions registry, API and agent (FastAPI).
- `frontend/` â€” React + Vite + TypeScript UI (Tailwind v4, shadcn/ui), calls the backend API.

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

The clean-clone demo, live model-provider integration, and deployment are scheduled for later phases. Demand outputs use documented assumptions and synthetic data; they are not fitted forecasts.

## PostgreSQL and environment configuration

1. Copy `.env.example` to `.env` and replace the local database password (and add provider API keys only when needed).
2. Start PostgreSQL with `docker compose up -d db`.
3. Install/update backend dependencies with `uv sync --extra dev`.
4. Start the API with `uv run uvicorn backend.api.main:app --reload`.

The API loads `.env` for local development. `GET /database/health` reports connection status. `POST /scenario-runs` evaluates and saves one run; `GET /scenario-runs` lists the latest saved runs. The database tables are created on first use. OpenAI defaults to model `gpt-5.5`; provider integration remains a later phase.
