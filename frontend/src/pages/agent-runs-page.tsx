import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { formatTokens, formatUsd, formatWhen } from "@/lib/format"
import { getAgentRun, getAgentRuns } from "@/lib/governance"
import type { AgentRunDetail, AgentRunRow } from "@/lib/governance"

const LABEL_STYLE: Record<string, string> = {
  Observed: "bg-muted text-foreground", Modeled: "bg-primary/10 text-primary", Assumed: "bg-edge/15 text-edge", Recommended: "bg-gain/10 text-gain",
}

export function AgentRunsPage() {
  const [runs, setRuns] = useState<AgentRunRow[]>()
  const [error, setError] = useState<string>()
  useEffect(() => { getAgentRuns().then(setRuns).catch((c: unknown) => setError(c instanceof Error ? c.message : "Could not load agent runs")) }, [])
  return (
    <main className="mx-auto w-full max-w-[1200px] flex-1 space-y-6 px-5 py-8 md:px-8">
      <div>
        <h1 className="font-display text-3xl font-semibold">Agent runs</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">Every question put to the AI decision assistant, with who asked, where, and what it cost. Open one to see the labelled claims and the auditor's verdict.</p>
      </div>
      {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
      {!runs && !error && <p className="text-sm text-muted-foreground" role="status">Loading…</p>}
      {runs && runs.length === 0 && <p className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">No agent runs yet. Ask the AI decision assistant inside a workspace and the run will appear here.</p>}
      {runs && runs.length > 0 && <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="px-4 py-3">When</th><th className="px-4 py-3">Goal</th><th className="px-4 py-3">Workspace</th><th className="px-4 py-3">By</th><th className="px-4 py-3 text-right">Tokens in / out</th><th className="px-4 py-3 text-right">Cost</th></tr></thead>
          <tbody>{runs.map((run) => <tr key={run.trace_id} className="border-b last:border-0 hover:bg-secondary/40">
            <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{formatWhen(run.at)}</td>
            <td className="max-w-md px-4 py-3"><Link to={`/agent-runs/${run.trace_id}`} className="font-medium text-primary underline-offset-4 hover:underline">{run.goal || "(no goal recorded)"}</Link></td>
            <td className="px-4 py-3">{run.workspace_name ?? "None"}</td>
            <td className="px-4 py-3">{run.user_email}</td>
            <td className="num whitespace-nowrap px-4 py-3 text-right">{run.input_tokens === null ? "n/a" : formatTokens(run.input_tokens) + " / " + formatTokens(run.output_tokens ?? 0)}</td>
            <td className="num whitespace-nowrap px-4 py-3 text-right">{formatUsd(run.cost_usd)}</td></tr>)}</tbody>
        </table></div>}
    </main>
  )
}

export function AgentRunDetailPage() {
  const { traceId = "" } = useParams()
  const [state, setState] = useState<{ id: string; run?: AgentRunDetail; error?: string }>()
  useEffect(() => {
    let active = true
    getAgentRun(traceId).then((run) => { if (active) setState({ id: traceId, run }) })
      .catch((c: unknown) => { if (active) setState({ id: traceId, error: c instanceof Error && c.message.includes("404") ? "That run's trace file isn't available." : "Could not load this run" }) })
    return () => { active = false }
  }, [traceId])
  const current = state?.id === traceId ? state : undefined
  const run = current?.run
  return (
    <main className="mx-auto w-full max-w-[1000px] flex-1 space-y-6 px-5 py-8 md:px-8">
      <Link to="/agent-runs" className="text-sm font-medium text-primary underline-offset-4 hover:underline">All agent runs</Link>
      {current?.error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{current.error}</div>}
      {!current && <p className="text-sm text-muted-foreground" role="status">Loading…</p>}
      {run && <>
        <div>
          <h1 className="font-display text-2xl font-semibold">Agent run</h1>
          <p className="mt-1 text-sm text-muted-foreground">Model {run.model_id ?? "unknown"} · prompt {run.prompt_version_hash?.slice(0, 10) ?? "n/a"} · {run.tool_calls.length} tool calls</p>
        </div>
        {run.audit && <section className={`rounded-xl border p-4 ${run.audit.passed ? "border-gain/40 bg-gain/5" : "border-loss/40 bg-loss/5"}`} aria-label="Auditor verdict">
          <p className="font-medium">{run.audit.passed ? "Auditor passed" : "Auditor flagged issues"} <span className="font-normal text-muted-foreground">({run.audit.numbers_checked} numbers checked)</span></p>
          {run.audit.issues.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{run.audit.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>}
        </section>}
        {run.answer && <section className="space-y-4" aria-label="Answer">
          <p className="leading-7">{run.answer.summary}</p>
          {run.answer.refusals.length > 0 && <div><h2 className="font-display text-lg font-semibold">Refusals</h2><ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{run.answer.refusals.map((r) => <li key={r}>{r}</li>)}</ul></div>}
          {run.answer.recommendations.length > 0 && <div><h2 className="font-display text-lg font-semibold">Recommendations</h2><ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{run.answer.recommendations.map((r) => <li key={r}>{r}</li>)}</ul></div>}
          {run.answer.caveats.length > 0 && <div><h2 className="font-display text-lg font-semibold">Caveats</h2><ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">{run.answer.caveats.map((r) => <li key={r}>{r}</li>)}</ul></div>}
          <div><h2 className="font-display text-lg font-semibold">Claims</h2>
            <ul className="mt-2 space-y-2">{run.answer.claims.map((claim) => <li key={claim.claim_id} className="rounded-lg border bg-card p-3 text-sm">
              <span className={`mr-2 rounded px-1.5 py-0.5 text-xs font-medium ${LABEL_STYLE[claim.label] ?? "bg-muted"}`}>{claim.label}</span>{claim.text}
              <p className="mt-1 text-xs text-muted-foreground">{claim.tool_call_id ? `from ${claim.tool_call_id}${claim.field_path ? " at " + claim.field_path : ""}` : "no tool result cited"}{claim.references.length > 0 ? ` · supports ${claim.references.join(", ")}` : ""}</p></li>)}</ul></div>
        </section>}
        <section aria-label="Tool calls"><h2 className="font-display text-lg font-semibold">Tool calls</h2>
          <ol className="mt-2 divide-y rounded-xl border bg-card text-sm">{run.tool_calls.map((call) => <li key={call.call_id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2">
            <span><span className="num text-muted-foreground">{call.call_id}</span> <span className="font-medium">{call.name}</span></span>
            <span className="num text-xs text-muted-foreground" title={call.result_hash}>{call.result_hash.slice(0, 16)}…</span></li>)}</ol></section>
      </>}
    </main>
  )
}
