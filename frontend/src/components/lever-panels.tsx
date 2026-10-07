import { useEffect, useMemo, useState } from "react"
import { DivBar, LineChart, type ChartPoint } from "@/components/bars"
import { CandidateTable, SyntheticBanner } from "@/components/evidence-parts"
import { evaluateScenarios, researchToScenarios } from "@/lib/api"
import type { ApiLever, ApiScenario, ApiScenarioResult, EnvelopeInfo, EvidenceDefaults, ResearchBridgeResponse } from "@/lib/api"
import { BRAND, PACKS, baselineLever, changePct, compact, inr, newScenario, packLabel, rupees, signed, signedRupees, skuFor, tone, totals } from "@/lib/catalog"
import type { Assumption } from "@/lib/types"

type Add = (scenario: ApiScenario) => void
const series = [
  { key: "volume", label: "Volume", color: "var(--edge)" },
  { key: "revenue", label: "Revenue", color: "var(--ink)" },
  { key: "margin", label: "Gross profit", color: "var(--gain)" },
]

/** Evaluate a grid of scenarios (point estimates) whenever the base scenario or grid changes. */
function useSweep(scenarios: ApiScenario[]) {
  const [results, setResults] = useState<ApiScenarioResult[]>()
  const [loading, setLoading] = useState(false)
  const key = JSON.stringify(scenarios)
  useEffect(() => {
    let live = true
    setLoading(true)
    evaluateScenarios(scenarios, 0)
      .then((r) => { if (live) setResults(r) })
      .catch(() => { if (live) setResults(undefined) })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return { results, loading }
}

function sweepPoints(xs: number[], results: ApiScenarioResult[] | undefined, baseline: ApiScenarioResult): ChartPoint[] {
  const base = totals(baseline)
  return xs.map((x, i) => {
    const r = results?.[i]
    if (!r) return { x, values: {} }
    if (r.status === "REFUSED") return { x, refused: true, values: {} }
    const t = totals(r)
    return { x, values: { volume: changePct(t.volume, base.volume), revenue: changePct(t.nsv, base.nsv), margin: changePct(t.gp, base.gp) } }
  })
}

function withLever(base: ApiScenario, pack: string, change: Partial<ApiLever>): ApiScenario {
  const sku = skuFor(pack)
  return { ...base, levers: { ...base.levers, [sku]: { ...baselineLever, ...base.levers[sku], ...change } } }
}

// ---------------------------------------------------------------- Price

function PricePanel({ base, pack, baseline, envelope, defaults, assumptions, onAdd }: {
  base: ApiScenario; pack: string; baseline: ApiScenarioResult; envelope: EnvelopeInfo; defaults: EvidenceDefaults
  assumptions: Assumption[]; onAdd: Add
}) {
  const sku = skuFor(pack), ref = defaults.reference_prices[pack]
  const [lo, hi] = envelope.price_index_p1_p99[sku] ?? [0.9, 1.1]
  const xs = useMemo(() => Array.from({ length: 11 }, (_, i) => Math.round((lo - 0.15 * (hi - lo) + (i / 10) * 1.3 * (hi - lo)) * 1000) / 1000), [lo, hi])
  const { results, loading } = useSweep(xs.map((x) => withLever(base, pack, { price_index: x })))
  const [wtp, setWtp] = useState<ResearchBridgeResponse>()
  useEffect(() => { let live = true; researchToScenarios("Willingness to Pay", pack).then((r) => { if (live) setWtp(r) }).catch(() => undefined); return () => { live = false } }, [pack])
  const elasticity = assumptions.find((a) => a.id === envelope.own_elasticity_assumption_by_format[pack])
  const lever = base.levers[sku] ?? baselineLever
  const markers = [{ x: lever.price_index, label: "This scenario", tone: "var(--ink)" },
    ...(wtp?.research.candidates ?? []).map((c) => ({ x: c.price / ref, label: c.source_metric.replace(" WTP", ""), tone: "var(--edge)" }))]
  return <div className="space-y-6">
    <div className="grid gap-4 md:grid-cols-3">
      <div className="rounded-lg border bg-card p-4"><p className="text-xs text-muted-foreground">Own-price elasticity (assumed)</p>
        <p className="num mt-1 text-2xl font-semibold">{elasticity?.value ?? "…"}</p>
        <p className="mt-1 text-xs text-muted-foreground">{elasticity ? `${elasticity.id}, plausible range ${elasticity.validRange}` : ""}. A 1% price rise cuts volume by about this many percent, before cross-pack effects.</p></div>
      <div className="rounded-lg border bg-card p-4"><p className="text-xs text-muted-foreground">Reference price, {packLabel(pack)}</p>
        <p className="num mt-1 text-2xl font-semibold">{inr(ref)}</p>
        <p className="mt-1 text-xs text-muted-foreground">Price index 1.00. Supported range {lo.toFixed(2)} to {hi.toFixed(2)}; outside it the engine refuses.</p></div>
      <div className="rounded-lg border bg-card p-4"><p className="text-xs text-muted-foreground">Current lever</p>
        <p className="num mt-1 text-2xl font-semibold">{inr(ref * lever.price_index)}</p>
        <p className="mt-1 text-xs text-muted-foreground">Price index {lever.price_index.toFixed(2)} in &ldquo;{base.name}&rdquo;.</p></div>
    </div>
    <section className="rounded-lg border bg-card p-5">
      <h3 className="font-display text-lg font-semibold">Demand, revenue and margin response</h3>
      <p className="mb-2 text-xs text-muted-foreground">Engine results for {packLabel(pack)} price changes against the baseline. Hatched columns are refused: no numbers exist there. Dashed lines mark synthetic willingness-to-pay candidates.</p>
      <div className={`overflow-x-auto transition-opacity ${loading ? "opacity-60" : ""}`}>
        <LineChart ariaLabel="Price response curves" points={sweepPoints(xs, results, baseline)} series={series} markers={markers} xLabel={`${packLabel(pack)} price`} xFormat={(x) => inr(x * ref)} /></div>
    </section>
    <section className="space-y-3">
      <div><h3 className="font-display text-lg font-semibold">Consumer evidence to candidate price to modeled outcome</h3>
        <p className="text-sm text-muted-foreground">Willingness-to-pay percentiles from synthetic respondents, evaluated by the engine.</p></div>
      <SyntheticBanner>Candidate prices come from synthetic respondents. The numbers below come from the engine.</SyntheticBanner>
      {wtp && <CandidateTable rows={wtp.scenarios} baseline={baseline} onAdd={onAdd} />}
    </section>
  </div>
}

// ----------------------------------------------------------------- Pack

function PackPanel({ scenario, result, baseline, defaults }: {
  scenario: ApiScenario; result: ApiScenarioResult; baseline: ApiScenarioResult; defaults: EvidenceDefaults
}) {
  if (result.status === "REFUSED") return <p className="rounded-lg border border-dashed border-loss/40 bg-card p-5 text-sm">This scenario was refused, so there is no pack movement to show. Choose a supported scenario.</p>
  const rows = PACKS.map((p) => {
    const sku = skuFor(p.id), b = baseline.volume[sku]?.value ?? 0, v = result.volume[sku]?.value ?? 0
    const index = scenario.levers[sku]?.price_index ?? 1
    return { ...p, sku, b, v, delta: v - b, pct: changePct(v, b), price: defaults.reference_prices[p.id] * index, perLitre: (defaults.reference_prices[p.id] * index) / p.litres, promo: scenario.levers[sku]?.promo_depth_pct ?? 0 }
  })
  const otherBase = Object.entries(baseline.volume).filter(([k]) => !k.startsWith(BRAND)).reduce((t, [, x]) => t + x.value, 0)
  const otherNow = Object.entries(result.volume).filter(([k]) => !k.startsWith(BRAND)).reduce((t, [, x]) => t + x.value, 0)
  const tb = totals(baseline), tn = totals(result)
  const gained = rows.filter((r) => r.delta > 0).reduce((t, r) => t + r.delta, 0), lost = rows.filter((r) => r.delta < 0).reduce((t, r) => t - r.delta, 0)
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.pct)), Math.abs(changePct(otherNow, otherBase))) * 1.15
  return <div className="space-y-6">
    <section className="rounded-lg border bg-card p-5">
      <h3 className="font-display text-lg font-semibold">Pack-price architecture and cannibalization</h3>
      <p className="mb-4 text-xs text-muted-foreground">How &ldquo;{scenario.name}&rdquo; moves volume between the four observed {BRAND} packs. Only observed pack sizes can be changed; unobserved sizes are not offered.</p>
      <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm">
        <thead><tr className="text-left text-xs text-muted-foreground"><th className="py-2 pr-3 font-normal">Pack</th><th className="px-3 font-normal">Shelf price</th><th className="px-3 font-normal">Per litre</th><th className="px-3 text-right font-normal">Volume now</th><th className="px-3 text-right font-normal">Baseline</th><th className="w-56 px-3 font-normal">Change</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.id} className="border-t">
          <td className="py-3 pr-3 font-medium">{r.label}{r.promo > 0 && <span className="ml-2 rounded bg-edge/15 px-1.5 py-0.5 text-xs text-edge">{r.promo}% promo</span>}</td>
          <td className="num px-3">{inr(r.price)}</td><td className="num px-3">{inr(r.perLitre)}</td>
          <td className="num px-3 text-right">{compact(r.v)}</td><td className="num px-3 text-right text-muted-foreground">{compact(r.b)}</td>
          <td className="px-3"><div className={`num mb-1 font-semibold ${tone(r.pct)}`}>{signed(r.pct)}</div><DivBar value={r.pct} max={max} /></td></tr>)}
          <tr className="border-t text-muted-foreground"><td className="py-3 pr-3">Competitor brands <span className="text-xs">(cross-price effect only)</span></td><td colSpan={2} /><td className="num px-3 text-right">{compact(otherNow)}</td><td className="num px-3 text-right">{compact(otherBase)}</td>
            <td className="px-3"><div className={`num mb-1 ${tone(changePct(otherNow, otherBase))}`}>{signed(changePct(otherNow, otherBase))}</div><DivBar value={changePct(otherNow, otherBase)} max={max} /></td></tr></tbody></table></div>
    </section>
    <section className="grid gap-4 md:grid-cols-4">
      {[["Volume gained by packs", `+${compact(gained)}`, "text-gain"], ["Volume lost by packs", `−${compact(lost)}`, "text-loss"],
        [`${BRAND} volume`, signed(changePct(tn.volume, tb.volume)), tone(changePct(tn.volume, tb.volume))], [`${BRAND} gross profit`, signed(changePct(tn.gp, tb.gp)) + " (" + signedRupees(tn.gp - tb.gp) + " a week)", tone(changePct(tn.gp, tb.gp))]]
        .map(([label, value, cls]) => <div key={label} className="rounded-lg border bg-card p-4"><p className="text-xs text-muted-foreground">{label}</p><p className={`num mt-1 text-2xl font-semibold ${cls}`}>{value}</p></div>)}
    </section>
    <p className="text-sm text-muted-foreground">Cross-pack effect on gross profit in this scenario: <span className={`num font-medium ${tone(tn.crossPack)}`}>{signedRupees(tn.crossPack)}</span> a week. Volume that moves from a high-margin pack to a low-margin one can leave total volume flat while profit falls.</p>
  </div>
}

