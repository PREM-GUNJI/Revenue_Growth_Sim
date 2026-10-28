import { useState } from "react"
import { Metric } from "@/components/bars"
import { RefusalDetail } from "@/components/refusal-detail"
import { ProvenanceChain } from "@/components/evidence-parts"
import { LabelTag } from "@/components/label-tag"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { rupees, signed, signedRupees, tone, units } from "@/lib/catalog"
import { useWorkspace } from "@/workspace/workspace-context"
import { useDetailMode } from "@/lib/preferences"
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

/** "Likely range" with the one explanation users need; the band comes from the engine's assumption draws. */
export function LikelyRange() {
  return <Tooltip>
    <TooltipTrigger render={<span className="cursor-help underline decoration-dotted underline-offset-2" />}>The likely range</TooltipTrigger>
    <TooltipContent>How much the answer moves if our assumptions are somewhat off. The engine re-runs each option across the documented assumption ranges; it is not a forecast interval.</TooltipContent>
  </Tooltip>
}

type SortKey = "name" | "units" | "revenue" | "gp" | "change" | "margin"

export function Why({ bridge }: { bridge: ScenarioBridge }) {
  const { currency } = useWorkspace()
  return <div className="flex flex-wrap items-center gap-1.5 text-xs" aria-label="Why the profit moved">
    <span className="text-muted-foreground">Why:</span>
    {BRIDGE.filter(([key]) => Math.abs(bridge[key]) >= 0.5).map(([key, label, meaning]) => <Tooltip key={key}>
      <TooltipTrigger render={<span className={`num cursor-help rounded border px-1.5 py-0.5 ${tone(bridge[key])}`} />}>{label} {signedRupees(bridge[key], currency)}</TooltipTrigger>
      <TooltipContent>{meaning}</TooltipContent></Tooltip>)}
    <span className="num font-semibold">= {signedRupees(bridge.total, currency)} a week</span>
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
  const [detail] = useDetailMode()
  const { currency } = useWorkspace()
  const ok = scenarios.filter((s) => s.status !== "REFUSED" && s.delta && s.abs)
  const refused = scenarios.filter((s) => s.status === "REFUSED")
  const scale = (pick: (d: ScenarioDelta) => number, band = false) =>
    Math.max(1, ...ok.flatMap((s) => [s.delta, ...(band ? [s.p10, s.p90] : [])].map((d) => Math.abs(d ? pick(d) : 0)))) * 1.1
  const vMax = scale((d) => d.volumePct), rMax = scale((d) => d.revenuePct), mMax = scale((d) => d.marginPct, true)
  const why = (s: ScenarioResult) => {
    const d = s.delta as ScenarioDelta, parts = []
    if (d.marginPct < 0) parts.push(`gross profit ${d.marginPct.toFixed(1)}%`)
    if (!s.isBaseline && d.volumePct < -volumeGuardrailPct) parts.push(`volume ${d.volumePct.toFixed(1)}% beyond the ${volumeGuardrailPct}% limit`)
    return parts.join(" and ")
  }
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
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2"><h2 className="font-display text-xl font-semibold tracking-tight">All options, side by side</h2><LabelTag label="Modeled" /></div>
        <span className="text-xs text-muted-foreground">Aurora only · {currency.code} / week · click a heading to sort</span>
      </div>
      <div className="overflow-x-auto rounded-xl border bg-card shadow-sm"><table className="w-full min-w-[860px] text-sm">
        <thead><tr className="border-b bg-secondary/40 text-xs text-muted-foreground">{head("name", "Scenario", "text-left")}{head("units", "Units")}{head("revenue", "Revenue")}{head("gp", "Gross profit")}{head("change", "Change vs baseline")}{head("margin", "Margin")}<th scope="col" className="px-3 py-2 text-right font-normal">Likely gross profit range</th></tr></thead>
        <tbody>{sorted.map((s) => {
          const a = s.abs!
          return <tr key={s.scenarioId + s.name} className={`border-t ${s === winner ? "bg-gain/5" : "hover:bg-secondary/20"}`}>
            <td className="px-3 py-2.5 font-medium">{s.name}{s.isBaseline && <span className={`${chip} ml-2 bg-secondary font-normal`}>Baseline</span>}{s === winner && <span className={`${chip} ml-2 bg-gain/15 font-medium text-gain`}>Winner</span>}</td>
            <td className="num px-3 py-2.5 text-right">{units(a.units)}</td><td className="num px-3 py-2.5 text-right">{rupees(a.revenue, currency)}</td><td className="num px-3 py-2.5 text-right font-semibold">{rupees(a.gp, currency)}</td>
            <td className={`num px-3 py-2.5 text-right ${s.isBaseline ? "text-muted-foreground" : tone(a.gpChange)}`}>{s.isBaseline ? "—" : <>{signedRupees(a.gpChange, currency)} <span className="text-xs">({signed(s.delta!.marginPct)})</span></>}</td>
            <td className="num px-3 py-2.5 text-right">{a.marginPct.toFixed(1)}%</td>
            <td className="num px-3 py-2.5 text-right text-xs text-muted-foreground">{rupees(a.gpRange[0], currency)} to {rupees(a.gpRange[1], currency)}</td></tr>
        })}
          {refused.map((s) => <tr key={s.scenarioId + s.name} className="hatch border-t"><td className="px-3 py-2.5 font-medium">{s.name}</td><td colSpan={6} className="px-3 py-2.5 text-loss">REFUSED: we haven't seen this in the data, so we won't guess. No numbers.</td></tr>)}</tbody></table></div>
      <p className="text-xs text-muted-foreground"><LikelyRange /> shows how much Aurora's gross profit moves if our assumptions are somewhat off{detail && " (P10 to P90 across the assumption ranges)"}. It is an assumption range, not a forecast interval.</p>
    </section>}

    <div className="space-y-3">
      {ok.map((s) => {
        const d = s.delta as ScenarioDelta, a = s.abs!, loser = d.marginPct < 0 && !s.isBaseline
        return <article key={s.scenarioId + s.name} className={`rounded-xl border bg-card px-5 py-4 shadow-sm transition ${s.isBaseline ? "border-dashed" : ""} ${s === winner ? "border-gain/60 ring-1 ring-gain/30" : "hover:border-foreground/15"}`}>
          <div className="grid items-center gap-x-8 gap-y-4 md:grid-cols-[minmax(0,13rem)_repeat(3,minmax(0,1fr))]">
            <div>
              <h3 className="font-display text-base font-semibold leading-tight">{s.name}</h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {s.isBaseline && <span className={`${chip} bg-secondary`}>Baseline</span>}
                {s === winner && <span className={`${chip} bg-gain/15 font-medium text-gain`}>Winning candidate</span>}
                {s.status === "EDGE" && <span className={`${chip} bg-edge/15 font-medium text-edge`}>Edge of data</span>}
                {loser && <span className={`${chip} bg-loss/10 font-medium text-loss`}>Worse than baseline: {why(s)}</span>}
                {breaches(s) && <span className={`${chip} bg-loss/10 font-medium text-loss`}>{why(s)}</span>}
                {s.source && <span className={`${chip} bg-edge/10 text-edge`}>From {s.source.methodology.split(" (")[0]} study</span>}
              </div>
            </div>
            <Metric label="Volume" value={d.volumePct} max={vMax} extra={units(a.units) + " units"} />
            <Metric label="Revenue" value={d.revenuePct} max={rMax} extra={rupees(a.revenue, currency)} />
            <Tooltip>
              <TooltipTrigger render={<div className="min-w-0 cursor-help text-left" />}>
                <Metric label="Gross profit" value={d.marginPct} max={mMax} strong band={s.p10 && s.p90 ? [s.p10.marginPct, s.p90.marginPct] : undefined} extra={rupees(a.gp, currency) + " · margin " + signed(d.marginPpt, 1).replace("%", " pp")} />
              </TooltipTrigger>
              <TooltipContent>Likely range for Aurora's gross profit: {rupees(a.gpRange[0], currency)} to {rupees(a.gpRange[1], currency)} a week ({signed(s.p10?.marginPct ?? 0)} to {signed(s.p90?.marginPct ?? 0)}) if our assumptions are somewhat off. Not a forecast interval.</TooltipContent>
            </Tooltip>
          </div>
          {!s.isBaseline && s.bridge && <div className="mt-3"><Why bridge={s.bridge} /></div>}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {s.assumptionIds && onShowAssumptions && <button type="button" onClick={() => onShowAssumptions(s.assumptionIds as string[])} className="rounded font-medium text-primary underline-offset-4 hover:underline">Rests on {s.assumptionIds.length} assumptions</button>}
            {detail && <CopyId id={s.scenarioId} />}
            {detail && s.resultHash && <span className="font-mono" title="Hash of the full result. Identical settings give an identical hash.">result {s.resultHash.slice(0, 8)}</span>}
          </div>
          {s.source && <details className="mt-3 text-sm"><summary className="cursor-pointer text-muted-foreground">Where this price came from</summary>
            <div className="mt-2"><ProvenanceChain source={s.source} scenarioId={s.scenarioId} resultHash={s.resultHash} /></div></details>}
        </article>
      })}
      {refused.map((s) => <article key={s.scenarioId + s.name} className="hatch rounded-xl border border-dashed border-loss/40 bg-card/80 px-5 py-4 opacity-95">
        <div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-base font-semibold">{s.name}</h3><span className="rounded bg-loss px-1.5 py-0.5 text-xs font-medium text-white">REFUSED</span>
          {s.source && <span className={`${chip} bg-edge/10 text-edge`}>From {s.source.methodology.split(" (")[0]} study</span>}</div>
        {s.refusals?.length ? <RefusalDetail reasons={s.refusals} /> : <p className="mt-2 max-w-2xl text-sm">{s.refusalReason}</p>}
        <p className="mt-1 text-xs text-muted-foreground">We won't guess outside the data, so there are no numbers for this option.{s.nearestSupportedId && " The closest option we can stand behind is one click away."}</p>
        {s.nearestSupportedId && <button type="button" onClick={() => onUseNearest?.(s.scenarioId)} className="mt-3 rounded-md border border-primary/40 bg-card px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary hover:text-primary-foreground">Use nearest supported scenario</button>}
      </article>)}
    </div>
  </div>
}
