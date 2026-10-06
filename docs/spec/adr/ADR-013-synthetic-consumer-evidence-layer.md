# ADR-013: Synthetic consumer evidence as an upstream candidate generator

Status: accepted

Context: the user asked for synthetic consumer evidence, pricing-research methods (WTP, Gabor-Granger, Van Westendorp), a conjoint *simulation*, and a bridge from those into the existing Price + Pack + Promotion simulator, without changing the core scope in `docs/plan/PLAN.md`.

Decision: research is an upstream layer that only *proposes candidate prices/configurations*. Every candidate becomes an ordinary `Scenario`, passes the existing support envelope, and is evaluated by the existing deterministic engine. Research never writes volume, revenue or margin.

Consequences:
- No ML, no fitting, no utility estimation. WTP/GG/VW are descriptive rules over synthetic respondents. Conjoint is a multinomial-logit *simulation* over part-worths supplied through the registry (A-037).
- Research parameters live in the assumptions registry (A-026..A-037). Generator-only inputs that shape the synthetic respondents follow the existing `GENERATOR_SEED` precedent (`CONSUMER_GENERATOR_SEED`, no assumption id, never read by the engine).
- Refusal is unchanged: an unsupported candidate is REFUSED with no numbers and a separate nearest-supported alternative; it is never clamped.
- Research-derived agent claims are `Modeled` claims that cite a research tool call and carry the `research_id`. A `Recommended` claim must reference an engine-modeled claim; research evidence alone cannot back a recommendation.
- Research prices are INR and indexed to a registry reference price per pack (A-028..A-031) to obtain the engine's `price_index`. The engine's own currency stays abstract; the UI never mixes the two.
- Scope decision on "pack": the engine has per-SKU levers over four observed formats and no pack-swap lever, so "pack decisions" are expressed as relative price/promotion positioning across observed formats (for example, take price on the 330 ml can while making the 500 ml cheaper). Cannibalization is read from the engine's per-SKU volumes and `cross_pack_cents`.

Owner / date: user / 2026-10-07
