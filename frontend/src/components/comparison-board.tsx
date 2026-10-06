import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { ScenarioDelta, ScenarioResult } from "@/lib/types"

const fmt = (v: number, suffix = "%") => `${v >= 0.05 ? "+" : v <= -0.05 ? "−" : ""}${Math.abs(v).toFixed(1)}${suffix}`
const tone = (v: number) => (v < -0.05 ? "text-loss" : v > 0.05 ? "text-gain" : "text-muted-foreground")

/** Bar growing from a zero axis; optional P10-P90 whisker. */
function DivBar({ value, max, band, strong }: { value: number; max: number; band?: [number, number]; strong?: boolean }) {
  const pos = (v: number) => 50 + (Math.max(-max, Math.min(max, v)) / max) * 50
  const left = Math.min(50, pos(value)), width = Math.abs(pos(value) - 50)
  return <div className={`relative w-full ${strong ? "h-3" : "h-2"}`} aria-hidden="true">
    <div className="absolute inset-y-0 left-1/2 w-px bg-foreground/25" />
    <div className="bar absolute inset-y-0 rounded-[2px]" style={{ left: `${left}%`, width: `${width}%`, background: value < 0 ? "var(--loss)" : "var(--gain)", ["--origin" as string]: value < 0 ? "right" : "left" }} />
    {band && <div className="absolute top-1/2 h-px bg-foreground/70" style={{ left: `${pos(band[0])}%`, width: `${pos(band[1]) - pos(band[0])}%` }}>
      <span className="absolute -left-px -top-[3px] h-[7px] w-px bg-foreground/70" /><span className="absolute -right-px -top-[3px] h-[7px] w-px bg-foreground/70" />
    </div>}
  </div>
}

function Metric({ label, value, max, band, strong, extra }: { label: string; value: number; max: number; band?: [number, number]; strong?: boolean; extra?: string }) {
  return <div className="min-w-0">
    <div className="mb-1.5 flex items-baseline justify-between gap-2 text-xs text-muted-foreground"><span>{label}</span>{extra && <span>{extra}</span>}</div>
    <div className={`num ${strong ? "text-xl" : "text-base"} font-semibold ${tone(value)}`}>{fmt(value)}</div>
    <div className="mt-1.5"><DivBar value={value} max={max} band={band} strong={strong} /></div>
  </div>
}

export function ComparisonBoard({ scenarios, onUseNearest }: { scenarios: ScenarioResult[]; onUseNearest?: (id: string) => void }) {
  const ok = scenarios.filter((s) => s.status !== "REFUSED" && s.delta)
  const refused = scenarios.filter((s) => s.status === "REFUSED")
  const scale = (pick: (d: ScenarioDelta) => number, band = false) =>
    Math.max(1, ...ok.flatMap((s) => [s.delta, ...(band ? [s.p10, s.p90] : [])].map((d) => Math.abs(d ? pick(d) : 0)))) * 1.1
  const vMax = scale((d) => d.volumePct), rMax = scale((d) => d.revenuePct), mMax = scale((d) => d.marginPct, true)
  return <div className="space-y-3">
    {ok.map((s) => {
      const d = s.delta as ScenarioDelta, loser = d.marginPct < 0 && !s.isBaseline
      return <article key={s.scenarioId} className={`grid items-center gap-x-8 gap-y-4 rounded-lg border bg-card px-5 py-4 md:grid-cols-[minmax(0,13rem)_repeat(3,minmax(0,1fr))] ${s.isBaseline ? "border-dashed" : ""}`}>
        <div>
          <h3 className="font-display text-base font-semibold leading-tight">{s.name}</h3>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            {s.isBaseline && <span className="rounded bg-secondary px-1.5 py-0.5">Baseline</span>}
            {s.status === "EDGE" && <span className="rounded bg-edge/15 px-1.5 py-0.5 font-medium text-edge">Edge of data</span>}
            {loser && <span className="rounded bg-loss/10 px-1.5 py-0.5 font-medium text-loss">Worse than baseline</span>}
          </div>
        </div>
        <Metric label="Volume" value={d.volumePct} max={vMax} />
        <Metric label="Revenue" value={d.revenuePct} max={rMax} />
        <Tooltip>
          <TooltipTrigger render={<div className="min-w-0 cursor-help text-left" />}>
            <Metric label="Margin" value={d.marginPct} max={mMax} strong band={s.p10 && s.p90 ? [s.p10.marginPct, s.p90.marginPct] : undefined} extra={fmt(d.marginPpt, " pp")} />
          </TooltipTrigger>
          <TooltipContent>P10 to P90 margin change: {s.p10?.marginPct.toFixed(1)}% to {s.p90?.marginPct.toFixed(1)}% (sensitivity band, not a confidence interval)</TooltipContent>
        </Tooltip>
      </article>
    })}
    {refused.map((s) => <article key={s.scenarioId} className="hatch rounded-lg border border-dashed border-loss/40 bg-card px-5 py-4">
      <div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-base font-semibold">{s.name}</h3><span className="rounded bg-loss px-1.5 py-0.5 text-xs font-medium text-white">REFUSED</span></div>
      <p className="mt-2 max-w-2xl text-sm">{s.refusalReason}</p>
      <p className="mt-1 text-xs text-muted-foreground">The engine will not extrapolate outside supported data, so there are no numbers for this scenario.</p>
      {s.nearestSupportedId && <button type="button" onClick={() => onUseNearest?.(s.scenarioId)} className="mt-3 rounded-md border border-primary/40 bg-card px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary hover:text-primary-foreground">Use nearest supported scenario</button>}
    </article>)}
  </div>
}
