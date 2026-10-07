import type { Provenance } from "@/lib/api"
// UI-facing comparison types; backend payload types are defined in lib/api.ts.
export type ScenarioStatus = "SUPPORTED" | "EDGE" | "REFUSED"
export interface ScenarioDelta {
  volumePct: number
  revenuePct: number
  marginPct: number
  marginPpt: number
}
/** The focal brand's absolute figures for one scenario, INR per typical week (units for volume). */
export interface ScenarioAbsolute {
  units: number
  revenue: number
  nsv: number
  gp: number
  marginPct: number
  /** Valid P10 and P90 of the brand's total gross profit (from per-draw sums). */
  gpRange: [number, number]
  /** Change in gross profit against the baseline, INR per week, with its P10 and P90. */
  gpChange: number
  gpChangeRange: [number, number]
}
/** The focal brand's profit walk against the baseline, INR per week; the parts add up to `total`. */
export interface ScenarioBridge { price: number; volume: number; crossPack: number; promo: number; trade: number; cogs: number; total: number }
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
  abs?: ScenarioAbsolute
  bridge?: ScenarioBridge
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
  /** Where a reader can check the choice, or a plain statement that no external source exists. */
  reference?: string
}