// ------------------------------------------------------------ Promotion

function PromoPanel({ base, pack, baseline, envelope }: { base: ApiScenario; pack: string; baseline: ApiScenarioResult; envelope: EnvelopeInfo }) {
  const mechanics = envelope.mechanics.filter((m) => m !== "none")
  const [mechanic, setMechanic] = useState(mechanics[0] ?? "TPR")
  const [weeks, setWeeks] = useState(2)
  const depths = envelope.depth_steps
  const { results, loading } = useSweep(depths.map((d) => withLever(base, pack, d === 0
    ? { promo_depth_pct: 0, mechanic: "none", promo_weeks_per_month: 0 }
    : { promo_depth_pct: d, mechanic, promo_weeks_per_month: weeks })))
  const bt = totals(baseline)
  const rows = depths.map((d, i) => {
    const r = results?.[i]
    if (!r) return { d, ok: false as const, refused: false }
    if (r.status === "REFUSED") return { d, ok: false as const, refused: true }
    const t = totals(r)
    return { d, ok: true as const, refused: false, volume: changePct(t.volume, bt.volume), spend: t.promoSpend, nsv: changePct(t.nsv, bt.nsv), gp: changePct(t.gp, bt.gp), units: t.volume }
  })
  const good = rows.filter((r): r is Extract<typeof r, { ok: true }> => r.ok)
  const peak = good.reduce<(typeof good)[number] | undefined>((a, r) => (!a || r.gp > a.gp ? r : a), undefined)
  const most = good.reduce<(typeof good)[number] | undefined>((a, r) => (!a || r.volume > a.volume ? r : a), undefined)
  const points: ChartPoint[] = rows.map((r) => r.ok ? { x: r.d, values: { volume: r.volume, revenue: r.nsv, margin: r.gp } } : { x: r.d, refused: r.refused, values: {} })
  return <div className="space-y-6">
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h3 className="font-display text-lg font-semibold">Promotion economics, {packLabel(pack)}</h3>
          <p className="text-xs text-muted-foreground">Depth, then incremental volume, trade spend, net revenue and gross profit for Aurora, each from the engine.</p></div>
        <div className="flex gap-3 text-xs text-muted-foreground">
          <label>Mechanic<select aria-label="Mechanic" value={mechanic} onChange={(e) => setMechanic(e.target.value)} className="mt-1 block rounded-md border bg-card px-2 py-1.5 text-sm text-foreground">{mechanics.map((m) => <option key={m}>{m}</option>)}</select></label>
          <label>Weeks per month: <span className="num text-foreground">{weeks}</span><input aria-label="Promo weeks per month" type="range" min="1" max="4" step="1" value={weeks} onChange={(e) => setWeeks(Number(e.target.value))} className="mt-1 block w-32" /></label>
        </div>
      </div>
      <div className={`mt-3 overflow-x-auto transition-opacity ${loading ? "opacity-60" : ""}`}>
        <LineChart ariaLabel="Promotion response curves" points={points} series={series} xLabel="Promotion depth" xFormat={(x) => `${x}%`} /></div>
      {peak && most && <p className="mt-3 rounded-md bg-secondary/70 p-3 text-sm">
        {most.d === peak.d
          ? <>Volume and gross profit both peak at <span className="num font-semibold">{peak.d}%</span> depth in this range.</>
          : <>Volume keeps rising up to <span className="num font-semibold">{most.d}%</span> depth ({signed(most.volume)}), but gross profit peaks at <span className="num font-semibold">{peak.d}%</span> ({signed(peak.gp)}) and is <span className={`num font-semibold ${tone(most.gp)}`}>{signed(most.gp)}</span> at {most.d}%. A deeper promotion buys volume it cannot pay for.</>}</p>}
    </section>
    <section className="overflow-x-auto rounded-lg border bg-card p-5">
      <table className="w-full min-w-[640px] text-sm">
        <thead><tr className="text-left text-xs text-muted-foreground"><th className="py-2 font-normal">Depth</th><th className="px-3 text-right font-normal">Incremental volume</th><th className="px-3 text-right font-normal">Added by this step</th><th className="px-3 text-right font-normal">Trade spend</th><th className="px-3 text-right font-normal">Net revenue</th><th className="px-3 text-right font-normal">Gross profit</th></tr></thead>
        <tbody>{rows.map((r, i) => {
          if (!r.ok) return <tr key={r.d} className={`border-t ${r.refused ? "hatch" : ""}`}><td className="num py-2">{r.d}%</td><td colSpan={5} className="px-3 text-muted-foreground">{r.refused ? "REFUSED: outside the supported data, no numbers" : "…"}</td></tr>
          const prev = rows.slice(0, i).reverse().find((x) => x.ok)
          const step = prev?.ok ? r.volume - prev.volume : undefined
          return <tr key={r.d} className="border-t"><td className="num py-2 font-medium">{r.d}%</td>
            <td className={`num px-3 text-right ${tone(r.volume)}`}>{signed(r.volume)}</td>
            <td className="num px-3 text-right text-muted-foreground">{step === undefined ? "n/a" : signed(step)}</td>
            <td className="num px-3 text-right">{r.spend ? rupees(r.spend) : "₹0"}</td>
            <td className={`num px-3 text-right ${tone(r.nsv)}`}>{signed(r.nsv)}</td>
            <td className={`num px-3 text-right font-semibold ${tone(r.gp)}`}>{signed(r.gp)}</td></tr>
        })}</tbody></table>
      <p className="mt-3 text-xs text-muted-foreground">&ldquo;Added by this step&rdquo; shrinks as depth rises: promotion response saturates, while the price given away keeps growing. Trade spend is the extra spend against the baseline, in rupees a week.</p>
    </section>
  </div>
}

