// Mirrors the engine's Scenario/Result shape from backend/engine (PLAN.md section 7, 14).
// Real values arrive from POST /api/scenarios/evaluate once Phase 6-8 lands;
// this shell renders against MOCK_SCENARIOS (see lib/mock-data.ts) until then.

export type ScenarioStatus = "SUPPORTED" | "EDGE" | "REFUSED"

export interface ScenarioDelta {
  volumePct: number
  revenuePct: number
  marginPct: number
  marginPpt: number
}

export interface ScenarioResult {
  scenarioId: string
  name: string
  status: ScenarioStatus
  isBaseline?: boolean
  isAgentProposed?: boolean
  delta?: ScenarioDelta
  p10?: ScenarioDelta
  p90?: ScenarioDelta
  assumptionIds?: string[]
  refusalReason?: string
  nearestSupportedId?: string
}

export interface Assumption {
  id: string
  label: string
  value: string
  unit?: string
  source: "data-derived" | "business-input" | "modelling-choice"
  rationale: string
  validRange?: string
}
