import type { ApiAssumption, ApiScenario, ApiScenarioResult } from "@/lib/api"
import { baselineLever, newScenario, skuFor, sum } from "@/lib/catalog"
import type { Assumption, ScenarioDelta, ScenarioResult } from "@/lib/types"

const CAN = skuFor("can_330ml")
export const initialScenarios: ApiScenario[] = [
  newScenario("Baseline"),
  newScenario("+4% price, Aurora can", { [CAN]: { ...baselineLever, price_index: 1.04 } }),
  newScenario("Promotion scenario", { [CAN]: { ...baselineLever, promo_depth_pct: 20, mechanic: "TPR", promo_weeks_per_month: 3 } }),
  newScenario("Competitive price defense", { [CAN]: { ...baselineLever, price_index: 0.96 } }),
  newScenario("Out-of-range price", { [CAN]: { ...baselineLever, price_index: 1.5 } }),
]
const totalAt = (values: ApiScenarioResult["volume"], edge: "value" | "p10" | "p90") => sum(values, edge)
export function asUiAssumption(item: ApiAssumption): Assumption {
  return {
    id: item.id, label: item.label,
    value: typeof item.value === "string" ? item.value : JSON.stringify(item.value),
    unit: item.unit ?? undefined, source: item.source, rationale: item.rationale,
    validRange: item.valid_range ? String(item.valid_range[0]) + " to " + String(item.valid_range[1]) : undefined,
  }
}
export function toUiResults(raw: ApiScenarioResult[], inputs: ApiScenario[]): ScenarioResult[] {
  const base = raw[0]
  const baseVolume = sum(base.volume), baseRevenue = sum(base.gsv), baseGp = sum(base.gp), baseNsv = sum(base.nsv)
  return raw.map((result, index) => {
    const input = inputs[index]
    const common = { scenarioId: result.scenario_id, resultHash: result.result_hash, name: input.name, status: result.status, isBaseline: index === 0, source: input.source }
    if (result.status === "REFUSED") {
      return {
        ...common,
        refusalReason: result.refusal_reasons.map((reason) => reason.message).join("; "),
        refusals: result.refusal_reasons.map((r) => ({ skuId: r.sku_id, lever: r.lever, requested: r.requested, range: r.supported_range, message: r.message })),
        nearestSupportedId: result.nearest_supported_scenario ? "nearest-" + result.scenario_id : undefined,
      }
    }
    const delta = (volume: number, revenue: number, gp: number, nsv: number): ScenarioDelta => ({
      volumePct: baseVolume ? (volume / baseVolume - 1) * 100 : 0,
      revenuePct: baseRevenue ? (revenue / baseRevenue - 1) * 100 : 0,
      marginPct: baseGp ? (gp / baseGp - 1) * 100 : 0,
      marginPpt: (nsv ? gp / nsv * 100 : 0) - (baseNsv ? baseGp / baseNsv * 100 : 0),
    })
    const at = (edge: "value" | "p10" | "p90") => delta(totalAt(result.volume, edge), totalAt(result.gsv, edge), totalAt(result.gp, edge), totalAt(result.nsv, edge))
    return { ...common, delta: at("value"), p10: at("p10"), p90: at("p90") }
  })
}

/** The scenario with the best gross-profit move that keeps volume loss within the guardrail; refused scenarios never qualify. */
export function pickBest(results: ScenarioResult[], guardrailPct: number): ScenarioResult | undefined {
  return results.filter((item) => item.status !== "REFUSED" && !item.isBaseline && item.delta && item.delta.volumePct >= -guardrailPct)
    .sort((a, b) => (b.delta?.marginPct ?? -Infinity) - (a.delta?.marginPct ?? -Infinity))[0]
}
