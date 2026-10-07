import { ProvenanceChain } from "@/components/evidence-parts"
import { type AgentClaim, type ApiScenario, type Provenance, type ResearchScenarioRow } from "@/lib/api"
import { rupees } from "@/lib/catalog"
import { useWorkspace } from "@/workspace/workspace-context"

const RESEARCH_TOOLS = ["run_wtp", "run_gabor_granger", "run_van_westendorp", "run_conjoint_simulation"]
const chipClass = (claim: AgentClaim) => claim.research_id ? "border-edge/50 bg-edge/10" : claim.label === "Recommended" ? "border-primary/50 bg-primary/10" : "bg-card"

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
  const { agent, addExternal, workspace } = useWorkspace()
  const { goal, setGoal, run, error, loading, ask } = agent
  const evaluations = run?.tool_events.find((event) => event.name === "evaluate_scenarios")?.result
  const rows = Array.isArray(evaluations) ? evaluations : []
  const evidenceEvents = run?.tool_events.filter((event) => RESEARCH_TOOLS.includes(event.name)) ?? []
  const mapped = (run?.tool_events.find((event) => event.name === "research_to_scenarios")?.result ?? []) as ResearchScenarioRow[]
  const sourceFor = (scenario: ApiScenario): Provenance | undefined => mapped.find((row) => row.scenario?.name === scenario.name)?.provenance
  const options = suggestions(workspace?.description)

  return <section className="space-y-6">
    {!compact && <div><h2 className="font-display text-2xl font-semibold">Ask the AI decision assistant</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">The assistant reads where Aurora stands, chooses scenarios and, when useful, which synthetic consumer evidence to consult. The deterministic engine computes every number, and an auditor checks that each claim traces to a tool result.</p></div>}
    <div className="space-y-3 rounded-lg border bg-card p-5">
      <label className="block text-sm font-medium" htmlFor={compact ? "agent-goal-drawer" : "agent-goal"}>What should it work out?</label>
      <textarea id={compact ? "agent-goal-drawer" : "agent-goal"} rows={3} maxLength={4000} value={goal} onChange={(event) => setGoal(event.target.value)} className="w-full rounded-md border bg-background p-3 text-sm" />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" disabled={loading || !goal.trim()} onClick={() => void ask()} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{loading ? "Analyzing…" : "Run assistant"}</button>
        {options.map((text) => <button key={text} type="button" onClick={() => setGoal(text)} className="rounded-md border px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground">{text.length > 46 ? text.slice(0, 44) + "…" : text}</button>)}
      </div>
      {error && <p role="alert" className="text-sm text-loss">{error}</p>}
    </div>
    {run && <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className={`rounded px-2 py-1 text-xs font-medium ${run.audit.passed ? "bg-gain/15 text-gain" : "bg-loss/10 text-loss"}`}>{run.audit.passed ? "Auditor passed" : "Auditor rejected"}</span>
        <span className="rounded border px-2 py-1 text-xs">{run.model_id}</span>
        <span className="text-xs text-muted-foreground">Total {run.wall_time_ms.toFixed(0)} ms, model {run.model_time_ms.toFixed(0)} ms, tools {run.tool_time_ms.toFixed(0)} ms, trace {run.trace_id}</span>
      </div>
      {!run.audit.passed && <ul className="list-disc pl-5 text-sm text-loss">{run.audit.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>}
      <article className="space-y-3 rounded-lg border bg-card p-5">
        <h3 className="font-display text-lg font-semibold">Summary</h3>
        <p className="text-sm">{run.answer.summary}</p>
        {run.answer.recommendations.map((item) => <p key={item} className="text-sm font-medium">{item}</p>)}
        {run.answer.refusals.map((item) => <p key={item} className="hatch rounded border border-dashed border-loss/40 p-2 text-sm text-loss">{item}</p>)}
        {run.answer.caveats.map((item) => <p key={item} className="text-xs text-muted-foreground">{item}</p>)}
        <div className="flex flex-wrap gap-2">{run.answer.claims.map((claim) => <span key={claim.claim_id} className={`rounded-full border px-2.5 py-1 text-xs ${chipClass(claim)}`}><strong>{claim.research_id ? "Modeled (research-derived)" : claim.label}</strong>: {claim.text}</span>)}</div>
      </article>
      {evidenceEvents.length > 0 && <section className="space-y-3 rounded-lg border border-edge/40 bg-edge/5 p-5">
        <h3 className="font-display text-lg font-semibold text-edge">Synthetic consumer evidence used</h3>
        <p className="text-sm text-foreground/80">Research proposed the candidate prices below. Their commercial outcomes come from the engine, on the same board as every other scenario.</p>
        {evidenceEvents.map((event) => {
          const result = event.result as { research_id: string; methodology: string; sample_size: number; candidates: Array<{ price: number; source_metric: string }> }
          return <p key={event.call_id} className="text-sm"><code>{result.research_id}</code> {result.methodology}, {result.sample_size.toLocaleString()} synthetic respondents: {result.candidates.map((c) => `₹${c.price.toFixed(2)} (${c.source_metric})`).join(", ")}</p>
        })}
        {mapped.slice(0, 1).map((row) => <details key={row.scenario_id} className="text-sm"><summary className="cursor-pointer text-muted-foreground">Provenance of the first candidate</summary><div className="mt-2"><ProvenanceChain source={row.provenance} scenarioId={row.scenario_id} resultHash={row.result_hash} /></div></details>)}
      </section>}
      <section className="space-y-2">
        <h3 className="font-display text-lg font-semibold">Options the assistant compared</h3>
        {run.scenarios.map((scenario, index) => {
          const result = rows[index] as { status?: string; focal?: { gp?: { value: number } } } | undefined
          const source = sourceFor(scenario)
          return <div key={index} className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-card p-3 text-sm">
            <div><span className="font-medium">{scenario.name || "Scenario " + (index + 1)}</span>
              <span className={`ml-2 ${result?.status === "REFUSED" ? "font-medium text-loss" : "text-muted-foreground"}`}>{result?.status ?? "pending evaluation"}</span>
              {result?.status !== "REFUSED" && result?.focal?.gp && <span className="ml-2 num">Aurora gross profit {rupees(result.focal.gp.value)} a week</span>}
              {source && <span className="ml-2 rounded bg-edge/10 px-1.5 py-0.5 text-xs text-edge">research candidate</span>}</div>
            <button type="button" onClick={() => addExternal(source ? { ...scenario, source } : scenario)} className="rounded-md border px-2.5 py-1.5 text-xs font-medium hover:bg-secondary">Add to my options</button>
          </div>
        })}
      </section>
      <details className="rounded-md border bg-card p-3">
        <summary className="cursor-pointer text-sm font-medium">Replay trace events</summary>
        <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(run.tool_events, null, 2)}</pre>
      </details>
    </div>}
  </section>
}
