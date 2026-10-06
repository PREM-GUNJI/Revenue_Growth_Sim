# Revenue_Growth_Sim
Simulator for volume and margin across price, pack, and promotion scenarios using synthetic elasticity data. State assumptions in the UI and code, prioritize scenario comparisonâ€”including losersâ€”and explicitly block unsupported extrapolation beyond the data range.

Full spec: `docs/plan/PLAN.md` and `docs/plan/CAPSTONE_COMPLIANCE.md`. Architecture and stack decisions: `docs/spec/DESIGN.md` and `docs/spec/adr/`.

## Layout
- `backend/` â€” Python 3.11 engine, assumptions registry, API and agent (FastAPI).
- `frontend/` â€” React + Vite + TypeScript UI (Tailwind v4, shadcn/ui), calls the backend API.

## Dev setup
```
uv sync --extra dev && uv run pytest -q   # backend
cd frontend && npm install && npm run dev  # frontend (http://localhost:5173)
```
Run the API with `uv run uvicorn backend.api.main:app --reload` (default: `http://localhost:8000`).
The backend supports assumptions and envelope inspection, scenario evaluation and sweeps, nearest-supported suggestions, and deterministic scenario export/import. Run `uv run python -m tasks bench` to measure the budgets in `docs/plan/PLAN.md` section 8.

The clean-clone demo, generated worked examples, agent flow, and deployment are scheduled for later phases. Demand outputs use documented assumptions and synthetic data; they are not fitted forecasts.
