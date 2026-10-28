import { ProvenanceChain } from "@/components/evidence-parts"
import { MEANING, type ClaimLabel } from "@/lib/claim-labels"
import { useDetailMode } from "@/lib/preferences"
import { RefusalDetail } from "@/components/refusal-detail"
import { SensitivityTable } from "@/components/sensitivity-panel"
import { type AgentClaim, type ApiScenario, type ApiScenarioResult, type Provenance, type ResearchScenarioRow, type SensitivityResult } from "@/lib/api"
import { rupees } from "@/lib/catalog"
import { money as moneyPrice } from "@/lib/currency"
import { useWorkspace } from "@/workspace/workspace-context"

const RESEARCH_TOOLS = ["run_wtp", "run_gabor_granger", "run_van_westendorp", "run_conjoint_simulation"]
const chipClass = (claim: AgentClaim) => claim.research_id ? "border-edge/50 bg-edge/10" : claim.label === "Recommended" ? "border-primary/50 bg-primary/10" : "bg-card"

/** First sentence of older answers that only filled `summary`. */
function decisionText(answer: { decision?: string; summary: string }): string {
  const trimmed = (answer.decision ?? "").trim()
  if (trimmed) return trimmed
  const summary = answer.summary.trim()
  const cut = summary.search(/[.!?]\s/)
  return cut === -1 ? summary : summary.slice(0, cut + 1)
}

/** Suggestions that start from the user's own case rather than a generic prompt. */
function suggestions(question: string | undefined): string[] {
  return [
    ...(question ? [question] : []),
    "Which pack should we take price on, and which should we promote?",
    "Input costs rise 8%. Find moves that protect gross profit without losing more than 5% volume.",
    "What price would consumers accept for the 500ml pack? Use willingness to pay evidence.",
  ]
}

