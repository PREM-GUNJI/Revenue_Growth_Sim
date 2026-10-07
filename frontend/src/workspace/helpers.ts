import type { ApiAssumption, ApiScenario, ApiScenarioResult, SituationTotals } from "@/lib/api"
import { baselineLever, newScenario, skuFor } from "@/lib/catalog"
import type { Assumption, ScenarioAbsolute, ScenarioBridge, ScenarioDelta, ScenarioResult } from "@/lib/types"

const CAN = skuFor("can_330ml"), BOTTLE = skuFor("bottle_1500ml"), MULTIPACK = skuFor("multipack_6x330ml")
const promo = (depth: number, weeks = 2) => ({ ...baselineLever, promo_depth_pct: depth, mechanic: "TPR", promo_weeks_per_month: weeks })

/** Starting scenarios for a new case: a clear winner, a combination, a loser for contrast, and one request the engine refuses. */
export const initialScenarios: ApiScenario[] = [
  newScenario("Baseline"),
  newScenario("Take price on the 1.5 L bottle", { [BOTTLE]: { ...baselineLever, price_index: 1.03 } }),
  newScenario("Promote the can", { [CAN]: promo(10) }),
  newScenario("Price up on large packs, promote the can", { [BOTTLE]: { ...baselineLever, price_index: 1.03 }, [MULTIPACK]: { ...baselineLever, price_index: 1.03 }, [CAN]: promo(10) }),
  newScenario("Raise the can price", { [CAN]: { ...baselineLever, price_index: 1.04 } }),
  newScenario("Out-of-range can price", { [CAN]: { ...baselineLever, price_index: 1.5 } }),
]

export function asUiAssumption(item: ApiAssumption): Assumption {
  return {
    id: item.id, label: item.label,
    value: typeof item.value === "string" ? item.value : JSON.stringify(item.value),
    unit: item.unit ?? undefined, source: item.source, rationale: item.rationale,
    validRange: item.valid_range ? String(item.valid_range[0]) + " to " + String(item.valid_range[1]) : undefined,
    reference: item.reference ?? undefined,
  }
}

const pct = (value: number, base: number) => (base ? (value / base - 1) * 100 : 0)

function bridgeOf(result: ApiScenarioResult): ScenarioBridge | undefined {
  const b = result.focal_bridge
  if (!b) return undefined
  const r = (cents: number) => cents / 100
  return { price: r(b.price_cents), volume: r(b.volume_cents), crossPack: r(b.cross_pack_cents), promo: r(b.promo_cents), trade: r(b.trade_cents), cogs: r(b.cogs_cents), total: r(b.total_cents) }
}

/**
 * Turns engine results into what the pages show. Everything is about the focal brand (Aurora) and is measured
 * against the engine's own zero-change baseline, not against whichever scenario happens to be listed first.
 * Ranges are the engine's bands for the brand's total, never sums of per-pack bands.
 */
export function toUiResults(raw: ApiScenarioResult[], inputs: ApiScenario[], baseline: SituationTotals): ScenarioResult[] {
  return raw.map((result, index) => {
    const input = inputs[index]
    const common = { scenarioId: result.scenario_id, resultHash: result.result_hash, name: input.name, status: result.status, isBaseline: index === 0, source: input.source, assumptionIds: result.assumption_ids }
    if (result.status === "REFUSED") {
      return {
        ...common,
        refusalReason: result.refusal_reasons.map((reason) => reason.message).join("; "),
        refusals: result.refusal_reasons.map((r) => ({ skuId: r.sku_id, lever: r.lever, requested: r.requested, range: r.supported_range, message: r.message })),
        nearestSupportedId: result.nearest_supported_scenario ? "nearest-" + result.scenario_id : undefined,
      }
    }
    const f = result.focal
    const delta = (volume: number, revenue: number, gp: number, nsv: number): ScenarioDelta => ({
      volumePct: pct(volume, baseline.units),
      revenuePct: pct(revenue, baseline.gsv),
      marginPct: pct(gp, baseline.gp),
      marginPpt: (nsv ? gp / nsv * 100 : 0) - baseline.gp_margin_pct,
    })
    const at = (edge: "value" | "p10" | "p90") => delta(f.volume[edge], f.gsv[edge], f.gp[edge], f.nsv[edge])
    const abs: ScenarioAbsolute = {
      units: f.volume.value, revenue: f.gsv.value, nsv: f.nsv.value, gp: f.gp.value,
      marginPct: f.nsv.value ? f.gp.value / f.nsv.value * 100 : 0,
      gpRange: [f.gp.p10, f.gp.p90],
      gpChange: f.gp.value - baseline.gp,
      gpChangeRange: [f.gp.p10 - baseline.gp, f.gp.p90 - baseline.gp],
    }
    return { ...common, delta: at("value"), p10: at("p10"), p90: at("p90"), abs, bridge: bridgeOf(result) }
  })
}

/** The scenario with the best gross-profit move that keeps volume loss within the guardrail; refused scenarios never qualify. */
export function pickBest(results: ScenarioResult[], guardrailPct: number): ScenarioResult | undefined {
  return results.filter((item) => item.status !== "REFUSED" && !item.isBaseline && item.delta && item.delta.volumePct >= -guardrailPct)
    .sort((a, b) => (b.delta?.marginPct ?? -Infinity) - (a.delta?.marginPct ?? -Infinity))[0]
}
