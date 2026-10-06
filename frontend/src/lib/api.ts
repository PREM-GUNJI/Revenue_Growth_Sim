export interface ApiAssumption {
  id: string
  label: string
  value: unknown
  unit: string | null
  source: "data-derived" | "business-input" | "modelling-choice"
  rationale: string
  valid_range: [number, number] | null
}
export interface ApiBand { value: number; p10: number; p50: number; p90: number }
export interface ApiScenarioResult {
  scenario_id: string
  status: "SUPPORTED" | "EDGE" | "REFUSED"
  volume: Record<string, ApiBand>
  gsv: Record<string, ApiBand>
  nsv: Record<string, ApiBand>
  gp: Record<string, ApiBand>
  portfolio_gp: ApiBand | null
  bridge: Record<string, { price_cents: number; volume_cents: number; cross_pack_cents: number; promo_cents: number; trade_cents: number; cogs_cents: number; total_cents: number }>
  result_hash: string
  refusal_reasons: Array<{ sku_id: string; lever: string; message: string }>
  nearest_supported_scenario: ApiScenario | null
}
export interface ApiScenario {
  schema_version: number
  name: string
  levers: Record<string, { price_index: number; promo_depth_pct: number; mechanic: string; promo_weeks_per_month: number }>
  cost_shock: { aluminium_pct: number; pet_resin_pct: number; sugar_pct: number }
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api" + path, {
    ...init, headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error("API " + response.status + ": " + (detail || response.statusText))
  }
  return response.json() as Promise<T>
}
export function getAssumptions() { return request<ApiAssumption[]>("/assumptions") }
export function getModelInfo() {
  return request<{ engine_version: string; data_hash: string; model_spec_hash: string; deterministic: boolean }>("/model/info")
}
export function evaluateScenarios(scenarios: ApiScenario[], k = 200, seed = 42) {
  return request<ApiScenarioResult[]>("/scenarios/evaluate", { method: "POST", body: JSON.stringify({ scenarios, k, seed }) })
}
export function nearestSupported(scenario: ApiScenario) {
  return request<{ scenario: ApiScenario; scenario_id: string; distance: number; status: "SUPPORTED" | "EDGE" }>("/scenarios/nearest_supported", {
    method: "POST", body: JSON.stringify({ scenario }),
  })
}


export interface AgentClaim {
  claim_id: string
  text: string
  label: "Observed" | "Modeled" | "Assumed" | "Recommended"
  tool_call_id: string | null
  field_path: string | null
  references: string[]
}
export interface AgentToolEvent {
  call_id: string
  name: string
  arguments: Record<string, unknown>
  result: unknown
  result_hash: string
}
export interface AgentApiRun {
  trace_id: string
  model_id: string
  wall_time_ms: number
  model_time_ms: number
  tool_time_ms: number
  scenarios: ApiScenario[]
  answer: {
    summary: string
    recommendations: string[]
    refusals: string[]
    caveats: string[]
    claims: AgentClaim[]
  }
  audit: { passed: boolean; issues: string[]; numbers_checked: number }
  tool_events: AgentToolEvent[]
}
export function runAgent(goal: string) {
  return request<AgentApiRun>("/agent/run", {
    method: "POST", body: JSON.stringify({ goal }),
  })
}

export interface ResearchCandidateResponse {
  research: { methodology: string; research_id: string; sample_size: number; source_data_hash: string; result_hash: string }
  scenarios: Array<{ scenario: ApiScenario; scenario_id: string; status: "SUPPORTED" | "EDGE" | "REFUSED"; result_hash: string; provenance: { candidate: { price: number; pack: string }; research_id: string; methodology: string; model_version: string }; refusal_reasons: Array<{message: string}>; nearest_supported_scenario: ApiScenario | null }>
}
export function runResearchToScenarios(methodology = "Willingness to Pay") {
  return request<ResearchCandidateResponse>("/pricing/research-to-scenarios", {
    method: "POST", body: JSON.stringify({ methodology, seed: 42, sample_size: 250 }),
  })
}