// ------------------------------------------------- Joint decisions

export function jointPresets(pack: string): Array<{ name: string; blurb: string; levers: ApiScenario["levers"] } | undefined> {
  const index = PACKS.findIndex((p) => p.id === pack)
  const larger = PACKS[index + 1]?.id
  const short = PACKS[index].short
  const sku = skuFor(pack), promo = (depth: number): ApiLever => ({ ...baselineLever, promo_depth_pct: depth, mechanic: "TPR", promo_weeks_per_month: 2 })
  return [
    { name: `${short}: price +5%, same pack`, blurb: "Take price on this pack, no promotion.", levers: { [sku]: { ...baselineLever, price_index: 1.05 } } },
    larger ? { name: `${short}: price +5%, steer to ${PACKS[index + 1].short}`, blurb: "Take price here and make the next larger pack slightly cheaper.", levers: { [sku]: { ...baselineLever, price_index: 1.05 }, [skuFor(larger)]: { ...baselineLever, price_index: 0.98 } } } : undefined,
    { name: `${short}: price +5%, 10% promotion`, blurb: "Raise price and fund a light promotion.", levers: { [sku]: { ...promo(10), price_index: 1.05 } } },
    larger ? { name: `${PACKS[index + 1].short}: same price, 10% promotion`, blurb: "Hold price and promote the larger pack.", levers: { [skuFor(larger)]: promo(10) } } : undefined,
    { name: `${short}: lower price, 20% promotion`, blurb: "Cut price and promote deeply. Often the loser.", levers: { [sku]: { ...promo(20), price_index: 0.96 } } },
  ]
}