/** The AI decision assistant. State lives in the case, so this shows the same run on the Recommend step and in the side drawer. */
export function AgentPanel({ compact = false }: { compact?: boolean }) {
  const { agent, addExternal, workspace, currency } = useWorkspace()
  const { goal, setGoal, run, error, loading, ask } = agent
  const [detail] = useDetailMode()
  const evaluations = run?.tool_events.find((event) => event.name === "evaluate_scenarios")?.result
  const rows = Array.isArray(evaluations) ? evaluations : []
  const sensitivity = run?.tool_events.find((event) => event.name === "sensitivity")?.result as SensitivityResult | undefined
  const baseIndex = (run?.scenarios ?? []).findIndex((item) => !Object.keys(item.levers).length && !Object.values(item.cost_shock).some(Boolean))
  const baseRow = (rows[baseIndex] ?? undefined) as ApiScenarioResult | undefined
  const baseGp = baseRow?.focal?.gp?.value, baseUnits = baseRow?.focal?.volume?.value
  const rank = new Map<number, number>((rows as ApiScenarioResult[]).map((item, index) => [index, item] as const).filter(([, item]) => item.status !== "REFUSED" && item.focal?.gp)
    .sort((a, b) => b[1].focal.gp.value - a[1].focal.gp.value).map(([index], position) => [index, position + 1]))
  const evidenceEvents = run?.tool_events.filter((event) => RESEARCH_TOOLS.includes(event.name)) ?? []
  const mapped = (run?.tool_events.find((event) => event.name === "research_to_scenarios")?.result ?? []) as ResearchScenarioRow[]
  const sourceFor = (scenario: ApiScenario): Provenance | undefined => mapped.find((row) => row.scenario?.name === scenario.name)?.provenance
  const options = suggestions(workspace?.description)
  const why = (run?.answer.why ?? []).filter(Boolean).slice(0, 2)
  const recommendations = (run?.answer.recommendations ?? []).slice(0, 2)

  return <section className="space-y-6">
    {!compact && <div><h2 className="font-display text-2xl font-semibold">Ask the AI decision assistant</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">You get a short decision first. The engine still computes every number; open Why / Evidence for the full comparison and audit trail.</p></div>}
    <div className="space-y-3 rounded-lg border bg-card p-5">
      <label className="block text-sm font-medium" htmlFor={compact ? "agent-goal-drawer" : "agent-goal"}>What should it work out?</label>
      <textarea id={compact ? "agent-goal-drawer" : "agent-goal"} rows={3} maxLength={4000} value={goal} onChange={(event) => setGoal(event.target.value)} className="w-full rounded-md border bg-background p-3 text-sm" />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" disabled={loading || !goal.trim()} onClick={() => void ask()} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{loading ? "Analyzing…" : "Run assistant"}</button>
        {options.map((text) => <button key={text} type="button" onClick={() => setGoal(text)} className="rounded-md border px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground">{text.length > 46 ? text.slice(0, 44) + "…" : text}</button>)}
      </div>
      {error && <p role="alert" className="text-sm text-loss">{error}</p>}
    </div>
    {run && <div className="space-y-4">
      <article className="space-y-4 rounded-2xl border bg-card p-5 shadow-sm" aria-label="Decision">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-lg font-semibold">Decision</h3>
          <span title="An independent auditor checked that every number in this answer comes from an engine result." className={`rounded px-2 py-1 text-xs font-medium ${run.audit.passed ? "bg-gain/15 text-gain" : "bg-loss/10 text-loss"}`}>{run.audit.passed ? "Verified against the engine" : "Not verified: the auditor found problems"}</span>
        </div>
        {!run.audit.passed && <ul className="list-disc pl-5 text-sm text-loss">{run.audit.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>}
        <p className="font-display text-xl font-semibold leading-snug tracking-tight md:text-2xl">{decisionText(run.answer)}</p>
        {why.length > 0 && <ul className="space-y-1.5 text-sm text-muted-foreground">{why.map((item) => <li key={item} className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden /><span>{item}</span></li>)}</ul>}
        {recommendations.length > 0 && <div className="space-y-2 border-t pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Do this</p>
          {recommendations.map((item) => <p key={item} className="text-sm font-medium leading-relaxed">{item}</p>)}
        </div>}
        {run.answer.refusals.map((item) => <p key={item} className="hatch rounded border border-dashed border-loss/40 p-2 text-sm text-loss">{item}</p>)}
      </article>

      <details className="rounded-lg border bg-card">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium">Why this · labelled claims</summary>
        <div className="space-y-3 border-t px-4 pb-4 pt-3">
          {run.answer.caveats.map((item) => <p key={item} className="text-xs text-muted-foreground">{item}</p>)}
          <div className="flex flex-wrap gap-2">{run.answer.claims.map((claim) => <span key={claim.claim_id} title={claim.research_id ? "Calculated by the engine from a price that synthetic research proposed." : MEANING[claim.label as ClaimLabel]} className={`cursor-help rounded-full border px-2.5 py-1 text-xs ${chipClass(claim)}`}><strong>{claim.research_id ? "Modeled (research-derived)" : claim.label}</strong>: {claim.text}</span>)}</div>
        </div>
      </details>

      <details className="rounded-lg border bg-card">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium">Compared options ({run.scenarios.length})</summary>
        <div className="space-y-3 border-t px-4 pb-4 pt-3">
          <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-secondary text-xs text-muted-foreground"><tr><th className="p-2">Rank</th><th className="p-2">Option</th><th className="p-2 text-right">Aurora gross profit</th><th className="p-2 text-right">vs baseline</th><th className="p-2 text-right">Units</th><th className="p-2">Why</th><th className="p-2" /></tr></thead>
            <tbody>{run.scenarios.map((scenario, index) => {
              const result = rows[index] as ApiScenarioResult | undefined
              const refused = result?.status === "REFUSED"
              const gp = refused ? undefined : result?.focal?.gp?.value, units = refused ? undefined : result?.focal?.volume?.value
              const gpDelta = gp !== undefined && baseGp !== undefined ? gp - baseGp : undefined
              const unitDelta = units !== undefined && baseUnits ? (units / baseUnits - 1) * 100 : undefined
              const source = sourceFor(scenario), position = rank.get(index)
              const reason = refused ? "Refused: outside supported data, no numbers produced" : index === baseIndex ? "Baseline"
                : gpDelta !== undefined && gpDelta < 0 ? "Loses: gross profit below baseline"
                : unitDelta !== undefined && unitDelta < -5 ? "Gains profit but loses over 5% of units" : "Beats baseline"
              return <tr key={index} className={`border-t align-top ${refused ? "hatch" : ""}`}>
                <td className="num p-2">{position ?? "–"}</td>
                <td className="p-2"><span className="font-medium">{scenario.name || "Scenario " + (index + 1)}</span>{source && <span className="ml-2 rounded bg-edge/10 px-1.5 py-0.5 text-xs text-edge">research candidate</span>}
                  {refused && result && <RefusalDetail reasons={result.refusal_reasons.map((r) => ({ skuId: r.sku_id, lever: r.lever, requested: r.requested, range: r.supported_range, message: r.message }))} />}</td>
                <td className="num p-2 text-right">{gp !== undefined ? rupees(gp, currency) : "–"}</td>
                <td className={`num p-2 text-right ${gpDelta !== undefined && gpDelta < 0 ? "text-loss" : gpDelta ? "text-gain" : ""}`}>{gpDelta !== undefined && index !== baseIndex ? (gpDelta >= 0 ? "+" : "") + rupees(gpDelta, currency) : "–"}</td>
                <td className="num p-2 text-right">{unitDelta !== undefined && index !== baseIndex ? (unitDelta >= 0 ? "+" : "") + unitDelta.toFixed(1) + "%" : "–"}</td>
                <td className={`p-2 text-xs ${refused || (gpDelta !== undefined && gpDelta < 0) ? "text-loss" : "text-muted-foreground"}`}>{reason}</td>
                <td className="p-2">{!refused && <button type="button" onClick={() => addExternal(source ? { ...scenario, source } : scenario)} className="rounded-md border px-2.5 py-1.5 text-xs font-medium hover:bg-secondary">Add to my options</button>}</td>
              </tr>
            })}</tbody>
          </table></div>
          {run.alternatives?.map((alt) => {
            const nearest = run.tool_events.find((event) => event.call_id === alt.tool_call_id)
            const scenario = (nearest?.arguments.scenarios as ApiScenario[] | undefined)?.[alt.result_index]
            const gp = alt.result.focal?.gp?.value
            const name = run.scenarios[alt.refused_index]?.name || "refused option"
            return <div key={alt.refused_index} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-primary/40 bg-primary/5 p-3 text-sm">
              <div><strong>Nearest supported alternative to “{name}”</strong>
                <span className="ml-2 text-muted-foreground">re-run through the engine{gp !== undefined ? ": Aurora gross profit " + rupees(gp, currency) + " a week" : ""}{gp !== undefined && baseGp !== undefined ? " (" + (gp - baseGp >= 0 ? "+" : "") + rupees(gp - baseGp, currency) + " vs baseline)" : ""}</span></div>
              {scenario && <button type="button" onClick={() => addExternal({ ...scenario, name: "Nearest supported: " + name })} className="rounded-md border border-primary/40 px-2.5 py-1.5 text-xs font-medium text-primary hover:bg-primary hover:text-primary-foreground">Add to my options</button>}
            </div>
          })}
        </div>
      </details>

      {evidenceEvents.length > 0 && <details className="rounded-lg border border-edge/40 bg-edge/5">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-edge">Synthetic consumer evidence</summary>
        <div className="space-y-3 border-t border-edge/30 px-4 pb-4 pt-3">
          <p className="text-sm text-foreground/80">Research proposed candidate prices. Commercial outcomes still come from the engine.</p>
          {evidenceEvents.map((event) => {
            const result = event.result as { research_id: string; methodology: string; sample_size: number; candidates: Array<{ price: number; source_metric: string }> }
            return <p key={event.call_id} className="text-sm">{detail && <><code>{result.research_id}</code> </>}{result.methodology}, {result.sample_size.toLocaleString()} synthetic respondents: {result.candidates.map((c) => `${moneyPrice(c.price, currency)} (${c.source_metric})`).join(", ")}</p>
          })}
          {mapped.slice(0, 1).map((row) => <div key={row.scenario_id} className="text-sm"><p className="mb-2 text-muted-foreground">Provenance of the first candidate</p><ProvenanceChain source={row.provenance} scenarioId={row.scenario_id} resultHash={row.result_hash} /></div>)}
        </div>
      </details>}

      {sensitivity && <details className="rounded-lg border bg-card">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium">What would change this answer?</summary>
        <div className="border-t px-4 pb-4 pt-3"><SensitivityTable data={sensitivity} names={run.scenarios.map((item) => item.name)} /></div>
      </details>}

      <details className="rounded-md border bg-card">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium">Audit details</summary>
        <dl className="mt-0 grid gap-x-4 gap-y-1 border-t px-4 pb-4 pt-3 text-xs sm:grid-cols-[auto_1fr]">
          <dt className="text-muted-foreground">Auditor</dt><dd>{run.audit.passed ? "Passed: every number traces to a tool result" : "Rejected"}</dd>
          <dt className="text-muted-foreground">Model</dt><dd>{run.model_id}</dd>
          <dt className="text-muted-foreground">Time</dt><dd className="num">total {run.wall_time_ms.toFixed(0)} ms, model {run.model_time_ms.toFixed(0)} ms, tools {run.tool_time_ms.toFixed(0)} ms</dd>
          <dt className="text-muted-foreground">Trace</dt><dd className="font-mono">{run.trace_id}</dd>
        </dl>
        {detail && <pre className="mx-4 mb-4 max-h-96 overflow-auto whitespace-pre-wrap text-xs" aria-label="Replay trace events">{JSON.stringify(run.tool_events, null, 2)}</pre>}
      </details>
    </div>}
  </section>
}
