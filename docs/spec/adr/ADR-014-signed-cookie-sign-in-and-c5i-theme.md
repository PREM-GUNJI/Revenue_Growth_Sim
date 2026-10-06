# ADR-014: Sign-in with a signed httpOnly session cookie; C5i theme

Status: accepted

Context: The app had no authentication: every API route, including `/agent/run`, was open to anyone who could reach the port. The user asked for a login page (from the C5i login design), three named accounts, and the C5i look across the whole app. Neither `CLAUDE.md` nor `docs/spec/DESIGN.md` anticipated a user store or sessions.

Options considered:
- A. JWT kept in `localStorage`. Rejected: readable by any XSS, which conflicts with the security intent of `CAPSTONE_COMPLIANCE.md`.
- B. Server-side session table. Rejected for now: more moving parts than three users justify.
- C. Stateless signed cookie (itsdangerous) checked against the `users` table on every request. `httpOnly`, `SameSite=Lax`, `Secure` when `AUTH_COOKIE_SECURE` is set. Passwords stored only as Argon2 hashes.

Decision: C, via `backend/auth.py`. A FastAPI app-level dependency (`require_user`) protects every route; only `/auth/login`, `/healthz` and `/readyz` are public. Users live in a new `users` table (migration `002_users`). Login is throttled (5 failures per email in 15 minutes, then 429) and unknown emails cost the same hashing time as wrong passwords. The frontend shows the login page until `/auth/me` succeeds and falls back to it on any 401.

Consequences:
- The database is now required for sign-in. The engine, agent and existing test suite still run without it: `tests/conftest.py` overrides `require_user`, and tests marked `real_auth` (`tests/api/test_auth.py`) exercise the real check against in-memory SQLite.
- Sessions are stateless, so sign-out clears the cookie but does not revoke a copied token before it expires (12 h, or 30 days with "Keep me signed in"). Deactivating a user (`is_active = false`) takes effect on the next request.
- `AUTH_SECRET_KEY` must be set for any shared deployment. If unset, a local key is generated in `.auth_dev_secret` (gitignored) so dev reloads keep sessions.
- The throttle is in-process memory: fine for one worker, not shared across workers or restarts.
- Real team email addresses are the sign-in identities. `CLAUDE.md` forbids real customer data and PII in the project; these are staff accounts, held only in the operator's own database as email plus hash, and no email or password is committed. They are created with `python -m backend.auth_users EMAIL`, never from a file in the repo.
- Theme: the colour tokens in `frontend/src/index.css` follow the C5i design tokens (purple scale, neutrals, status colours, Inter). Components keep using semantic tokens (`primary`, `ink`, `gain`, `loss`, `edge`), so the palette is changed in one place.

Owner / date: user / 2026-10-07
