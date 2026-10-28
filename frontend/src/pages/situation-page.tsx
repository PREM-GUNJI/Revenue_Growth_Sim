import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { LabelTag } from "@/components/label-tag"
import type { SituationProbe, SituationSku } from "@/lib/api"
import { baselineLever, newScenario, packLabel, packOf, rupees, signed, signedRupees, tone, units } from "@/lib/catalog"
import { money as moneyPrice, type Currency } from "@/lib/currency"
import { useDetailMode } from "@/lib/preferences"
import { useWorkspace } from "@/workspace/workspace-context"

const th = "px-3 py-2 text-right font-normal"
const td = "num px-3 py-2.5 text-right"

const COST_ASSUMPTIONS = ["A-013", "A-014a", "A-014b", "A-014c", "A-014d", "A-015", "A-016"]

function Kpi({ label, value, note, emphasis }: { label: string; value: string; note?: string; emphasis?: boolean }) {
  return <div className={`rounded-xl border p-4 transition ${emphasis ? "border-ink/20 bg-ink text-white shadow-sm" : "bg-card"}`}>
    <p className={`text-xs font-medium ${emphasis ? "text-white/70" : "text-muted-foreground"}`}>{label}</p>
    <p className={`num mt-1 text-2xl font-semibold tracking-tight ${emphasis ? "text-white" : ""}`}>{value}</p>
    {note && <p className={`mt-1 text-xs ${emphasis ? "text-white/60" : "text-muted-foreground"}`}>{note}</p>}
  </div>
}

/** One engine probe: what a small move does to the brand's weekly gross profit, with a way to put it on the comparison. */
function ProbeCell({ probe, onAdd, currency }: { probe?: SituationProbe; onAdd: () => void; currency: Currency }) {
  if (!probe) return <td className={td}>…</td>
  if (probe.status === "REFUSED") return <td className="px-3 py-2.5 text-right text-xs text-loss" title={probe.reasons?.join("; ")}>Outside our data, no estimate</td>
  const change = probe.focal_gp_change ?? 0
  const fmt = (v: number) => signedRupees(v, currency)
  return <td className="px-3 py-2.5 text-right">
    <div className={`num font-semibold ${tone(change)}`} title={`Likely range: ${fmt(probe.focal_gp_change_p10 ?? change)} to ${fmt(probe.focal_gp_change_p90 ?? change)}`}>{fmt(change)}<span className="ml-1 text-xs font-normal text-muted-foreground">/wk</span></div>
    <div className="text-xs text-muted-foreground">pack volume {signed(probe.pack_volume_pct ?? 0)}</div>
    <button type="button" onClick={onAdd} className="mt-1 rounded text-xs font-medium text-primary underline-offset-4 hover:underline">Add to compare</button>
  </td>
}

