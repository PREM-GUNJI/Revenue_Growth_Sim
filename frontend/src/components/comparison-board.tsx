import { useState } from "react"
import { Metric } from "@/components/bars"
import { ProvenanceChain } from "@/components/evidence-parts"
import { LabelTag } from "@/components/label-tag"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { rupees, signed, signedRupees, tone, units } from "@/lib/catalog"
import type { ScenarioBridge, ScenarioDelta, ScenarioResult } from "@/lib/types"

const chip = "rounded px-1.5 py-0.5 text-xs"
const BRIDGE: Array<[keyof Omit<ScenarioBridge, "total">, string, string]> = [
  ["price", "Price", "Change in price on the units we would have sold anyway"],
  ["volume", "Volume", "Units gained or lost on the packs whose price or promotion moved"],
  ["crossPack", "Cross-pack", "Volume moving between our own packs"],
  ["promo", "Promotion", "Extra revenue from promotional lift"],
  ["trade", "Trade terms", "Change in trade spend, fixed terms plus promotion funding"],
  ["cogs", "Unit costs", "Change in cost of goods from the new volume or input costs"],
]

type SortKey = "name" | "units" | "revenue" | "gp" | "change" | "margin"

export function Why({ bridge }: { bridge: ScenarioBridge }) {
  return <div className="flex flex-wrap items-center gap-1.5 text-xs" aria-label="Why the profit moved">
    <span className="text-muted-foreground">Why:</span>
    {BRIDGE.filter(([key]) => Math.abs(bridge[key]) >= 0.5).map(([key, label, meaning]) => <Tooltip key={key}>
      <TooltipTrigger render={<span className={`num cursor-help rounded border px-1.5 py-0.5 ${tone(bridge[key])}`} />}>{label} {signedRupees(bridge[key])}</TooltipTrigger>
      <TooltipContent>{meaning}</TooltipContent></Tooltip>)}
    <span className="num font-semibold">= {signedRupees(bridge.total)} a week</span>
  </div>
}

function CopyId({ id }: { id: string }) {
  const [copied, setCopied] = useState(false)
  return <button type="button" title="Copy the full scenario ID. The same ID and settings always reproduce the same numbers."
    onClick={() => { void navigator.clipboard?.writeText(id).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) }).catch(() => undefined) }}
    className="rounded font-mono text-[11px] text-muted-foreground hover:text-foreground">{copied ? "copied" : "ID " + id.slice(0, 8)}</button>
}

