import type { Assumption, ScenarioResult } from "./types"

// Placeholder board: one baseline, one winner, one deliberate loser and one
// refused scenario — the minimum shape PLAN.md section 10/14 requires.
// Swap for a real POST /api/scenarios/evaluate call in Phase 8.
export const MOCK_SCENARIOS: ScenarioResult[] = [
  {
    scenarioId: "baseline",
    name: "Baseline (current prices)",
    status: "SUPPORTED",
    isBaseline: true,
  },
  {
    scenarioId: "a1b2c3",
    name: "+4% price, 500ml PET",
    status: "SUPPORTED",
    delta: { volumePct: -3.2, revenuePct: 0.7, marginPct: 2.1, marginPpt: 0.6 },
    p10: { volumePct: -4.5, revenuePct: -0.2, marginPct: 1.0, marginPpt: 0.2 },
    p90: { volumePct: -1.9, revenuePct: 1.6, marginPct: 3.2, marginPpt: 1.0 },
    assumptionIds: ["A-003", "A-017"],
  },
  {
    scenarioId: "d4e5f6",
    name: "Deep promo, BOGO, 6x330ml multipack",
    status: "SUPPORTED",
    delta: { volumePct: 11.4, revenuePct: -2.8, marginPct: -9.6, marginPpt: -3.1 },
    p10: { volumePct: 8.0, revenuePct: -4.9, marginPct: -12.5, marginPpt: -4.0 },
    p90: { volumePct: 14.1, revenuePct: -0.6, marginPct: -6.8, marginPpt: -2.2 },
    assumptionIds: ["A-009", "A-012", "A-021"],
  },
  {
    scenarioId: "g7h8i9",
    name: "-30% price with 30% promo depth",
    status: "REFUSED",
    refusalReason:
      "Price index 0.70 is outside the observed 1st-99th percentile (0.88-1.12) for this SKU.",
    nearestSupportedId: "nearest-g7h8i9",
  },
]

export const MOCK_ASSUMPTIONS: Assumption[] = [
  {
    id: "A-003",
    label: "Own-price elasticity, 500ml PET",
    value: "-1.4",
    source: "modelling-choice",
    rationale: "Typical CPG range -0.8 to -2.5; mid-size format, mid elasticity.",
    validRange: "-2.0 to -0.9",
  },
  {
    id: "A-009",
    label: "BOGO promo mechanic multiplier",
    value: "1.4",
    source: "modelling-choice",
    rationale: "BOGO drives the largest lift of the three modelled mechanics.",
    validRange: "1.2 to 1.6",
  },
  {
    id: "A-012",
    label: "Post-promo pull-forward share",
    value: "0.2",
    source: "modelling-choice",
    rationale: "15-25% of lift is pulled forward from future weeks.",
    validRange: "0.15 to 0.25",
  },
  {
    id: "A-017",
    label: "Retailer hurdle margin",
    value: "25%",
    source: "business-input",
    rationale: "Standard retailer minimum margin requirement.",
  },
  {
    id: "A-021",
    label: "No competitor reaction",
    value: "assumed",
    source: "modelling-choice",
    rationale: "Out of scope for this engine; stated in docs/HONESTY.md.",
  },
]
