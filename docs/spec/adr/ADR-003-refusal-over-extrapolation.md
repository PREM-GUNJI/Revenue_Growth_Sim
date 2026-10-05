# ADR-003: Refusal over extrapolation, with a joint-density check

Status: accepted

Context: Per-lever range checks alone miss combinations that are individually in-range but jointly never observed (e.g. deep promo at a high price index) — a classic silent-extrapolation trap.

Options considered:
- A. Per-lever min/max only (naive baseline, kept for comparison in `docs/plan/CAPSTONE_COMPLIANCE.md` section 4).
- B. A convex-hull membership test.
- C. A binned joint-occupancy count (own-cell count plus a neighbourhood count only for EDGE downgrade), REFUSED/EDGE/SUPPORTED.

Decision: C. Full design in `docs/spec/DESIGN.md` and the engine's `support.py`. Neighbour counts are used only to downgrade SUPPORTED→EDGE, never to upgrade a REFUSED cell — otherwise the deliberately-seeded data gaps would be smoothed away by their dense neighbours.

Consequences: Thresholds (minimum count for REFUSED, minimum count/neighbourhood for EDGE) are themselves registry assumptions with a cost in false refusals; this tradeoff is measured in the refusal suite's precision/recall (AC-011) and discussed under Subject Matter Q&A prep. A convex hull would pass some gap cells that are inside the hull but empty; the binned count catches those by construction.

Owner / date: B (engine owner) / 2026-10-05
