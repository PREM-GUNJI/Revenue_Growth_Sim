import type { Provenance } from "@/lib/api"
// UI-facing comparison types; backend payload types are defined in lib/api.ts.
export type ScenarioStatus = "SUPPORTED" | "EDGE" | "REFUSED"
export interface ScenarioDelta {
  volumePct: number
  revenuePct: number
  marginPct: number
  marginPpt: number
}
export interface ScenarioResult {
  scenarioId: string
  resultHash?: string
  source?: Provenance
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
