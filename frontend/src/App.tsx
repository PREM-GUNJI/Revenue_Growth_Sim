import { useEffect, useState } from "react"
import { AgentPanel } from "@/components/agent-panel"
import { AppFooter } from "@/components/app-footer"
import { AssumptionsDrawer } from "@/components/assumptions-drawer"
import { ComparisonBoard } from "@/components/comparison-board"
import { AnalyticsViews, type HeatCell } from "@/components/analytics-views"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { evaluateScenarios, getAssumptions, getModelInfo, nearestSupported } from "@/lib/api"
import type { ApiAssumption, ApiScenario, ApiScenarioResult } from "@/lib/api"
import type { Assumption, ScenarioDelta, ScenarioResult } from "@/lib/types"

const SKU = "Aurora-can_330ml"
const initialScenarios: ApiScenario[] = [
  { schema_version: 1, name: "Baseline", levers: {}, cost_shock: { aluminium_pct: 0, pet_resin_pct: 0, sugar_pct: 0 } },
  { schema_version: 1, name: "+4% price, Aurora can", levers: { [SKU]: { price_index: 1.04, promo_depth_pct: 0, mechanic: "none", promo_weeks_per_month: 0 } }, cost_shock: { aluminium_pct: 0, pet_resin_pct: 0, sugar_pct: 0 } },
  { schema_version: 1, name: "Promotion scenario", levers: { [SKU]: { price_index: 1, promo_depth_pct: 20, mechanic: "TPR", promo_weeks_per_month: 3 } }, cost_shock: { aluminium_pct: 0, pet_resin_pct: 0, sugar_pct: 0 } },
  { schema_version: 1, name: "Out-of-range price", levers: { [SKU]: { price_index: 1.5, promo_depth_pct: 0, mechanic: "none", promo_weeks_per_month: 0 } }, cost_shock: { aluminium_pct: 0, pet_resin_pct: 0, sugar_pct: 0 } },
]
function total(values: Record<string, { value: number }>) {
  return Object.values(values).reduce((sum, band) => sum + band.value, 0)
}
function totalAt(values: Record<string, { p10: number; p90: number }>, edge: "p10" | "p90") {
  return Object.values(values).reduce((sum, band) => sum + band[edge], 0)
}
function asUiAssumption(item: ApiAssumption): Assumption {
  return {
    id: item.id, label: item.label,
    value: typeof item.value === "string" ? item.value : JSON.stringify(item.value),
    unit: item.unit ?? undefined, source: item.source, rationale: item.rationale,
    validRange: item.valid_range ? String(item.valid_range[0]) + " to " + String(item.valid_range[1]) : undefined,
  }
}
function toUiResults(raw: ApiScenarioResult[], inputs: ApiScenario[]): ScenarioResult[] {
  const base = raw[0]
  const baseVolume = total(base.volume), baseRevenue = total(base.gsv)
  const baseGp = total(base.gp), baseNsv = total(base.nsv)
  return raw.map((result, index) => {
    const input = inputs[index]
    if (result.status === "REFUSED") {
      return {
        scenarioId: result.scenario_id, name: input.name, status: result.status, isBaseline: index === 0,
        refusalReason: result.refusal_reasons.map((reason) => reason.message).join("; "),
        nearestSupportedId: result.nearest_supported_scenario ? "nearest-" + result.scenario_id : undefined,
      }
    }
    const delta = (volume: number, revenue: number, gp: number, nsv: number): ScenarioDelta => ({
      volumePct: baseVolume ? (volume / baseVolume - 1) * 100 : 0,
      revenuePct: baseRevenue ? (revenue / baseRevenue - 1) * 100 : 0,
      marginPct: baseGp ? (gp / baseGp - 1) * 100 : 0,
      marginPpt: (nsv ? gp / nsv * 100 : 0) - (baseNsv ? baseGp / baseNsv * 100 : 0),
    })
    return {
      scenarioId: result.scenario_id, name: input.name, status: result.status, isBaseline: index === 0,
      delta: delta(total(result.volume), total(result.gsv), total(result.gp), total(result.nsv)),
      p10: delta(totalAt(result.volume, "p10"), totalAt(result.gsv, "p10"), totalAt(result.gp, "p10"), totalAt(result.nsv, "p10")),
      p90: delta(totalAt(result.volume, "p90"), totalAt(result.gsv, "p90"), totalAt(result.gp, "p90"), totalAt(result.nsv, "p90")),
    }
  })
}
function App() {
  const [scenarios, setScenarios] = useState<ApiScenario[]>(initialScenarios)
  const [results, setResults] = useState<ScenarioResult[]>([])
  const [rawResults, setRawResults] = useState<ApiScenarioResult[]>([])
  const [heatmap, setHeatmap] = useState<HeatCell[]>([])
  const [heatmapLoading, setHeatmapLoading] = useState(false)
  const [assumptions, setAssumptions] = useState<Assumption[]>([])
  const [modelInfo, setModelInfo] = useState<{ engine_version: string; data_hash: string }>()
  const [computeMs, setComputeMs] = useState<number>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()

  async function refresh(items = scenarios) {
    setLoading(true)
    setError(undefined)
    const started = performance.now()
    try {
      const raw = await evaluateScenarios(items)
      setRawResults(raw)
      setResults(toUiResults(raw, items))
      setComputeMs(performance.now() - started)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to evaluate scenarios")
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    let active = true
    Promise.all([getAssumptions(), getModelInfo()])
      .then(([items, info]) => {
        if (active) { setAssumptions(items.map(asUiAssumption)); setModelInfo(info) }
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "Backend unavailable")
      })
    void refresh(initialScenarios)
    return () => { active = false }
  }, [])

  async function generateHeatmap() {
    setHeatmapLoading(true)
    setError(undefined)
    try {
      const prices = [0.92, 0.96, 1, 1.04, 1.08]
      const depths = [0, 10, 20, 30]
      const grid: ApiScenario[] = depths.flatMap((depth) => prices.map((price) => ({
        schema_version: 1, name: "Sweep price " + price + " promo " + depth,
        levers: { [SKU]: { price_index: price, promo_depth_pct: depth, mechanic: depth === 0 ? "none" : "TPR", promo_weeks_per_month: depth === 0 ? 0 : 2 } },
        cost_shock: { aluminium_pct: 0, pet_resin_pct: 0, sugar_pct: 0 },
      })))
      const evaluated = await evaluateScenarios(grid, 0, 42)
      setHeatmap(evaluated.map((item, i) => ({
        price: prices[i % prices.length], depth: depths[Math.floor(i / prices.length)], status: item.status,
        gp: item.status === "REFUSED" ? null : item.portfolio_gp?.value ?? null,
      })))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to calculate heatmap")
    } finally {
      setHeatmapLoading(false)
    }
  }
  function updateLever(index: number, change: Partial<ApiScenario["levers"][string]>) {
    setScenarios((current) => current.map((scenario, i) => {
      if (i !== index) return scenario
      const lever = scenario.levers[SKU] ?? { price_index: 1, promo_depth_pct: 0, mechanic: "none", promo_weeks_per_month: 0 }
      return { ...scenario, levers: { ...scenario.levers, [SKU]: { ...lever, ...change } } }
    }))
  }
  function addScenario(copyIndex?: number) {
    setScenarios((current) => {
      const source = copyIndex === undefined ? undefined : current[copyIndex]
      const copy: ApiScenario = source
        ? JSON.parse(JSON.stringify(source)) as ApiScenario
        : { schema_version: 1, name: "New scenario", levers: {}, cost_shock: { aluminium_pct: 0, pet_resin_pct: 0, sugar_pct: 0 } }
      copy.name = source ? "Copy of " + source.name : copy.name
      return [...current, copy]
    })
  }
  function acceptAgentScenario(scenario: ApiScenario) {
    const next = [...scenarios, scenario]
    setScenarios(next)
    void refresh(next)
  }

  async function useNearest(scenarioId: string) {
    const index = results.findIndex((item) => item.scenarioId === scenarioId)
    if (index < 0) return
    try {
      const nearest = await nearestSupported(scenarios[index])
      const next = [...scenarios, { ...nearest.scenario, name: "Nearest supported to " + scenarios[index].name }]
      setScenarios(next)
      await refresh(next)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not find supported alternative")
    }
  }
  return (
    <TooltipProvider><div className="flex min-h-svh flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-4">
        <div><h1 className="text-lg font-semibold">Revenue Growth Scenario Simulator</h1><p className="text-sm text-muted-foreground">Synthetic CPG data · deterministic elasticity engine · comparison-first</p></div>
        <AssumptionsDrawer assumptions={assumptions} />
      </header>
      <main className="flex-1 px-6 py-6">
        <section aria-label="Scenario tray" className="mb-5 space-y-3">
          <div className="flex items-center justify-between"><h2 className="font-semibold">Scenario tray</h2><button type="button" onClick={() => addScenario()} className="rounded-md border px-3 py-1.5 text-sm">Add scenario</button></div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{scenarios.map((scenario, index) => {
            const lever = scenario.levers[SKU] ?? { price_index: 1, promo_depth_pct: 0, mechanic: "none", promo_weeks_per_month: 0 }
            return <div key={index} className="space-y-2 rounded-lg border p-3">
              <div className="flex gap-2"><input aria-label="Scenario name" value={scenario.name} readOnly={index === 0} onChange={(event) => setScenarios((current) => current.map((item, i) => i === index ? { ...item, name: event.target.value } : item))} className="min-w-0 flex-1 rounded border bg-background px-2 py-1 text-sm" />
                {index > 0 && <button type="button" onClick={() => addScenario(index)} className="text-xs underline">Duplicate</button>}
                {index > 0 && <button type="button" onClick={() => setScenarios((current) => current.filter((_, i) => i !== index))} className="text-xs text-destructive underline">Remove</button>}
              </div>
              {index > 0 && <div className="grid grid-cols-2 gap-2 text-xs">
                <label>Price index<input aria-label="Price index" type="number" min="0.5" max="2" step="0.01" value={lever.price_index} onChange={(event) => updateLever(index, { price_index: Number(event.target.value) })} className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm" /></label>
                <label>Promo depth %<input aria-label="Promo depth" type="number" min="0" max="100" step="5" value={lever.promo_depth_pct} onChange={(event) => {
                  const depth = Number(event.target.value)
                  updateLever(index, { promo_depth_pct: depth, mechanic: depth === 0 ? "none" : "TPR", promo_weeks_per_month: depth === 0 ? 0 : Math.max(1, lever.promo_weeks_per_month) })
                }} className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm" /></label>
              </div>}
            </div>
          })}</div>
          <button type="button" disabled={loading} onClick={() => void refresh()} className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50">{loading ? "Evaluating…" : "Evaluate scenarios"}</button>
        </section>
        <Tabs defaultValue="board">
          <TabsList><TabsTrigger value="board">Comparison board</TabsTrigger><TabsTrigger value="analytics">Analytics</TabsTrigger><TabsTrigger value="agent">Agent <Badge variant="outline" className="ml-2">Phase 15</Badge></TabsTrigger></TabsList>
          <TabsContent value="board" className="mt-4 space-y-4">
            {error && <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
            {loading && <p className="text-sm text-muted-foreground">Evaluating scenarios…</p>}
            {!loading && results.length > 0 && <ComparisonBoard scenarios={results} onUseNearest={useNearest} />}
          </TabsContent>
          <TabsContent value="analytics" className="mt-4">{!loading && results.length > 0 && <AnalyticsViews scenarios={results} bridges={Object.fromEntries(rawResults.map((item) => [item.scenario_id, item.bridge]))} heatmap={heatmap} baselineGp={rawResults[0] ? total(rawResults[0].gp) : 0} onGenerateHeatmap={() => void generateHeatmap()} heatmapLoading={heatmapLoading} />}</TabsContent>
          <TabsContent value="agent" className="mt-4"><AgentPanel onAcceptScenario={acceptAgentScenario} /></TabsContent>
        </Tabs>
      </main>
      <AppFooter computeMs={computeMs} modelVersion={modelInfo?.engine_version} dataHash={modelInfo?.data_hash} />
    </div></TooltipProvider>
  )
}
export default App

