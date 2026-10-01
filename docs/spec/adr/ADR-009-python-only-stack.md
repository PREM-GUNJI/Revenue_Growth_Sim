# ADR-009: Python-only stack (FastAPI + Jinja2 + HTMX, no Node/React)

Status: accepted

Context: `docs/plan/PLAN.md` section 1 specifies React + Vite + TypeScript + Recharts for the UI, with Streamlit + Plotly as a fallback. The user explicitly asked for a Python backend and, on follow-up, confirmed they want the UI in Python too so the 3-person team never has to touch TypeScript/Node.

Options considered:
- A. React + Vite + TS + Recharts (the spec's default): richer client-side interactivity (meeting-mode sliders, trade-off plane), but a second language/toolchain and `npm audit` surface.
- B. Streamlit + Plotly (the spec's own fallback): fast to build, weaker for fine-grained live sliders and for Playwright-style structural testing.
- C. FastAPI + Jinja2 + HTMX, server-rendered: one language end to end, ordinary Playwright testing against real DOM/HTML, debounced HTMX requests make the meeting-mode sliders and visible compute-time budget demonstrable without a SPA build step.

Decision: C.

Consequences: `docs/plan/PLAN.md` section 1 and section 14 (React/Recharts, `npm audit`) are superseded for this build; `docs/spec/DESIGN.md` and root `CLAUDE.md` are the current source of truth for the stack. Playwright drives the server-rendered pages directly (no React component testing). The V2 "meeting mode" sliders are implemented as debounced HTMX requests rather than client-side state.

Owner / date: D (platform/UI owner) / 2026-10-05