export function ComparisonBoard({ scenarios, onUseNearest, volumeGuardrailPct, onShowAssumptions }: {
  scenarios: ScenarioResult[]; onUseNearest?: (id: string) => void; volumeGuardrailPct: number; onShowAssumptions?: (ids: string[]) => void
}) {
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "gp", desc: true })
  const ok = scenarios.filter((s) => s.status !== "REFUSED" && s.delta && s.abs)
  const refused = scenarios.filter((s) => s.status === "REFUSED")
  const scale = (pick: (d: ScenarioDelta) => number, band = false) =>
    Math.max(1, ...ok.flatMap((s) => [s.delta, ...(band ? [s.p10, s.p90] : [])].map((d) => Math.abs(d ? pick(d) : 0)))) * 1.1
  const vMax = scale((d) => d.volumePct), rMax = scale((d) => d.revenuePct), mMax = scale((d) => d.marginPct, true)
  const breaches = (s: ScenarioResult) => !s.isBaseline && (s.delta?.volumePct ?? 0) < -volumeGuardrailPct
  const winner = ok.filter((s) => !s.isBaseline && !breaches(s) && (s.delta?.marginPct ?? 0) > 0.05)
    .sort((a, b) => (b.delta?.marginPct ?? 0) - (a.delta?.marginPct ?? 0))[0]

  const value = (s: ScenarioResult, key: SortKey): number | string => {
    const a = s.abs
    if (!a) return 0
    return { name: s.name, units: a.units, revenue: a.revenue, gp: a.gp, change: a.gpChange, margin: a.marginPct }[key]
  }
  const sorted = [...ok].sort((x, y) => {
    const a = value(x, sort.key), b = value(y, sort.key)
    const order = typeof a === "string" ? a.localeCompare(String(b)) : (a as number) - (b as number)
    return sort.desc ? -order : order
  })
  const head = (key: SortKey, label: string, align = "text-right") => <th scope="col" aria-sort={sort.key === key ? (sort.desc ? "descending" : "ascending") : "none"} className={`px-3 py-2 font-normal ${align}`}>
    <button type="button" onClick={() => setSort((cur) => ({ key, desc: cur.key === key ? !cur.desc : key !== "name" }))} className="hover:text-foreground">{label}{sort.key === key ? (sort.desc ? " ↓" : " ↑") : ""}</button></th>

  return <div className="space-y-5">
    {ok.length > 0 && <section aria-label="Summary table" className="space-y-2">
      <div className="flex flex-wrap items-center gap-2"><h2 className="font-display text-lg font-semibold">All options, side by side</h2><LabelTag label="Modeled" />
        <span className="text-xs text-muted-foreground">Aurora only, per typical week, in rupees. Click a heading to sort.</span></div>
      <div className="overflow-x-auto rounded-lg border bg-card"><table className="w-full min-w-[860px] text-sm">
        <thead><tr className="text-xs text-muted-foreground">{head("name", "Scenario", "text-left")}{head("units", "Units")}{head("revenue", "Revenue")}{head("gp", "Gross profit")}{head("change", "Change vs baseline")}{head("margin", "Margin")}<th scope="col" className="px-3 py-2 text-right font-normal">Gross profit range</th></tr></thead>
        <tbody>{sorted.map((s) => {
          const a = s.abs!
          return <tr key={s.scenarioId + s.name} className={`border-t ${s === winner ? "bg-gain/5" : ""}`}>
            <td className="px-3 py-2.5 font-medium">{s.name}{s.isBaseline && <span className={`${chip} ml-2 bg-secondary font-normal`}>Baseline</span>}{s === winner && <span className={`${chip} ml-2 bg-gain/15 font-medium text-gain`}>Winner</span>}</td>
            <td className="num px-3 py-2.5 text-right">{units(a.units)}</td><td className="num px-3 py-2.5 text-right">{rupees(a.revenue)}</td><td className="num px-3 py-2.5 text-right font-semibold">{rupees(a.gp)}</td>
            <td className={`num px-3 py-2.5 text-right ${s.isBaseline ? "text-muted-foreground" : tone(a.gpChange)}`}>{s.isBaseline ? "—" : <>{signedRupees(a.gpChange)} <span className="text-xs">({signed(s.delta!.marginPct)})</span></>}</td>
            <td className="num px-3 py-2.5 text-right">{a.marginPct.toFixed(1)}%</td>
            <td className="num px-3 py-2.5 text-right text-xs text-muted-foreground">{rupees(a.gpRange[0])} to {rupees(a.gpRange[1])}</td></tr>
        })}
          {refused.map((s) => <tr key={s.scenarioId + s.name} className="hatch border-t"><td className="px-3 py-2.5 font-medium">{s.name}</td><td colSpan={6} className="px-3 py-2.5 text-loss">REFUSED: outside the data the engine can support, so there are no numbers.</td></tr>)}</tbody></table></div>
      <p className="text-xs text-muted-foreground">The range is the engine's P10 to P90 for Aurora's total gross profit across the assumption ranges. It is a sensitivity band, not a confidence interval.</p>
    </section>}

    <div className="space-y-3">
      {ok.map((s) => {
        const d = s.delta as ScenarioDelta, a = s.abs!, loser = d.marginPct < 0 && !s.isBaseline
        return <article key={s.scenarioId + s.name} className={`rounded-lg border bg-card px-5 py-4 ${s.isBaseline ? "border-dashed" : ""} ${s === winner ? "border-gain/60 ring-1 ring-gain/30" : ""}`}>
          <div className="grid items-center gap-x-8 gap-y-4 md:grid-cols-[minmax(0,13rem)_repeat(3,minmax(0,1fr))]">
            <div>
              <h3 className="font-display text-base font-semibold leading-tight">{s.name}</h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {s.isBaseline && <span className={`${chip} bg-secondary`}>Baseline</span>}
                {s === winner && <span className={`${chip} bg-gain/15 font-medium text-gain`}>Winning candidate</span>}
                {s.status === "EDGE" && <span className={`${chip} bg-edge/15 font-medium text-edge`}>Edge of data</span>}
                {loser && <span className={`${chip} bg-loss/10 font-medium text-loss`}>Worse than baseline</span>}
                {breaches(s) && <span className={`${chip} bg-loss/10 font-medium text-loss`}>Volume guardrail breached</span>}
                {s.source && <span className={`${chip} bg-edge/10 text-edge`}>From {s.source.methodology.split(" (")[0]} study</span>}
              </div>
            </div>
            <Metric label="Volume" value={d.volumePct} max={vMax} extra={units(a.units) + " units"} />
            <Metric label="Revenue" value={d.revenuePct} max={rMax} extra={rupees(a.revenue)} />
            <Tooltip>
              <TooltipTrigger render={<div className="min-w-0 cursor-help text-left" />}>
                <Metric label="Gross profit" value={d.marginPct} max={mMax} strong band={s.p10 && s.p90 ? [s.p10.marginPct, s.p90.marginPct] : undefined} extra={rupees(a.gp) + " · margin " + signed(d.marginPpt, 1).replace("%", " pp")} />
              </TooltipTrigger>
              <TooltipContent>P10 to P90 for Aurora's gross profit: {rupees(a.gpRange[0])} to {rupees(a.gpRange[1])} a week ({signed(s.p10?.marginPct ?? 0)} to {signed(s.p90?.marginPct ?? 0)}). Sensitivity band, not a confidence interval.</TooltipContent>
            </Tooltip>
          </div>
          {!s.isBaseline && s.bridge && <div className="mt-3"><Why bridge={s.bridge} /></div>}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {s.assumptionIds && onShowAssumptions && <button type="button" onClick={() => onShowAssumptions(s.assumptionIds as string[])} className="rounded font-medium text-primary underline-offset-4 hover:underline">Rests on {s.assumptionIds.length} assumptions</button>}
            <CopyId id={s.scenarioId} />
            {s.resultHash && <span className="font-mono" title="Hash of the full result. Identical settings give an identical hash.">result {s.resultHash.slice(0, 8)}</span>}
          </div>
          {s.source && <details className="mt-3 text-sm"><summary className="cursor-pointer text-muted-foreground">Where this price came from</summary>
            <div className="mt-2"><ProvenanceChain source={s.source} scenarioId={s.scenarioId} resultHash={s.resultHash} /></div></details>}
        </article>
      })}
      {refused.map((s) => <article key={s.scenarioId + s.name} className="hatch rounded-lg border border-dashed border-loss/40 bg-card px-5 py-4">
        <div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-base font-semibold">{s.name}</h3><span className="rounded bg-loss px-1.5 py-0.5 text-xs font-medium text-white">REFUSED</span>
          {s.source && <span className={`${chip} bg-edge/10 text-edge`}>From {s.source.methodology.split(" (")[0]} study</span>}</div>
        <p className="mt-2 max-w-2xl text-sm">{s.refusalReason}</p>
        <p className="mt-1 text-xs text-muted-foreground">The engine will not extrapolate outside supported data, so there are no numbers for this scenario.</p>
        {s.nearestSupportedId && <button type="button" onClick={() => onUseNearest?.(s.scenarioId)} className="mt-3 rounded-md border border-primary/40 bg-card px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary hover:text-primary-foreground">Use nearest supported scenario</button>}
      </article>)}
    </div>
  </div>
}
