# ADR-017: Viewer, Analyst and Admin roles, enforced on the server

Status: accepted (fully built)

Context: Every signed-in user saw everything: the four-step workbench, the synthetic research pages, the audit trail and AI cost. Executives only need the decision, and governance data is not for every user. ADR-015 noted that the audit pages stay open to all "until roles exist".

Decision:
- `users.role` is one of `viewer`, `analyst` or `admin` (migration 005). Existing users and new users without an explicit role are `analyst`, which is the access they had before. `python -m backend.auth_users EMAIL --role admin` sets it; resetting a password without `--role` keeps the role.
- `/auth/me` and the login response return the role. `require_role(...)` in `backend/auth.py` gives HTTP 403 when the role is not allowed. The check is on the server; hiding links in the UI is a convenience, not the control.
- **Viewer** is read-only. They can list and open cases, evaluate scenarios, and export the deck or brief. Creating, renaming, archiving or editing a case, running the AI assistant (which spends tokens), saving scenario runs, and the synthetic research and persona endpoints all return 403. In the UI a viewer sees Home and the Executive brief; opening a case goes straight to the brief.
- **Analyst** has the workbench: the four steps, the brief, and the research pages behind the "Advanced research" switch.
- **Admin** has everything an analyst has, plus `/audit/log`, `/audit/ai-usage` and `/agent/runs*` and their pages.

Consequences:
- No role management UI: roles are set with the CLI, like passwords. There is still one shared pool of cases; roles control what a person may do, not which cases they see.
- Engine-only endpoints (`/scenarios/evaluate`, sensitivity, goal-seek, sweep) stay open to viewers because the brief needs them and they change nothing.
- The engine, agent and the claim-label rules are unchanged.

Owner / date: user / 2026-10-28
