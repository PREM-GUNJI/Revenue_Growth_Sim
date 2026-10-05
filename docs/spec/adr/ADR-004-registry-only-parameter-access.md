# ADR-004: Registry-only parameter access

Status: accepted

Context: Magic constants scattered through engine code are undocumented, untested and invisible to the UI/agent, which breaks the "assumptions stated in interface and code" brief requirement and makes assumption-coverage unmeasurable.

Options considered:
- A. Constants as module-level Python values, documented in comments.
- B. A config file (YAML/JSON) read once at startup, no access tracking.
- C. A typed `Assumption` registry (`id, label, value, unit, source, rationale, valid_range`) accessed only via `registry.get("A-xxx")`, with every read recorded for a coverage test.

Decision: C. See `docs/plan/PLAN.md` section 5. The same registry feeds the engine, the API (`GET /assumptions`), the UI drawer, the README's generated examples and the agent's explanations — one source, no documentation drift.

Consequences: Every new engine parameter requires a registry entry with a rationale and range before it can be used; a build fails if the engine reads outside the registry (coverage = 100% by construction, AC-005). Slightly more ceremony per parameter, in exchange for the assumption-documentation-coverage metric being trivially true rather than aspirational.

Owner / date: A (data+model owner) / 2026-10-05
