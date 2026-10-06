import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { runAgent, type AgentApiRun } from "@/lib/api"
import type { ApiScenario } from "@/lib/api"

interface AgentPanelProps {
  onAcceptScenario: (scenario: ApiScenario) => void
}

export function AgentPanel({ onAcceptScenario }: AgentPanelProps) {
  const [goal, setGoal] = useState("Find a margin growth opportunity while retaining a baseline, a plausible alternative, and a likely loser.")
  const [run, setRun] = useState<AgentApiRun>()
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(false)

  async function submit() {
    setLoading(true)
    setError(undefined)
    try {
      setRun(await runAgent(goal))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Agent request failed")
    } finally {
      setLoading(false)
    }
  }

  const evaluations = run?.tool_events.find((event) => event.name === "evaluate_scenarios")?.result
  const rows = Array.isArray(evaluations) ? evaluations : []

  return <section className="space-y-4">
    <div className="space-y-2 rounded-lg border p-4">
      <h2 className="font-semibold">Revenue growth agent</h2>
      <p className="text-sm text-muted-foreground">OpenAI proposes scenarios; the deterministic engine evaluates them, and the Auditor checks claims before they are shown.</p>
      <label className="block text-sm font-medium" htmlFor="agent-goal">Goal</label>
      <textarea id="agent-goal" rows={3} maxLength={4000} value={goal} onChange={(event) => setGoal(event.target.value)} className="w-full rounded border bg-background p-2 text-sm" />
      <button type="button" disabled={loading || !goal.trim()} onClick={() => void submit()} className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50">{loading ? "Analyzing…" : "Run agent"}</button>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </div>
    {run && <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={run.audit.passed ? "default" : "destructive"}>{run.audit.passed ? "Auditor passed" : "Auditor rejected"}</Badge>
        <Badge variant="outline">{run.model_id}</Badge>
        <span className="text-xs text-muted-foreground">Total {run.wall_time_ms.toFixed(0)} ms · model {run.model_time_ms.toFixed(0)} ms · tools {run.tool_time_ms.toFixed(0)} ms · trace {run.trace_id}</span>
      </div>
      {!run.audit.passed && <ul className="list-disc pl-5 text-sm text-destructive">{run.audit.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>}
      <article className="space-y-2 rounded-lg border p-4">
        <h3 className="font-semibold">Summary</h3>
        <p className="text-sm">{run.answer.summary}</p>
        {run.answer.recommendations.map((item) => <p key={item} className="text-sm">{item}</p>)}
        {run.answer.refusals.map((item) => <p key={item} className="rounded bg-destructive/5 p-2 text-sm text-destructive">{item}</p>)}
        {run.answer.caveats.map((item) => <p key={item} className="text-xs text-muted-foreground">{item}</p>)}
        <div className="flex flex-wrap gap-2">{run.answer.claims.map((claim) => <span key={claim.claim_id} className="rounded-full border px-2 py-1 text-xs"><strong>{claim.label}</strong>: {claim.text}</span>)}</div>
      </article>
      <section className="space-y-2">
        <h3 className="font-semibold">Proposed comparison board</h3>
        {run.scenarios.map((scenario, index) => {
          const result = rows[index] as { status?: string; portfolio_gp?: { value: number } | null } | undefined
          return <div key={index} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
            <div><span className="font-medium">{scenario.name || "Scenario " + (index + 1)}</span><span className="ml-2 text-muted-foreground">{result?.status ?? "pending evaluation"}</span>{result?.status !== "REFUSED" && result?.portfolio_gp && <span className="ml-2">GP {result.portfolio_gp.value.toLocaleString()}</span>}</div>
            <button type="button" onClick={() => onAcceptScenario(scenario)} className="rounded border px-2 py-1 text-xs">Add to tray</button>
          </div>
        })}
      </section>
      <details className="rounded-md border p-3">
        <summary className="cursor-pointer text-sm font-medium">Replay trace events</summary>
        <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(run.tool_events, null, 2)}</pre>
      </details>
    </div>}
  </section>
}