export function SituationPage() {
  const { situation, workspace, workspaceId, best, results, addExternal, openAssumptions, loading, currency } = useWorkspace()
  const navigate = useNavigate()
  const [detail] = useDetailMode()
  const [fullPnl, setFullPnl] = useState(false)
  if (!situation) return <p className="text-sm text-muted-foreground" role="status">Loading the baseline…</p>
  const focal = situation.skus.filter((s) => s.is_focal)
  const t = situation.totals.focal
  const days = situation.period
  const fmt = (v: number) => rupees(v, currency)
  const sfmt = (v: number) => signedRupees(v, currency)
  const addPrice = (s: SituationSku) => addExternal(newScenario(`+3% price, ${packLabel(packOf(s.sku_id))}`, { [s.sku_id]: { ...baselineLever, price_index: 1.03 } }))
  const addPromo = (s: SituationSku) => addExternal(newScenario(`10% promotion, ${packLabel(packOf(s.sku_id))}`, { [s.sku_id]: { ...baselineLever, promo_depth_pct: 10, mechanic: "TPR", promo_weeks_per_month: 2 } }))
  const base = `/w/${workspaceId}`
  const gain = best && best.abs && best.abs.gpChange > 0 ? best : undefined
  const cost = situation.cost_shock_probe

  return <>
    <header className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Step 1 of 4 · Situation</p>
        <span className="rounded-md border bg-secondary/80 px-2 py-0.5 text-[11px] font-semibold tracking-wide">{currency.code}</span>
      </div>
      <h1 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">{workspace?.name}</h1>
      <p className="max-w-3xl text-base leading-relaxed text-foreground/80">{workspace?.description || "No business question written for this case yet. Add one in the case name or description so everyone is solving the same problem."}</p>
      <p className="text-sm text-muted-foreground">{situation.focal_brand} against {situation.competitors.join(" and ")} · synthetic sparkling-drinks market · {days.history_weeks} weeks across {days.regions.length} regions · {currency.code} per typical week</p>
    </header>

    {gain?.abs && <section aria-label="Best option so far" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gain/40 bg-gain/5 p-4">
      <p className="text-sm"><span className="font-medium">Best option so far:</span> {gain.name}, <span className="num font-semibold text-gain">{sfmt(gain.abs.gpChange)}</span> gross profit a week
        {gain.delta && <> ({signed(gain.delta.marginPct)}) with volume {signed(gain.delta.volumePct)}</>} <LabelTag label="Modeled" /></p>
      <Link to={`${base}/board`} className="text-sm font-medium text-primary underline-offset-4 hover:underline">See it on the comparison</Link>
    </section>}

    <section aria-label="Where the brand stands" className="space-y-3">
      <h2 className="font-display text-xl font-semibold">Where {situation.focal_brand} stands today</h2>
      <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground" aria-label="How to read this page">
        How to read this page: figures are <LabelTag label="Modeled" /> (an estimated typical week, calculated by the engine) unless marked <LabelTag label="Observed" /> (read straight from the sales history). <LabelTag label="Assumed" /> inputs are documented, not measured.</p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Kpi label="Units sold (estimated)" value={units(t.units)} note={`${units(t.litres)} litres`} />
        <Kpi label="Revenue (gross sales)" value={fmt(t.gsv)} />
        <Kpi label="Gross profit" value={fmt(t.gp)} note="after trade terms and unit costs" emphasis />
        <Kpi label="Gross margin" value={t.gp_margin_pct.toFixed(1) + "%"} note="of net sales" />
        <Kpi label="Share of market value" value={situation.totals.focal_value_share_pct.toFixed(1) + "%"} note={`of ${fmt(situation.totals.market.gsv)} a week`} />
      </div>
      <p className="text-xs text-muted-foreground">{days.basis} This is an estimated typical week, so it can differ slightly from any single week of actual sales.</p>
    </section>

    <section aria-label="Profit and loss by pack" className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-display text-xl font-semibold">Weekly profit and loss by pack</h2>
        <button type="button" aria-pressed={fullPnl} onClick={() => setFullPnl((v) => !v)} className="rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-secondary">{fullPnl ? "Show summary" : "Show full P&L"}</button></div>
      <div className="overflow-x-auto rounded-lg border bg-card"><table className={`w-full text-sm ${fullPnl ? "min-w-[820px]" : "min-w-[560px]"}`}>
        <thead><tr className="text-xs text-muted-foreground"><th className="px-3 py-2 text-left font-normal">Pack</th><th className={th}>Shelf price</th>{fullPnl && <th className={th}>Per litre</th>}<th className={th}>Units</th><th className={th}>Revenue</th>{fullPnl && <><th className={th}>Trade terms</th><th className={th}>Net sales</th><th className={th}>Unit costs</th></>}<th className={th}>Gross profit</th><th className={th}>Margin</th></tr></thead>
        <tbody>{focal.map((s) => <tr key={s.sku_id} className="border-t">
          <td className="px-3 py-2.5 font-medium">{packLabel(packOf(s.sku_id))}</td>
          <td className={td}>{moneyPrice(s.price, currency)}</td>{fullPnl && <td className={td}>{moneyPrice(s.price_per_litre, currency)}</td>}<td className={td}>{units(s.baseline_units)}</td>
          <td className={td}>{fmt(s.baseline_gsv)}</td>
          {fullPnl && <><td className={td + " text-muted-foreground"}>{fmt(s.baseline_trade)}</td><td className={td}>{fmt(s.baseline_nsv)}</td><td className={td + " text-muted-foreground"}>{fmt(s.baseline_cogs)}</td></>}
          <td className={td + " font-semibold"}>{fmt(s.baseline_gp)}</td><td className={td}>{s.gp_margin_pct.toFixed(1)}%</td></tr>)}
          <tr className="border-t-2 font-semibold"><td className="px-3 py-2.5">{situation.focal_brand} total</td><td />{fullPnl && <td />}<td className={td}>{units(t.units)}</td><td className={td}>{fmt(t.gsv)}</td>
            {fullPnl && <><td className={td}>{fmt(t.trade)}</td><td className={td}>{fmt(t.nsv)}</td><td className={td}>{fmt(t.cogs)}</td></>}<td className={td}>{fmt(t.gp)}</td><td className={td}>{t.gp_margin_pct.toFixed(1)}%</td></tr></tbody></table></div>
      <p className="text-xs text-muted-foreground">Unit costs and trade terms are {COST_ASSUMPTIONS.length} documented assumptions{detail && ` (${COST_ASSUMPTIONS.join(", ")})`}. <button type="button" onClick={() => openAssumptions(situation.assumption_ids)} className="font-medium text-primary underline-offset-4 hover:underline">View them</button></p>
    </section>

    <section aria-label="Against competitors" className="space-y-2">
      <div className="flex items-center gap-2"><h2 className="font-display text-xl font-semibold">Price position and promotion habit</h2><LabelTag label="Observed" /></div>
      <div className="overflow-x-auto rounded-lg border bg-card"><table className="w-full min-w-[720px] text-sm">
        <thead><tr className="text-xs text-muted-foreground"><th className="px-3 py-2 text-left font-normal">Pack</th><th className={th}>Our price</th>
          {situation.competitors.map((c) => <th key={c} className={th}>vs {c}</th>)}<th className={th}>Weeks on promotion</th><th className={th}>Typical depth</th><th className={th}>Usual mechanic</th></tr></thead>
        <tbody>{focal.map((s) => <tr key={s.sku_id} className="border-t">
          <td className="px-3 py-2.5 font-medium">{packLabel(packOf(s.sku_id))}</td><td className={td}>{moneyPrice(s.price, currency)}</td>
          {situation.competitors.map((c) => <td key={c} className={td}>{signed(s.price_gap_vs_competitors_pct?.[c] ?? 0)}</td>)}
          <td className={td}>{s.history.promo_week_share_pct.toFixed(0)}%</td><td className={td}>{s.history.avg_promo_depth_pct.toFixed(0)}%</td><td className="px-3 py-2.5 text-right">{s.history.main_mechanic}</td></tr>)}</tbody></table></div>
      <p className="text-xs text-muted-foreground">A positive gap means {situation.focal_brand} is priced above that competitor. Prices and promotion history are read from the synthetic sales data.</p>
    </section>

    <section aria-label="Where the opportunities are" className="space-y-2">
      <div className="flex items-center gap-2"><h2 className="font-display text-xl font-semibold">Where the opportunities are</h2><LabelTag label="Modeled" /></div>
      <p className="max-w-3xl text-sm text-muted-foreground">One small move at a time, run through the engine against the baseline: {situation.probe_definitions.price}; {situation.probe_definitions.promo}. The change is {situation.focal_brand}'s gross profit a week. Hover a figure for its likely range. How strongly shoppers react to price is an <LabelTag label="Assumed" /> input.</p>
      <div className="overflow-x-auto rounded-lg border bg-card"><table className="w-full min-w-[720px] text-sm">
        <thead><tr className="text-xs text-muted-foreground"><th className="px-3 py-2 text-left font-normal">Pack</th><th className={th}>Price sensitivity</th><th className={th}>Raise the price 3%</th><th className={th}>Run a 10% promotion</th></tr></thead>
        <tbody>{focal.map((s) => <tr key={s.sku_id} className="border-t">
          <td className="px-3 py-2.5 font-medium">{packLabel(packOf(s.sku_id))}</td>
          <td className="px-3 py-2.5 text-right text-xs"><span className="text-foreground">+1% price, about {Math.abs(s.own_elasticity).toFixed(1)}% fewer sold</span>
            {detail && <span className="block font-mono text-muted-foreground">{s.own_elasticity} {s.own_elasticity_id}</span>}</td>
          <ProbeCell probe={s.price_probe} onAdd={() => addPrice(s)} currency={currency} /><ProbeCell probe={s.promo_probe} onAdd={() => addPromo(s)} currency={currency} /></tr>)}</tbody></table></div>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-loss/30 bg-loss/5 p-4">
        <p className="max-w-3xl text-sm"><span className="font-medium">If {cost.applies_to} rise {cost.shock_pct.toFixed(0)}%:</span>{" "}
          {cost.status === "REFUSED" ? "this is outside our data, so we won't estimate it." : <><span className={`num font-semibold ${tone(cost.focal_gp_change ?? 0)}`}>{sfmt(cost.focal_gp_change ?? 0)}</span> gross profit a week ({signed(cost.focal_gp_pct ?? 0)}) before any response.</>} <LabelTag label="Modeled" /></p>
        {cost.status !== "REFUSED" && <button type="button" onClick={() => addExternal({ ...newScenario("Input costs +8%, no response"), cost_shock: { aluminium_pct: cost.shock_pct, pet_resin_pct: cost.shock_pct, sugar_pct: cost.shock_pct } })} className="rounded-md border bg-card px-3 py-1.5 text-sm font-medium hover:bg-secondary">Add as a scenario to beat</button>}
      </div>
    </section>

    <section aria-label="Next steps" className="flex flex-wrap items-center gap-3 rounded-lg border bg-card p-5">
      <p className="mr-auto max-w-xl text-sm text-muted-foreground">Next: build options by setting price, pack and promotion together, compare them with the baseline, then ask the assistant for a recommendation. {loading && "Updating results…"} {results.length > 0 && `${results.length} scenarios are in this case.`}</p>
      <button type="button" onClick={() => navigate(`${base}/simulator`)} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">Build options</button>
      <button type="button" onClick={() => navigate(`${base}/board`)} className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-secondary">Compare</button>
      <button type="button" onClick={() => navigate(`${base}/assistant`)} className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-secondary">Ask the assistant</button>
    </section>
  </>
}
