import { AuthError, UNAUTHORIZED_EVENT } from "@/lib/auth"

export interface ApiAssumption {
  id: string
  label: string
  value: unknown
  unit: string | null
  source: "data-derived" | "business-input" | "modelling-choice"
  rationale: string
  valid_range: [number, number] | null
  /** Where a reader can check the choice, or a plain statement that no external source exists. */
  reference: string | null
}
export interface ApiBand { value: number; p10: number; p50: number; p90: number }
export interface ApiBridge { price_cents: number; volume_cents: number; cross_pack_cents: number; promo_cents: number; trade_cents: number; cogs_cents: number; total_cents: number }
/** The focal brand's totals. Bands come from per-draw sums, so they are valid ranges for the total. Empty if refused. */
export type ApiFocal = Record<"volume" | "gsv" | "nsv" | "gp", ApiBand>
export interface ApiScenarioResult {
  scenario_id: string
  status: "SUPPORTED" | "EDGE" | "REFUSED"
  focal: ApiFocal
  volume: Record<string, ApiBand>
  gsv: Record<string, ApiBand>
  nsv: Record<string, ApiBand>
  gp: Record<string, ApiBand>
  /** All three brands together. The focal brand's figures are the ones to decide on. */
  portfolio_gp: ApiBand | null
  /** Registry assumptions this result depends on. */
  assumption_ids?: string[]
  /** The focal brand's profit bridge in hundredths of a rupee; the parts add up exactly to total_cents. */
  focal_bridge?: ApiBridge | null
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
  promo_depth_observed: number[]
  formats: string[]
  mechanics: string[]
  depth_steps: number[]
  own_elasticity_assumption_by_format: Record<string, string>
}

/** An API failure that keeps its HTTP status, so callers can react to e.g. 404 or 409. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string, message: string) { super(message); this.name = "ApiError"; this.status = status; this.detail = detail }
}
function detailOf(text: string): string {
  try {
    const parsed = JSON.parse(text) as { detail?: unknown }
    return typeof parsed.detail === "string" ? parsed.detail : text
  } catch {
    return text
  }
}

export async function request<T>(path: string, init?: RequestInit, onResponse?: (response: Response) => void): Promise<T> {
  const response = await fetch("/api" + path, {
    ...init, headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (response.status === 401) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    throw new AuthError()
  }
  if (!response.ok) {
    const detail = await response.text()
    throw new ApiError(response.status, detailOf(detail) || response.statusText, "API " + response.status + ": " + (detail || response.statusText))
  }
  onResponse?.(response)
  return response.json() as Promise<T>
}
const post = <T,>(path: string, body: unknown, onResponse?: (response: Response) => void) => request<T>(path, { method: "POST", body: JSON.stringify(body) }, onResponse)
const forEngine = (scenarios: ApiScenario[]) => scenarios.map(({ source: _source, ...scenario }) => scenario)

export function getAssumptions() { return request<ApiAssumption[]>("/assumptions") }
export function getModelInfo() {
  return request<{ engine_version: string; data_hash: string; model_spec_hash: string; deterministic: boolean }>("/model/info")
}
export function getEnvelope() { return request<EnvelopeInfo>("/envelope") }
/** `onEngineMs` receives the server's own compute time for the batch (not the network round trip). */
export function evaluateScenarios(scenarios: ApiScenario[], k = 200, seed = 42, onEngineMs?: (ms: number) => void) {
  return post<ApiScenarioResult[]>("/scenarios/evaluate", { scenarios: forEngine(scenarios), k, seed }, onEngineMs
    ? (response) => { const ms = Number(response.headers.get("X-Engine-Ms")); if (Number.isFinite(ms)) onEngineMs(ms) }
    : undefined)
}

export interface SituationProbe {
  status: "SUPPORTED" | "EDGE" | "REFUSED"
  reasons?: string[]
  scenario_id?: string
  focal_volume_pct?: number | null
  focal_gsv_pct?: number | null
  focal_gp_change?: number
  focal_gp_pct?: number | null
  focal_gp_change_p10?: number
  focal_gp_change_p90?: number
  pack_volume_pct?: number | null
}
export interface SituationTotals { units: number; litres: number; gsv: number; trade: number; nsv: number; cogs: number; gp: number; gp_margin_pct: number }
export interface SituationSku {
  sku_id: string; brand: string; format: string; pack_size_l: number; is_focal: boolean
  price: number; price_per_litre: number; price_range: [number, number]
  baseline_units: number; baseline_gsv: number; baseline_trade: number; baseline_nsv: number; baseline_cogs: number; baseline_gp: number; gp_margin_pct: number
  history: { promo_week_share_pct: number; avg_promo_depth_pct: number; main_mechanic: string }
  own_elasticity: number; own_elasticity_id: string
  price_gap_vs_competitors_pct: Record<string, number | null> | null
  price_probe?: SituationProbe
  promo_probe?: SituationProbe
}
/** Where the focal brand stands today, and what the engine says about a few small moves. */
export interface Situation {
  currency: string
  focal_brand: string
  competitors: string[]
  period: { basis: string; history_weeks: number; regions: string[]; stores_per_region: number; rows: number; generator_version: string }
  data_hash: string
  skus: SituationSku[]
  totals: { focal: SituationTotals; by_brand: Record<string, SituationTotals>; market: SituationTotals; focal_value_share_pct: number }
  cost_shock_probe: SituationProbe & { shock_pct: number; applies_to: string }
  probe_definitions: { price: string; promo: string }
  assumption_ids: string[]
  labels: Record<string, "Observed" | "Modeled" | "Assumed">
}
export function getSituation() { return request<Situation>("/situation") }
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
export function runAgent(goal: string, workspaceId?: string) { return post<AgentApiRun>("/agent/run", { goal, workspace_id: workspaceId ?? null }) }

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
