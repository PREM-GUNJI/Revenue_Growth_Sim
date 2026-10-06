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
export interface ApiBridge { price_cents: number; volume_cents: number; cross_pack_cents: number; promo_cents: number; trade_cents: number; cogs_cents: number; total_cents: number }
export interface ApiScenarioResult {
  scenario_id: string
  status: "SUPPORTED" | "EDGE" | "REFUSED"
  volume: Record<string, ApiBand>
  gsv: Record<string, ApiBand>
  nsv: Record<string, ApiBand>
  gp: Record<string, ApiBand>
  portfolio_gp: ApiBand | null
  bridge: Record<string, ApiBridge>
  result_hash: string
  refusal_reasons: Array<{ sku_id: string; lever: string; message: string }>
  nearest_supported_scenario: ApiScenario | null
}
export interface ApiLever { price_index: number; promo_depth_pct: number; mechanic: string; promo_weeks_per_month: number }
/** `source` is UI-only provenance; it is stripped before a scenario is sent to the engine. */
export interface ApiScenario {
  schema_version: number
  name: string
  levers: Record<string, ApiLever>
  cost_shock: { aluminium_pct: number; pet_resin_pct: number; sugar_pct: number }
  source?: Provenance
}

export interface ResearchCandidate { pack: string; price: number; promotion_depth_pct: number; source_metric: string; brand?: string }
export interface Provenance {
  label: string
  research_id: string
  methodology: string
  sample_size: number
  source_data_hash: string
  research_result_hash: string
  candidate_index: number
  candidate: ResearchCandidate
  scenario_id: string
  model_version: string
  research_assumption_ids: string[]
  engine_assumption_ids: string[]
  result_hash: string
}
export interface ResearchResultApi {
  label: string
  methodology: string
  research_id: string
  sample_size: number
  inputs: Record<string, unknown>
  outputs: Record<string, unknown>
  candidates: ResearchCandidate[]
  assumptions: string[]
  assumption_ids: string[]
  limitations: string[]
  source_data_hash: string
  result_hash: string
  statement?: string
}
export interface ResearchScenarioRow extends ApiScenarioResult { scenario: ApiScenario; provenance: Provenance }
export interface ResearchBridgeResponse { research: ResearchResultApi; label: string; scenarios: ResearchScenarioRow[] }
export interface ConsumerSummary {
  label: string
  sample_size: number
  data_hash: string
  segments: Record<string, { count: number; mean_price_sensitivity: number; mean_promotion_sensitivity: number }>
  wtp_by_pack: Record<string, { respondents: number; mean_wtp: number }>
  sample_comments: Array<{ respondent_id: string; segment: string; comment: string }>
  note: string
}
export interface ConjointAlternative { brand: string; pack: string; price: number; promotion: string }
export interface EvidenceDefaults {
  label: string
  statement: string
  utilities: Record<string, unknown>
  brands: string[]
  packs: string[]
  promotions: string[]
  reference_prices: Record<string, number>
  default_alternatives: ConjointAlternative[]
}
export interface EnvelopeInfo {
  price_index_p1_p99: Record<string, [number, number]>
  promo_depth_observed: Record<string, [number, number]>
  formats: string[]
  mechanics: string[]
  depth_steps: number[]
  own_elasticity_assumption_by_format: Record<string, string>
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
const post = <T,>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) })
const forEngine = (scenarios: ApiScenario[]) => scenarios.map(({ source: _source, ...scenario }) => scenario)

export function getAssumptions() { return request<ApiAssumption[]>("/assumptions") }
export function getModelInfo() {
  return request<{ engine_version: string; data_hash: string; model_spec_hash: string; deterministic: boolean }>("/model/info")
}
export function getEnvelope() { return request<EnvelopeInfo>("/envelope") }
export function evaluateScenarios(scenarios: ApiScenario[], k = 200, seed = 42) {
  return post<ApiScenarioResult[]>("/scenarios/evaluate", { scenarios: forEngine(scenarios), k, seed })
}
export function nearestSupported(scenario: ApiScenario) {
  return post<{ scenario: ApiScenario; scenario_id: string; distance: number; status: "SUPPORTED" | "EDGE" }>(
    "/scenarios/nearest_supported", { scenario: forEngine([scenario])[0] })
}

export interface AgentClaim {
  claim_id: string
  text: string
  label: "Observed" | "Modeled" | "Assumed" | "Recommended"
  tool_call_id: string | null
  field_path: string | null
  references: string[]
  research_id?: string | null
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
export function runAgent(goal: string) { return post<AgentApiRun>("/agent/run", { goal }) }

// Supporting synthetic consumer evidence. Research proposes candidates; the engine decides outcomes.
export function getEvidenceDefaults() { return request<EvidenceDefaults>("/pricing/conjoint/defaults") }
export function getConsumerSummary(seed = 42) { return post<ConsumerSummary>("/pricing/consumer-summary", { seed }) }
export function runResearch(methodology: string, pack: string, seed = 42) {
  return post<ResearchResultApi>("/pricing/research", { methodology, pack, seed })
}
export function researchToScenarios(methodology: string, pack: string, promotion_depth_pct = 0, seed = 42) {
  return post<ResearchBridgeResponse>("/pricing/research-to-scenarios", { methodology, pack, promotion_depth_pct, seed })
}
export function conjointToScenarios(alternatives: ConjointAlternative[], focus_brand: string, seed = 42) {
  return post<ResearchBridgeResponse>("/pricing/conjoint-to-scenarios", { alternatives, focus_brand, seed })
}
