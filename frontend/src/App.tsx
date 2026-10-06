import { useEffect, useRef, useState } from "react"
import { AgentPanel } from "@/components/agent-panel"
import { AppFooter } from "@/components/app-footer"
import { AssumptionsDrawer } from "@/components/assumptions-drawer"
import { ComparisonBoard } from "@/components/comparison-board"
import { AnalyticsViews, type HeatCell } from "@/components/analytics-views"
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
  { schema_version: 1, name: "Competitive price defense", levers: { [SKU]: { price_index: 0.96, promo_depth_pct: 0, mechanic: "none", promo_weeks_per_month: 0 } }, cost_shock: { aluminium_pct: 0, pet_resin_pct: 0, sugar_pct: 0 } },
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
const pct = (index: number) => `${index > 1 ? "+" : index < 1 ? "−" : ""}${Math.abs((index - 1) * 100).toFixed(0)}%`
const signed = (v: number) => `${v >= 0.05 ? "+" : v <= -0.05 ? "−" : ""}${Math.abs(v).toFixed(1)}%`

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
  const latest = useRef(0)

  // Re-evaluate shortly after any edit; ignore responses that arrive out of order.
  useEffect(() => {
    const ticket = ++latest.current
    const timer = setTimeout(async () => {
      setLoading(true)
      setError(undefined)
      const started = performance.now()
      try {
        const raw = await evaluateScenarios(scenarios)
        if (ticket !== latest.current) return
        setRawResults(raw)
        setResults(toUiResults(raw, scenarios))
        setComputeMs(performance.now() - started)
      } catch (cause) {
        if (ticket === latest.current) setError(cause instanceof Error ? cause.message : "Unable to evaluate scenarios")
      } finally {
        if (ticket === latest.current) setLoading(false)
      }
    }, 350)
    return () => clearTimeout(timer)
  }, [scenarios])

  useEffect(() => {
    let active = true
    Promise.all([getAssumptions(), getModelInfo()])
      .then(([items, info]) => { if (active) { setAssumptions(items.map(asUiAssumption)); setModelInfo(info) } })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Backend unavailable") })
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
  function acceptAgentScenario(scenario: ApiScenario) { setScenarios((current) => [...current, scenario]) }

  async function useNearest(scenarioId: string) {
    const index = results.findIndex((item) => item.scenarioId === scenarioId)
    if (index < 0) return
    try {
      const nearest = await nearestSupported(scenarios[index])
      setScenarios((current) => [...current, { ...nearest.scenario, name: "Nearest supported to " + scenarios[index].name }])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not find supported alternative")
    }
  }
  const supportedCount = results.filter((item) => item.status !== "REFUSED").length
  const refusedCount = results.length - supportedCount
  const best = results.filter((item) => item.status !== "REFUSED" && !item.isBaseline && item.delta).sort((a, b) => (b.delta?.marginPct ?? -Infinity) - (a.delta?.marginPct ?? -Infinity))[0]
  const tab = "flex-none rounded-md px-4 py-2 text-sm data-active:bg-ink data-active:text-white!"
  return (
    <TooltipProvider><div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-20 border-b bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1480px] items-center justify-between gap-3 px-5 py-3 md:px-8">
          <div className="flex items-baseline gap-3"><span className="font-display text-lg font-bold tracking-tight">Northstar</span><span className="hidden text-sm text-muted-foreground sm:inline">Revenue growth simulator</span></div>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex"><span className={`size-2 rounded-full ${error ? "bg-loss" : "bg-gain"}`} />{error ? "Engine unreachable" : "Synthetic data, engine " + (modelInfo?.engine_version ?? "…")}</span>
            <AssumptionsDrawer assumptions={assumptions} />
          </div>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-[1480px] flex-1 items-start gap-8 px-5 py-8 md:px-8 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <aside className="space-y-4 lg:sticky lg:top-20 lg:max-h-[calc(100svh-6rem)] lg:overflow-y-auto lg:pr-1" aria-label="Scenario builder">
          <div><h2 className="font-display text-xl font-semibold">Scenarios</h2><p className="text-sm text-muted-foreground">Aurora 330 ml can. Drag a lever and results update.</p></div>
          {scenarios.map((scenario, index) => {
            const lever = scenario.levers[SKU] ?? { price_index: 1, promo_depth_pct: 0, mechanic: "none", promo_weeks_per_month: 0 }
            return <div key={index} className={`space-y-4 rounded-lg border p-4 ${index === 0 ? "border-dashed bg-transparent" : "bg-card"}`}>
              <div className="flex items-center gap-2">
                <input aria-label="Scenario name" value={scenario.name} readOnly={index === 0} onChange={(event) => setScenarios((current) => current.map((item, i) => i === index ? { ...item, name: event.target.value } : item))} className="min-w-0 flex-1 rounded border border-transparent bg-transparent px-1 py-1 font-display text-base font-semibold hover:border-input focus:border-input" />
                {index > 0 && <button type="button" onClick={() => addScenario(index)} className="rounded px-1.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">Duplicate</button>}
                {index > 0 && <button type="button" onClick={() => setScenarios((current) => current.filter((_, i) => i !== index))} className="rounded px-1.5 py-1 text-xs text-loss hover:bg-loss/10">Remove</button>}
              </div>
              {index === 0 ? <p className="px-1 text-xs text-muted-foreground">Current price, no promotion. Every other scenario is measured against this one.</p> : <>
                <label className="block text-xs text-muted-foreground"><span className="flex justify-between"><span>Price index</span><span className="num text-sm font-semibold text-foreground">{lever.price_index.toFixed(2)} <span className="font-normal text-muted-foreground">({pct(lever.price_index)})</span></span></span>
                  <input aria-label="Price index" type="range" min="0.8" max="1.6" step="0.01" value={lever.price_index} onChange={(event) => updateLever(index, { price_index: Number(event.target.value) })} /></label>
                <label className="block text-xs text-muted-foreground"><span className="flex justify-between"><span>Promo depth</span><span className="num text-sm font-semibold text-foreground">{lever.promo_depth_pct}%</span></span>
                  <input aria-label="Promo depth" type="range" min="0" max="50" step="5" value={lever.promo_depth_pct} onChange={(event) => {
                    const depth = Number(event.target.value)
                    updateLever(index, { promo_depth_pct: depth, mechanic: depth === 0 ? "none" : "TPR", promo_weeks_per_month: depth === 0 ? 0 : Math.max(1, lever.promo_weeks_per_month) })
                  }} /></label>
              </>}
            </div>
          })}
          <button type="button" onClick={() => addScenario()} className="w-full rounded-lg border border-dashed border-input py-2.5 text-sm font-medium text-muted-foreground hover:border-primary hover:text-primary">Add scenario</button>
        </aside>

        <div className="min-w-0 space-y-8">
          <section aria-label="Headline" className="grid gap-6 rounded-xl bg-ink p-6 text-white md:grid-cols-[1fr_auto] md:p-8">
            <div>
              <p className="text-sm text-white/60">{best ? "Best margin move" : "Waiting for results"}</p>
              <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className="num text-6xl font-bold leading-none md:text-7xl" style={{ color: best && (best.delta?.marginPct ?? 0) < 0 ? "#f0997f" : "#5fd6c0" }}>{best?.delta ? signed(best.delta.marginPct) : "—"}</span>
                <span className="font-display text-xl">{best ? "gross profit, " + best.name : loading ? "Evaluating…" : "Move a lever to compare."}</span>
              </div>
              {best?.delta && <p className="mt-3 max-w-xl text-sm text-white/70">Volume {signed(best.delta.volumePct)}, revenue {signed(best.delta.revenuePct)} against the baseline. The engine is deterministic: the same levers always give the same numbers.</p>}
            </div>
            <dl className="grid grid-cols-3 gap-x-8 self-end text-sm md:grid-cols-1 md:gap-y-3 md:text-right">
              <div><dt className="text-white/50">Compared</dt><dd className="num text-2xl font-semibold">{scenarios.length}</dd></div>
              <div><dt className="text-white/50">Supported</dt><dd className="num text-2xl font-semibold">{supportedCount}</dd></div>
              <div><dt className="text-white/50">Refused</dt><dd className="num text-2xl font-semibold">{refusedCount}</dd></div>
            </dl>
          </section>

          <Tabs defaultValue="board">
            <TabsList className="h-auto w-fit justify-start gap-1 rounded-lg bg-secondary p-1 sm:w-auto"><TabsTrigger value="board" className={tab}>Comparison board</TabsTrigger><TabsTrigger value="analytics" className={tab}>Analytics</TabsTrigger><TabsTrigger value="agent" className={tab}>Growth agent</TabsTrigger></TabsList>
            <TabsContent value="board" className={`mt-5 space-y-4 transition-opacity ${loading && results.length ? "opacity-60" : ""}`}>
              {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
              {!results.length && loading && <p className="text-sm text-muted-foreground">Evaluating scenarios…</p>}
              {results.length > 0 && <ComparisonBoard scenarios={results} onUseNearest={useNearest} />}
            </TabsContent>
            <TabsContent value="analytics" className="mt-5">{results.length > 0 && <AnalyticsViews scenarios={results} bridges={Object.fromEntries(rawResults.map((item) => [item.scenario_id, item.bridge]))} heatmap={heatmap} baselineGp={rawResults[0] ? total(rawResults[0].gp) : 0} onGenerateHeatmap={() => void generateHeatmap()} heatmapLoading={heatmapLoading} />}</TabsContent>
            <TabsContent value="agent" className="mt-5"><AgentPanel onAcceptScenario={acceptAgentScenario} /></TabsContent>
          </Tabs>
        </div>
      </main>
      <AppFooter computeMs={computeMs} modelVersion={modelInfo?.engine_version} dataHash={modelInfo?.data_hash} />
    </div></TooltipProvider>
  )
}
export default App
