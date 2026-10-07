import { Metric } from "@/components/bars"
import { RefusalDetail } from "@/components/refusal-detail"
import { ProvenanceChain } from "@/components/evidence-parts"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { signed } from "@/lib/catalog"
import type { ScenarioDelta, ScenarioResult } from "@/lib/types"

const chip = "rounded px-1.5 py-0.5 text-xs"

export function ComparisonBoard({ scenarios, onUseNearest, volumeGuardrailPct }: {
  scenarios: ScenarioResult[]; onUseNearest?: (id: string) => void; volumeGuardrailPct: number
}) {
  const ok = scenarios.filter((s) => s.status !== "REFUSED" && s.delta)
  const refused = scenarios.filter((s) => s.status === "REFUSED")
  const scale = (pick: (d: ScenarioDelta) => number, band = false) =>
    Math.max(1, ...ok.flatMap((s) => [s.delta, ...(band ? [s.p10, s.p90] : [])].map((d) => Math.abs(d ? pick(d) : 0)))) * 1.1
  const vMax = scale((d) => d.volumePct), rMax = scale((d) => d.revenuePct), mMax = scale((d) => d.marginPct, true)
  const breaches = (s: ScenarioResult) => !s.isBaseline && (s.delta?.volumePct ?? 0) < -volumeGuardrailPct
  const winner = ok.filter((s) => !s.isBaseline && !breaches(s) && (s.delta?.marginPct ?? 0) > 0.05)
    .sort((a, b) => (b.delta?.marginPct ?? 0) - (a.delta?.marginPct ?? 0))[0]
  const rank = new Map(ok.filter((s) => !s.isBaseline).sort((a, b) => (b.delta?.marginPct ?? 0) - (a.delta?.marginPct ?? 0)).map((s, i) => [s, i + 1]))
  const why = (s: ScenarioResult) => {
    const d = s.delta as ScenarioDelta, parts = []
    if (d.marginPct < 0) parts.push(`margin ${d.marginPct.toFixed(1)}%`)
    if (breaches(s)) parts.push(`volume ${d.volumePct.toFixed(1)}% beyond the ${volumeGuardrailPct}% limit`)
    return parts.join(" and ")
  }
  return <div className="space-y-3">
    {ok.map((s) => {
      const d = s.delta as ScenarioDelta, loser = d.marginPct < 0 && !s.isBaseline
      return <article key={s.scenarioId + s.name} className={`rounded-lg border bg-card px-5 py-4 ${s.isBaseline ? "border-dashed" : ""} ${s === winner ? "border-gain/60 ring-1 ring-gain/30" : ""}`}>
        <div className="grid items-center gap-x-8 gap-y-4 md:grid-cols-[minmax(0,13rem)_repeat(3,minmax(0,1fr))]">
          <div>
            <h3 className="font-display text-base font-semibold leading-tight">{rank.has(s) && <span className="num mr-2 text-muted-foreground">#{rank.get(s)}</span>}{s.name}</h3>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {s.isBaseline && <span className={`${chip} bg-secondary`}>Baseline</span>}
              {s === winner && <span className={`${chip} bg-gain/15 font-medium text-gain`}>Winning candidate</span>}
              {s.status === "EDGE" && <span className={`${chip} bg-edge/15 font-medium text-edge`}>Edge of data</span>}
              {loser && <span className={`${chip} bg-loss/10 font-medium text-loss`}>Loses: {why(s)}</span>}
              {breaches(s) && <span className={`${chip} bg-loss/10 font-medium text-loss`}>{why(s)}</span>}
              {s.source && <span className={`${chip} bg-edge/10 text-edge`}>From {s.source.methodology.split(" (")[0]} study</span>}
            </div>
          </div>
          <Metric label="Volume" value={d.volumePct} max={vMax} />
          <Metric label="Revenue" value={d.revenuePct} max={rMax} />
          <Tooltip>
            <TooltipTrigger render={<div className="min-w-0 cursor-help text-left" />}>
              <Metric label="Margin" value={d.marginPct} max={mMax} strong band={s.p10 && s.p90 ? [s.p10.marginPct, s.p90.marginPct] : undefined} extra={signed(d.marginPpt, 1).replace("%", " pp")} />
            </TooltipTrigger>
            <TooltipContent>P10 to P90 margin change: {s.p10?.marginPct.toFixed(1)}% to {s.p90?.marginPct.toFixed(1)}% (sensitivity band, not a confidence interval)</TooltipContent>
          </Tooltip>
        </div>
        {s.source && <details className="mt-3 text-sm"><summary className="cursor-pointer text-muted-foreground">Where this price came from</summary>
          <div className="mt-2"><ProvenanceChain source={s.source} scenarioId={s.scenarioId} resultHash={s.resultHash} /></div></details>}
      </article>
    })}
    {refused.map((s) => <article key={s.scenarioId + s.name} className="hatch rounded-lg border border-dashed border-loss/40 bg-card px-5 py-4">
      <div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-base font-semibold">{s.name}</h3><span className="rounded bg-loss px-1.5 py-0.5 text-xs font-medium text-white">REFUSED</span>
        {s.source && <span className={`${chip} bg-edge/10 text-edge`}>From {s.source.methodology.split(" (")[0]} study</span>}</div>
      {s.refusals?.length ? <RefusalDetail reasons={s.refusals} /> : <p className="mt-2 max-w-2xl text-sm">{s.refusalReason}</p>}
      <p className="mt-1 text-xs text-muted-foreground">The engine will not extrapolate outside supported data, so there are no numbers for this scenario.</p>
      {s.nearestSupportedId && <button type="button" onClick={() => onUseNearest?.(s.scenarioId)} className="mt-3 rounded-md border border-primary/40 bg-card px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary hover:text-primary-foreground">Use nearest supported scenario</button>}
    </article>)}
  </div>
}
