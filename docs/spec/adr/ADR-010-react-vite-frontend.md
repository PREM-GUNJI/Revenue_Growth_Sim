# ADR-010: React + Vite + TypeScript + shadcn/ui frontend (supersedes ADR-009)

Status: accepted (supersedes ADR-009)

Context: ADR-009 chose a server-rendered FastAPI + Jinja2 + HTMX UI so the 3-person team would work in one language end to end. The user later asked explicitly for a React + Vite frontend using shadcn/ui components, reversing that preference.

Options considered:
- A. Keep HTMX/Jinja2 (ADR-009).
- B. React + Vite + TypeScript, styled with Tailwind v4 and shadcn/ui components (Radix primitives + Tailwind, copied into the repo rather than installed as an opaque dependency).

Decision: B. The frontend lives in `frontend/` and the Python side lives in `backend/` (renamed from `simulator/` at the user's request so the two top-level directories read as plain `frontend`/`backend`, matching `docs/plan/PLAN.md` section 17's intent of one directory per side). `frontend/` is a standalone Vite app that calls the FastAPI backend (`backend/api`) over HTTP, proxied through Vite's dev server at `/api` during development and served as a static build in production (`deploy/`). shadcn/ui was chosen over a pre-built admin-dashboard template because its components are copied into `frontend/src/components/ui/` as plain editable code (via the `shadcn` CLI), not an opaque npm dependency — this fits the comparison-first UI's specific needs (scenario tray, comparison table, refusal cards) better than reskinning a generic dashboard template.

Consequences: The team now spans Python (`backend/`: engine/agent) and TypeScript (`frontend/`) after all; `npm audit` is back in scope for Phase 18 security scanning (reversing ADR-009's removal of it). Playwright now drives the built React app instead of server-rendered HTML — mechanically similar, same AC-024. `docs/spec/DESIGN.md`, root `CLAUDE.md`, `docs/TEAM.md` and `docs/plan/CAPSTONE_COMPLIANCE.md`'s traceability table are updated to point at `frontend/`/`backend/` instead of `simulator/web/`/`simulator/`. The meeting-mode sliders (PLAN.md section 14 V2) are implemented as React client state with debounced API calls rather than debounced HTMX requests.

Owner / date: D (platform/UI owner) / 2026-10-05
