# Revenue_Growth_Sim
Simulator for volume and margin across price, pack, and promotion scenarios using synthetic elasticity data. State assumptions in the UI and code, prioritize scenario comparison—including losers—and explicitly block unsupported extrapolation beyond the data range.

Full spec: `docs/plan/PLAN.md` and `docs/plan/CAPSTONE_COMPLIANCE.md`. Architecture and stack decisions: `docs/spec/DESIGN.md` and `docs/spec/adr/`.

## Layout
- `backend/` — Python 3.11 engine, assumptions registry, API and agent (FastAPI).
- `frontend/` — React + Vite + TypeScript UI (Tailwind v4, shadcn/ui), calls the backend API.

## Dev setup (current state: Phase 0 skeleton, no feature code yet)
```
uv sync --extra dev && uv run pytest -q   # backend
cd frontend && npm install && npm run dev  # frontend (http://localhost:5173)
```
A one-command `make demo` (full clean-clone run) ships in Phase 16-17.