function JointDecisions({ pack, onAdd }: { pack: string; onAdd: Add }) {
  return <section className="rounded-lg border bg-card p-5">
    <h3 className="font-display text-lg font-semibold">Joint decisions</h3>
    <p className="mb-3 text-sm text-muted-foreground">Price, pack and promotion move together. Add a combination to compare it on the board; the engine evaluates all three levers at once.</p>
    <div className="grid gap-2 md:grid-cols-2">
      {jointPresets(pack).map((preset, i) => preset
        ? <button key={preset.name} type="button" onClick={() => onAdd(newScenario(preset.name, preset.levers))} className="rounded-md border p-3 text-left hover:border-primary hover:bg-primary/5"><span className="block text-sm font-medium">{preset.name}</span><span className="text-xs text-muted-foreground">{preset.blurb}</span></button>
        : <div key={i} className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">No larger observed pack than {packLabel(pack)}.</div>)}
    </div>
  </section>
}

// ------------------------------------------------------------ Workspace

export function LeverWorkspace({ scenarios, rawResults, activePack, envelope, defaults, assumptions, onAdd }: {
  scenarios: ApiScenario[]; rawResults: ApiScenarioResult[]; activePack: string; envelope?: EnvelopeInfo
  defaults?: EvidenceDefaults; assumptions: Assumption[]; onAdd: Add
}) {
  const [selected, setSelected] = useState(1)
  const [tab, setTab] = useState<"price" | "pack" | "promo">("price")
  const index = Math.min(selected, scenarios.length - 1)
  const base = scenarios[index], result = rawResults[index], baseline = rawResults[0]
  if (!envelope || !defaults || !base || !baseline || !result) return <p className="text-sm text-muted-foreground">Loading engine evidence…</p>
  const tabs = [["price", "Price"], ["pack", "Pack"], ["promo", "Promotion"]] as const
  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div role="tablist" aria-label="Lever" className="flex gap-1 rounded-lg bg-secondary p-1">
        {tabs.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} type="button" onClick={() => setTab(id)} className={`rounded-md px-4 py-2 text-sm ${tab === id ? "bg-ink font-medium text-white" : "hover:bg-card"}`}>{label}</button>)}
      </div>
      <label className="text-xs text-muted-foreground">Scenario to analyse<select aria-label="Scenario to analyse" value={index} onChange={(e) => setSelected(Number(e.target.value))} className="mt-1 block max-w-64 rounded-md border bg-card px-2 py-2 text-sm text-foreground">
        {scenarios.map((s, i) => <option key={i} value={i}>{s.name}</option>)}</select></label>
    </div>
    {tab === "price" && <PricePanel base={base} pack={activePack} baseline={baseline} envelope={envelope} defaults={defaults} assumptions={assumptions} onAdd={onAdd} />}
    {tab === "pack" && <PackPanel scenario={base} result={result} baseline={baseline} defaults={defaults} />}
    {tab === "promo" && <PromoPanel base={base} pack={activePack} baseline={baseline} envelope={envelope} />}
    <JointDecisions pack={activePack} onAdd={onAdd} />
  </div>
}
