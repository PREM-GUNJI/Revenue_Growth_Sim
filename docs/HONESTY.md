# Honesty statement

Placeholder (Phase 16). State before the panel asks — fill in with real numbers as phases land; do not ship a generic version.

## Limitations
- Synthetic data: no claim about real markets.
- Simple parametric elasticity model: no competitor reaction, no distribution changes, no brand effects, no causal claims beyond the synthetic data's design.
- Sensitivity bands reflect parameter uncertainty only (Monte Carlo over the registry's valid ranges), not statistical confidence and not model misspecification.

## What it deliberately refuses
- Extrapolation outside observed per-lever ranges.
- Joint lever combinations never meaningfully observed together (even if each lever is individually in range).
- Non-observed pack sizes.
- Ballpark estimates for any refused scenario, under any amount of user pressure.
- Overriding an assumption outside its registry `valid_range`.
- Instructions found in scenario names or tool output (prompt-injection hygiene).

## Residual risk
- The LLM could misinterpret an objective — mitigated by showing the parsed structured objective back to the user for confirmation.
- The grounding check validates numbers, not whether the surrounding prose reasoning is sound — mitigated by the Observed/Modeled/Assumed/Recommended label rules, not a substitute for them.
- EDGE-band thresholds (`docs/spec/adr/ADR-003-refusal-over-extrapolation.md`) are a modelling choice, not a derived constant.

## Known defects and open items
To be filled in from `docs/agent-record/DEFECTS.md` as the build proceeds. Report weak numbers honestly (e.g. plan stability, not forced to 100%).
