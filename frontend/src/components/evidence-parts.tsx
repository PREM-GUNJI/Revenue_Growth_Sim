import type { ReactNode } from "react"
import { Metric } from "@/components/bars"
import type { ApiScenario, ApiScenarioResult, Provenance, ResearchScenarioRow } from "@/lib/api"
import { SYNTHETIC, changePct, inr, packLabel, totals } from "@/lib/catalog"

export function SyntheticBanner({ children }: { children?: ReactNode }) {
  return <div className="rounded-md border border-edge/40 bg-edge/10 px-4 py-3 text-sm">
    <p className="font-display font-semibold text-edge">{SYNTHETIC}</p>
    <p className="mt-1 text-foreground/80">{children ?? "Generated respondents and comments, not real customers or real research. Results are illustrative and only propose candidate prices; volume, revenue and margin come from the deterministic engine."}</p>
  </div>
}

const short = (hash: string, n = 10) => hash.slice(0, n)

/** research_id to methodology to data hash to candidate to scenario_id to model version to result_hash. */
export function ProvenanceChain({ source, scenarioId, resultHash }: { source: Provenance; scenarioId?: string; resultHash?: string }) {
  const c = source.candidate
  const step = (title: string, body: ReactNode) => <li className="relative pl-5 before:absolute before:left-0 before:top-2 before:size-1.5 before:rounded-full before:bg-primary">
    <span className="text-muted-foreground">{title}</span> <span className="text-foreground">{body}</span></li>
  return <ol className="space-y-1.5 border-l border-primary/30 pl-3 text-xs leading-5">
    {step("Study", <>{source.methodology} <code>{source.research_id}</code>, {source.sample_size.toLocaleString()} synthetic respondents</>)}
    {step("Data", <>source hash <code>{short(source.source_data_hash, 12)}</code>, result hash <code>{short(source.research_result_hash, 12)}</code></>)}
    {step("Candidate", <>{c.source_metric}: {inr(c.price)} / {packLabel(c.pack)}{c.promotion_depth_pct ? `, ${c.promotion_depth_pct}% promotion` : ", no promotion"}</>)}
    {step("Scenario", <><code>{short(scenarioId ?? source.scenario_id, 12)}</code> on model <code>{source.model_version}</code></>)}
    {step("Modeled outcome", <>result hash <code>{short(resultHash ?? source.result_hash, 12)}</code> from the deterministic engine</>)}
    {step("Assumptions", <>{source.research_assumption_ids.join(", ")} (research) and {source.engine_assumption_ids.length} engine assumptions in the registry</>)}
  </ol>
}

export function CandidateTable({ rows, baseline, onAdd }: {
  rows: ResearchScenarioRow[]; baseline?: ApiScenarioResult; onAdd: (scenario: ApiScenario) => void
}) {
  const base = baseline ? totals(baseline) : undefined
  const deltas = rows.map((row) => {
    if (row.status === "REFUSED" || !base) return undefined
    const t = totals(row)
    return { volume: changePct(t.volume, base.volume), revenue: changePct(t.gsv, base.gsv), margin: changePct(t.gp, base.gp) }
  })
  const max = (pick: (d: NonNullable<(typeof deltas)[number]>) => number) =>
    Math.max(1, ...deltas.flatMap((d) => (d ? [Math.abs(pick(d))] : []))) * 1.1
  return <div className="space-y-3">
    {rows.map((row, i) => {
      const d = deltas[i], c = row.provenance.candidate
      const withSource = (scenario: ApiScenario, name?: string): ApiScenario => ({ ...scenario, name: name ?? scenario.name, source: row.provenance })
      return <article key={row.scenario_id + i} className={`rounded-lg border bg-card px-5 py-4 ${row.status === "REFUSED" ? "hatch border-dashed border-loss/40" : ""}`}>
        <div className="grid items-center gap-x-8 gap-y-3 md:grid-cols-[minmax(0,14rem)_repeat(3,minmax(0,1fr))]">
          <div>
            <p className="num text-2xl font-semibold">{inr(c.price)}</p>
            <p className="text-sm text-muted-foreground">{c.source_metric}</p>
            <p className="text-xs text-muted-foreground">{packLabel(c.pack)}{c.promotion_depth_pct ? `, ${c.promotion_depth_pct}% promotion` : ""}</p>
            {row.status === "REFUSED" && <span className="mt-2 inline-block rounded bg-loss px-1.5 py-0.5 text-xs font-medium text-white">REFUSED</span>}
            {row.status === "EDGE" && <span className="mt-2 inline-block rounded bg-edge/15 px-1.5 py-0.5 text-xs font-medium text-edge">Edge of data</span>}
          </div>
          {d ? <>
            <Metric label="Volume" value={d.volume} max={max((x) => x.volume)} />
            <Metric label="Revenue" value={d.revenue} max={max((x) => x.revenue)} />
            <Metric label="Margin" value={d.margin} max={max((x) => x.margin)} strong />
          </> : row.status === "REFUSED" ? <div className="text-sm md:col-span-3">
            {row.refusal_reasons.map((r) => <p key={r.message}>{r.message}</p>)}
            <p className="mt-1 text-xs text-muted-foreground">No modeled volume, revenue or margin exist for a refused candidate. The research price is shown as proposed, never clamped.</p>
          </div> : <p className="text-sm text-muted-foreground md:col-span-3">Waiting for the baseline.</p>}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {row.status !== "REFUSED" && <button type="button" onClick={() => onAdd(withSource(row.scenario))} className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white">Send to simulator</button>}
          {row.status === "REFUSED" && row.nearest_supported_scenario && <button type="button" onClick={() => onAdd(withSource(row.nearest_supported_scenario as ApiScenario, "Nearest supported to " + row.scenario.name))} className="rounded-md border border-primary/40 px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary hover:text-primary-foreground">Add nearest supported alternative</button>}
          <details className="text-sm"><summary className="cursor-pointer rounded px-2 py-1 text-muted-foreground hover:bg-secondary">Where this price came from</summary>
            <div className="mt-2"><ProvenanceChain source={row.provenance} scenarioId={row.scenario_id} resultHash={row.result_hash} /></div></details>
        </div>
      </article>
    })}
  </div>
}
