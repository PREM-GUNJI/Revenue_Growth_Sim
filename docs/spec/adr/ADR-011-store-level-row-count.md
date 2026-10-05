# ADR-011: Store-level rows to match the brief's "~31k rows" and give the envelope real density

Status: accepted

Context: PLAN.md section 3 states the portfolio (12 SKUs) x 104 weeks x 3 regions, and separately states "about 31k rows." The literal product of those three dimensions is 3,744, not ~31k. Checking the support-envelope design (ADR-003): with 1,344 joint-coverage cells (12 price bins x 7 depth steps x 4 formats x 4 mechanics) over only 3,744 rows, the average cell count would be ~2.8 — below the REFUSED threshold (c<3) for nearly every cell, which would make almost the entire lever space REFUSED regardless of the deliberate gap, defeating the point of a density-based envelope.

Options considered:
- A. Generate literally 3,744 rows (SKU x region x week only) and accept that the envelope thresholds would need to be far looser to avoid blanket refusal.
- B. Add a "store" dimension (retailer-POS-style granularity, matching `CAPSTONE_COMPLIANCE.md`'s "retailer-POS-style format") purely as a row-count/density multiplier in the generator: price, promo and mechanic decisions are set once per (SKU, region, week) — centrally, as a retailer would actually set them — and only `units_sold` varies per store via idiosyncratic noise.

Decision: B, with 8 stores per region (12 x 104 x 3 x 8 = 29,952 rows, matching "about 31k" to within 3.5%). Stores are never a modeled lever: the Scenario schema, the engine and the agent's tools have no `store_id` field anywhere. Stores exist solely in `backend/data/generator.py` to produce realistic within-region volume dispersion and enough row density for the joint-coverage table's thresholds (REFUSED c<3, EDGE c<15/n<60) to behave as designed — dense cells mostly SUPPORTED, with GAP-1 standing out as the deliberate empty region.

Consequences: the dataset is denser and more realistic than a literal 3,744-row reading would have been, at the cost of a generator dimension not explicitly named in the brief. This is recorded here, in the generator's docstring, and in `data_manifest.json` (`stores_per_region`) so it is never silently assumed. If asked "why 8 stores and not the brief's literal dimensions," the answer is this ADR.

Owner / date: A/B (data+model+engine owner) / 2026-10-05
