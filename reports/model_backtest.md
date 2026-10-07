# Model back-test and sensitivity report

**This is a consistency check, not a validation of real-world accuracy.** The data generator (`backend/data/generator.py`) and the engine's demand spec (`backend/model/spec.py`) share the exact same assumption values (`backend/assumptions/assumptions.py`). A back-test here can only confirm that the implementation reproduces its own generating model within the data's noise level — it says nothing about real-world accuracy, which would require real data and a calibration step (see docs/HONESTY.md).

## Back-test: last 13 weeks, held out from the baseline-volume calculation's own averaging window only in the sense that each week is predicted from the *window average* baseline, not from itself alone

- Points: 260 (13 weeks x 20 SKUs)
- MAPE (central-draw prediction vs actual national weekly volume): 5.9%
- P10-P90 band coverage (K=200 draws): 50.0%

Known limitation: the week immediately after a real promo event carries the generator's pull-forward dip, which isn't separately observable in the aggregated national weekly series used here, so those specific weeks carry above-average error. This is a modelling simplification of the back-test reconstruction, not a bug in the engine's scenario-evaluation formula (which receives `weeks_per_month` explicitly and does not need to infer it).

## Sensitivity (one-at-a-time tornado)

Metric: total portfolio volume at a reference stress scenario (+8% price and a half-month, 15%-depth promo on every SKU, mechanics cycled across SKUs), varying one assumption at a time across its registry `valid_range` (k=50 draws), others held at their central value. Spread is reported as % change relative to the central-value metric, since the reference scenario has no baseline-volume scale of its own (Phase 4 adds margin, which gives sensitivity a real-dollar scale).

| Rank | Assumption | Label | Spread (% of central) |
|---|---|---|---|
| 1 | A-008 | Promo lift scale (b_promo) | 19.1% |
| 2 | A-007 | Promo depth saturation rate | 11.9% |
| 3 | A-006 | Cross-price elasticity, across-brand | 9.8% |
| 4 | A-005 | Cross-price elasticity, within-brand (different format) | 4.6% |
| 5 | A-010 | Promo mechanic multiplier, feature & display | 1.7% |
| 6 | A-012 | Post-promo pull-forward share | 1.6% |
| 7 | A-011 | Promo mechanic multiplier, BOGO | 1.5% |
| 8 | A-002 | Own-price elasticity, 500ml PET | 1.1% |
| 9 | A-001 | Own-price elasticity, 330ml can | 1.1% |
| 10 | A-003 | Own-price elasticity, 1.5L sharing bottle | 1.0% |
| 11 | A-004 | Own-price elasticity, 6x330ml multipack | 0.6% |
| 12 | A-009 | Promo mechanic multiplier, TPR (temporary price reduction) | 0.0% |

**Ranking stability across seeds (1000 vs 2000): stable (identical order).**

## Baseline volumes (data-derived, national units/week, last 13 weeks de-trended)

| SKU | Baseline volume |
|---|---|
| Aurora-can_330ml | 3,785.6 |
| Aurora-pet_500ml | 3,017.6 |
| Aurora-bottle_1500ml | 1,388.7 |
| Aurora-multipack_6x330ml | 868.0 |
| Boreal-can_330ml | 3,665.8 |
| Boreal-pet_500ml | 3,000.7 |
| Boreal-bottle_1500ml | 1,271.2 |
| Boreal-multipack_6x330ml | 904.2 |
| Comet-can_330ml | 3,593.8 |
| Comet-pet_500ml | 3,190.3 |
| Comet-bottle_1500ml | 1,187.4 |
| Comet-multipack_6x330ml | 929.5 |
| Delta-can_330ml | 4,166.2 |
| Delta-pet_500ml | 3,101.7 |
| Delta-bottle_1500ml | 1,284.4 |
| Delta-multipack_6x330ml | 904.3 |
| Ember-can_330ml | 4,102.7 |
| Ember-pet_500ml | 3,240.3 |
| Ember-bottle_1500ml | 1,362.1 |
| Ember-multipack_6x330ml | 887.2 |
