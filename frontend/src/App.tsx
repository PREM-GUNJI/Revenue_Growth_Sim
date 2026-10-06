import { useEffect, useRef, useState } from "react"
import { AgentPanel } from "@/components/agent-panel"
import { AnalyticsViews, type HeatCell } from "@/components/analytics-views"
import { AppFooter } from "@/components/app-footer"
import { AssumptionsDrawer } from "@/components/assumptions-drawer"
import { ComparisonBoard } from "@/components/comparison-board"
import { ConjointPanel } from "@/components/conjoint-panel"
import { LeverWorkspace } from "@/components/lever-panels"
import { PricingEvidence } from "@/components/pricing-evidence"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { evaluateScenarios, getAssumptions, getEnvelope, getEvidenceDefaults, getModelInfo, nearestSupported } from "@/lib/api"
import type { ApiAssumption, ApiScenario, ApiScenarioResult, EnvelopeInfo, EvidenceDefaults } from "@/lib/api"
import { PACKS, baselineLever, newScenario, packOf, packShort, signed, skuFor, sum } from "@/lib/catalog"
import type { Assumption, ScenarioDelta, ScenarioResult } from "@/lib/types"

const CAN = skuFor("can_330ml")
const initialScenarios: ApiScenario[] = [
  newScenario("Baseline"),
  newScenario("+4% price, Aurora can", { [CAN]: { ...baselineLever, price_index: 1.04 } }),
  newScenario("Promotion scenario", { [CAN]: { ...baselineLever, promo_depth_pct: 20, mechanic: "TPR", promo_weeks_per_month: 3 } }),
  newScenario("Competitive price defense", { [CAN]: { ...baselineLever, price_index: 0.96 } }),
  newScenario("Out-of-range price", { [CAN]: { ...baselineLever, price_index: 1.5 } }),
]
const totalAt = (values: ApiScenarioResult["volume"], edge: "value" | "p10" | "p90") => sum(values, edge)
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
  const baseVolume = sum(base.volume), baseRevenue = sum(base.gsv), baseGp = sum(base.gp), baseNsv = sum(base.nsv)
  return raw.map((result, index) => {
    const input = inputs[index]
    const common = { scenarioId: result.scenario_id, resultHash: result.result_hash, name: input.name, status: result.status, isBaseline: index === 0, source: input.source }
    if (result.status === "REFUSED") {
      return {
        ...common,
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
    const at = (edge: "value" | "p10" | "p90") => delta(totalAt(result.volume, edge), totalAt(result.gsv, edge), totalAt(result.gp, edge), totalAt(result.nsv, edge))
    return { ...common, delta: at("value"), p10: at("p10"), p90: at("p90") }
  })
}

type View = "overview" | "simulator" | "board" | "assistant" | "evidence" | "conjoint"
const MAIN_NAV: Array<[View, string]> = [["overview", "Overview"], ["simulator", "Scenario simulator"], ["board", "Comparison board"], ["assistant", "AI decision assistant"]]
const SUPPORT_NAV: Array<[View, string]> = [["evidence", "Pricing evidence"], ["conjoint", "Conjoint simulation"]]

function App() {
  const [view, setView] = useState<View>("overview")
  const [scenarios, setScenarios] = useState<ApiScenario[]>(initialScenarios)
  const [results, setResults] = useState<ScenarioResult[]>([])
  const [rawResults, setRawResults] = useState<ApiScenarioResult[]>([])
  const [heatmap, setHeatmap] = useState<HeatCell[]>([])
  const [heatmapLoading, setHeatmapLoading] = useState(false)
  const [assumptions, setAssumptions] = useState<Assumption[]>([])
  const [envelope, setEnvelope] = useState<EnvelopeInfo>()
  const [evidenceDefaults, setEvidenceDefaults] = useState<EvidenceDefaults>()
  const [modelInfo, setModelInfo] = useState<{ engine_version: string; data_hash: string }>()
  const [computeMs, setComputeMs] = useState<number>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [activePack, setActivePack] = useState<string>("can_330ml")
  const [guardrail, setGuardrail] = useState(5)
  const [notice, setNotice] = useState<string>()
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
    Promise.all([getAssumptions(), getModelInfo(), getEnvelope(), getEvidenceDefaults()])
      .then(([items, info, env, defaults]) => {
        if (!active) return
        setAssumptions(items.map(asUiAssumption)); setModelInfo(info); setEnvelope(env); setEvidenceDefaults(defaults)
      })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Backend unavailable") })
    return () => { active = false }
  }, [])
  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(undefined), 7000)
    return () => clearTimeout(timer)
  }, [notice])

  async function generateHeatmap() {
    setHeatmapLoading(true)
    setError(undefined)
    try {
      const prices = [0.92, 0.96, 1, 1.04, 1.08]
      const depths = [0, 10, 20, 30]
      const sku = skuFor(activePack)
      const grid = depths.flatMap((depth) => prices.map((price) => newScenario("Sweep price " + price + " promo " + depth, {
        [sku]: { price_index: price, promo_depth_pct: depth, mechanic: depth === 0 ? "none" : "TPR", promo_weeks_per_month: depth === 0 ? 0 : 2 },
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
    const sku = skuFor(activePack)
    setScenarios((current) => current.map((scenario, i) => {
      if (i !== index) return scenario
      const lever = scenario.levers[sku] ?? baselineLever
      return { ...scenario, levers: { ...scenario.levers, [sku]: { ...lever, ...change } } }
    }))
  }
  function addScenario(copyIndex?: number) {
    setScenarios((current) => {
      const source = copyIndex === undefined ? undefined : current[copyIndex]
      const copy: ApiScenario = source ? JSON.parse(JSON.stringify(source)) as ApiScenario : newScenario("New scenario")
      if (source) copy.name = "Copy of " + source.name
      return [...current, copy]
    })
  }
  /** Used by presets, research candidates and the agent: add a scenario and say where to find it. */
  function addExternal(scenario: ApiScenario) {
    setScenarios((current) => [...current, scenario])
    setNotice(`Added "${scenario.name}". It is evaluated by the engine on the comparison board.`)
  }
  async function useNearest(scenarioId: string) {
    const index = results.findIndex((item) => item.scenarioId === scenarioId)
    if (index < 0) return
    try {
      const nearest = await nearestSupported(scenarios[index])
      setScenarios((current) => [...current, { ...nearest.scenario, name: "Nearest supported to " + scenarios[index].name, source: scenarios[index].source }])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not find supported alternative")
    }
  }

  const supportedCount = results.filter((item) => item.status !== "REFUSED").length
  const refusedCount = results.length - supportedCount
  const best = results.filter((item) => item.status !== "REFUSED" && !item.isBaseline && item.delta && item.delta.volumePct >= -guardrail)
    .sort((a, b) => (b.delta?.marginPct ?? -Infinity) - (a.delta?.marginPct ?? -Infinity))[0]
  const showBuilder = view === "simulator" || view === "board"
  const nav = (id: View, label: string) => <button key={id} type="button" aria-current={view === id ? "page" : undefined} onClick={() => setView(id)}
    className={`rounded-md px-3 py-1.5 text-sm ${view === id ? "bg-ink font-medium text-white" : "text-foreground/80 hover:bg-secondary"}`}>{label}</button>
  const tab = "flex-none rounded-md px-4 py-2 text-sm data-active:bg-ink data-active:text-white!"
  return (
    <TooltipProvider><div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-20 border-b bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1480px] flex-wrap items-center justify-between gap-x-6 gap-y-2 px-5 py-3 md:px-8">
          <div className="flex items-baseline gap-3"><span className="font-display text-lg font-bold tracking-tight">Northstar</span><span className="hidden text-sm text-muted-foreground xl:inline">Revenue growth simulator</span></div>
          <nav aria-label="Primary" className="flex flex-wrap items-center gap-1">
            {MAIN_NAV.map(([id, label]) => nav(id, label))}
            <span className="mx-2 hidden h-5 w-px bg-border md:block" aria-hidden="true" />
            <span className="mr-1 hidden text-xs text-muted-foreground md:inline">Supporting evidence</span>
            {SUPPORT_NAV.map(([id, label]) => nav(id, label))}
          </nav>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-1.5 text-xs text-muted-foreground 2xl:flex"><span className={`size-2 rounded-full ${error ? "bg-loss" : "bg-gain"}`} />{error ? "Engine unreachable" : "Synthetic data, engine " + (modelInfo?.engine_version ?? "…")}</span>
            <AssumptionsDrawer assumptions={assumptions} />
          </div>
        </div>
      </header>

      {notice && <div role="status" className="fixed bottom-14 left-1/2 z-30 flex -translate-x-1/2 items-center gap-4 rounded-lg bg-ink px-4 py-3 text-sm text-white shadow-lg">
        <span>{notice}</span><button type="button" onClick={() => { setView("board"); setNotice(undefined) }} className="rounded border border-white/40 px-2 py-1 text-xs font-medium hover:bg-white/10">Open comparison board</button></div>}

      <main className={`mx-auto grid w-full max-w-[1480px] flex-1 items-start gap-8 px-5 py-8 md:px-8 ${showBuilder ? "lg:grid-cols-[22rem_minmax(0,1fr)]" : ""}`}>
        {showBuilder && <aside className="space-y-4 lg:sticky lg:top-24 lg:max-h-[calc(100svh-7rem)] lg:overflow-y-auto lg:pr-1" aria-label="Scenario builder">
          <div><h2 className="font-display text-xl font-semibold">Scenarios</h2><p className="text-sm text-muted-foreground">Pick a pack, drag its levers, and results update.</p></div>
          <div role="group" aria-label="Pack to edit" className="grid grid-cols-4 gap-1 rounded-lg bg-secondary p-1">
            {PACKS.map((p) => <button key={p.id} type="button" aria-pressed={activePack === p.id} onClick={() => setActivePack(p.id)} className={`rounded-md py-1.5 text-xs ${activePack === p.id ? "bg-ink font-medium text-white" : "hover:bg-card"}`}>{p.short}</button>)}
          </div>
          {scenarios.map((scenario, index) => {
            const sku = skuFor(activePack)
            const lever = scenario.levers[sku] ?? baselineLever
            const others = Object.entries(scenario.levers).filter(([k, l]) => k !== sku && (l.price_index !== 1 || l.promo_depth_pct > 0))
              .map(([k, l]) => `${packShort(packOf(k))} ${l.price_index !== 1 ? signed((l.price_index - 1) * 100, 0) + " price" : ""}${l.promo_depth_pct > 0 ? ` ${l.promo_depth_pct}% promo` : ""}`.trim())
            return <div key={index} className={`space-y-4 rounded-lg border p-4 ${index === 0 ? "border-dashed bg-transparent" : "bg-card"}`}>
              <div className="flex items-center gap-2">
                <input aria-label="Scenario name" value={scenario.name} readOnly={index === 0} onChange={(event) => setScenarios((current) => current.map((item, i) => i === index ? { ...item, name: event.target.value } : item))} className="min-w-0 flex-1 rounded border border-transparent bg-transparent px-1 py-1 font-display text-base font-semibold hover:border-input focus:border-input" />
                {index > 0 && <button type="button" onClick={() => addScenario(index)} className="rounded px-1.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">Duplicate</button>}
                {index > 0 && <button type="button" onClick={() => setScenarios((current) => current.filter((_, i) => i !== index))} className="rounded px-1.5 py-1 text-xs text-loss hover:bg-loss/10">Remove</button>}
              </div>
              {index === 0 ? <p className="px-1 text-xs text-muted-foreground">Current price, no promotion. Every other scenario is measured against this one.</p> : <>
                <label className="block text-xs text-muted-foreground"><span className="flex justify-between"><span>Price index, {packShort(activePack)}</span><span className="num text-sm font-semibold text-foreground">{lever.price_index.toFixed(2)} <span className="font-normal text-muted-foreground">({signed((lever.price_index - 1) * 100, 0)})</span></span></span>
                  <input aria-label="Price index" type="range" min="0.8" max="1.6" step="0.01" value={lever.price_index} onChange={(event) => updateLever(index, { price_index: Number(event.target.value) })} /></label>
                <label className="block text-xs text-muted-foreground"><span className="flex justify-between"><span>Promo depth, {packShort(activePack)}</span><span className="num text-sm font-semibold text-foreground">{lever.promo_depth_pct}%</span></span>
                  <input aria-label="Promo depth" type="range" min="0" max="50" step="5" value={lever.promo_depth_pct} onChange={(event) => {
                    const depth = Number(event.target.value)
                    updateLever(index, { promo_depth_pct: depth, mechanic: depth === 0 ? "none" : "TPR", promo_weeks_per_month: depth === 0 ? 0 : Math.max(1, lever.promo_weeks_per_month) })
                  }} /></label>
                {others.length > 0 && <p className="text-xs text-muted-foreground">Also set: {others.join("; ")}</p>}
              </>}
            </div>
          })}
          <button type="button" onClick={() => addScenario()} className="w-full rounded-lg border border-dashed border-input py-2.5 text-sm font-medium text-muted-foreground hover:border-primary hover:text-primary">Add scenario</button>
        </aside>}

        <div className="min-w-0 space-y-8">
          {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}

          {view === "overview" && <>
            <section aria-label="Headline" className="grid gap-6 rounded-xl bg-ink p-6 text-white md:grid-cols-[1fr_auto] md:p-8">
              <div>
                <p className="text-sm text-white/60">{best ? "Best margin move within the volume guardrail" : "Waiting for results"}</p>
                <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <span className="num text-6xl font-bold leading-none md:text-7xl" style={{ color: best && (best.delta?.marginPct ?? 0) < 0 ? "#f0997f" : "#5fd6c0" }}>{best?.delta ? signed(best.delta.marginPct) : "—"}</span>
                  <span className="font-display text-xl">{best ? "gross profit, " + best.name : loading ? "Evaluating…" : "No scenario fits the guardrail."}</span>
                </div>
                {best?.delta && <p className="mt-3 max-w-xl text-sm text-white/70">Volume {signed(best.delta.volumePct)}, revenue {signed(best.delta.revenuePct)} against the baseline. The engine is deterministic: the same levers always give the same numbers.</p>}
              </div>
              <dl className="grid grid-cols-3 gap-x-8 self-end text-sm md:grid-cols-1 md:gap-y-3 md:text-right">
                <div><dt className="text-white/50">Compared</dt><dd className="num text-2xl font-semibold">{scenarios.length}</dd></div>
                <div><dt className="text-white/50">Supported</dt><dd className="num text-2xl font-semibold">{supportedCount}</dd></div>
                <div><dt className="text-white/50">Refused</dt><dd className="num text-2xl font-semibold">{refusedCount}</dd></div>
              </dl>
            </section>
            <section aria-label="How a decision is made">
              <h2 className="font-display text-xl font-semibold">How a decision is made</h2>
              <ol className="mt-4 grid gap-3 md:grid-cols-5">
                {([["Price, pack and promotion", "Set the three levers together for each scenario.", "simulator", "Open the simulator"],
                  ["Deterministic engine", "A documented elasticity model. Out-of-range requests are refused, never extrapolated.", undefined, ""],
                  ["Volume, revenue and margin", "Every number, with its sensitivity band, comes from the engine.", undefined, ""],
                  ["Comparison", "Baseline, winners, losers and refusals side by side.", "board", "Open the board"],
                  ["Decision", "The assistant recommends from engine results; an auditor checks every number.", "assistant", "Ask the assistant"]] as const)
                  .map(([title, body, target, cta], i) => <li key={title} className="flex flex-col rounded-lg border bg-card p-4">
                    <span className="num text-sm text-muted-foreground">{i + 1}</span><h3 className="mt-1 font-display text-base font-semibold">{title}</h3>
                    <p className="mt-1 flex-1 text-sm text-muted-foreground">{body}</p>
                    {target && <button type="button" onClick={() => setView(target)} className="mt-3 self-start rounded text-sm font-medium text-primary underline-offset-4 hover:underline">{cta}</button>}</li>)}
              </ol>
            </section>
            <section className="grid gap-4 rounded-lg border border-edge/40 bg-edge/5 p-5 md:grid-cols-[1fr_auto]" aria-label="Supporting evidence">
              <div><h2 className="font-display text-lg font-semibold">Supporting synthetic consumer evidence</h2>
                <p className="mt-1 max-w-2xl text-sm text-foreground/80">Synthetic willingness to pay, Gabor-Granger, Van Westendorp and a conjoint simulation suggest candidate prices. The candidates enter the same simulator and are judged by the same engine. Nothing here is real consumer research.</p></div>
              <div className="flex flex-wrap items-center gap-2"><button type="button" onClick={() => setView("evidence")} className="rounded-md border bg-card px-3 py-2 text-sm font-medium hover:bg-secondary">Pricing evidence</button>
                <button type="button" onClick={() => setView("conjoint")} className="rounded-md border bg-card px-3 py-2 text-sm font-medium hover:bg-secondary">Conjoint simulation</button></div>
            </section>
          </>}

          {view === "simulator" && <>
            <div><h1 className="font-display text-2xl font-semibold">Scenario simulator</h1>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Price, pack and promotion are one decision. Analyse how each lever moves volume, revenue and margin, then add joint combinations to the board.</p></div>
            <LeverWorkspace scenarios={scenarios} rawResults={rawResults} activePack={activePack} envelope={envelope} defaults={evidenceDefaults} assumptions={assumptions} onAdd={addExternal} />
          </>}

          {view === "board" && <Tabs defaultValue="board">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <TabsList className="h-auto w-fit justify-start gap-1 rounded-lg bg-secondary p-1"><TabsTrigger value="board" className={tab}>Comparison board</TabsTrigger><TabsTrigger value="analytics" className={tab}>Analytics</TabsTrigger></TabsList>
              <label className="text-xs text-muted-foreground">Volume guardrail: lose no more than <span className="num text-sm font-semibold text-foreground">{guardrail}%</span> volume
                <input aria-label="Volume guardrail" type="range" min="0" max="20" step="1" value={guardrail} onChange={(e) => setGuardrail(Number(e.target.value))} className="mt-1 block w-48" /></label>
            </div>
            <TabsContent value="board" className={`mt-5 space-y-4 transition-opacity ${loading && results.length ? "opacity-60" : ""}`}>
              {!results.length && loading && <p className="text-sm text-muted-foreground">Evaluating scenarios…</p>}
              {results.length > 0 && <ComparisonBoard scenarios={results} onUseNearest={useNearest} volumeGuardrailPct={guardrail} />}
            </TabsContent>
            <TabsContent value="analytics" className="mt-5">{results.length > 0 && <AnalyticsViews scenarios={results} bridges={Object.fromEntries(rawResults.map((item) => [item.scenario_id, item.bridge]))} heatmap={heatmap} baselineGp={rawResults[0] ? sum(rawResults[0].gp) : 0} onGenerateHeatmap={() => void generateHeatmap()} heatmapLoading={heatmapLoading} />}</TabsContent>
          </Tabs>}

          {view === "assistant" && <AgentPanel onAcceptScenario={addExternal} />}
          {view === "evidence" && <PricingEvidence baseline={rawResults[0]} onAdd={addExternal} onOpenConjoint={() => setView("conjoint")} />}
          {view === "conjoint" && <ConjointPanel defaults={evidenceDefaults} baseline={rawResults[0]} onAdd={addExternal} />}
        </div>
      </main>
      <AppFooter computeMs={computeMs} modelVersion={modelInfo?.engine_version} dataHash={modelInfo?.data_hash} />
    </div></TooltipProvider>
  )
}
export default App
