import { Link } from "react-router-dom"
import { AgentPanel } from "@/components/agent-panel"
import { Why } from "@/components/comparison-board"
import { LabelTag } from "@/components/label-tag"
import { rupees, signed, signedRupees, units } from "@/lib/catalog"
import { useWorkspace } from "@/workspace/workspace-context"

/** Step 4: the best option on the table, why it wins, and the assistant for a recommendation with audited claims. */
export function AssistantPage() {
  const { best, guardrail, results, openAssumptions, workspace, workspaceId, currency } = useWorkspace()
  const winner = best && best.abs && best.abs.gpChange > 0 ? best : undefined
  return <>
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Step 4 of 4 · Recommend</p>
          <span className="rounded-md border bg-secondary/80 px-2 py-0.5 text-[11px] font-semibold tracking-wide">{currency.code}</span>
        </div>
        <h1 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">{workspace?.name}</h1>
      </div>
      <Link to={`/w/${workspaceId}/executive`} className="rounded-md border bg-card px-3 py-1.5 text-sm font-medium hover:bg-secondary">View executive brief</Link>
    </header>

    <section aria-label="Best option" className="space-y-4 overflow-hidden rounded-2xl bg-ink p-6 text-white shadow-md md:p-8">
      {winner?.abs && winner.delta ? <>
        <p className="text-sm text-white/55">Best option on the table, keeping volume loss within {guardrail}%</p>
        <p className="font-display text-2xl font-semibold tracking-tight">{winner.name}</p>
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="num text-5xl font-bold leading-none tracking-tight text-[#4ade80] md:text-6xl">{signedRupees(winner.abs.gpChange, currency)}</span>
          <span className="max-w-xl text-base text-white/85 md:text-lg">gross profit a week ({signed(winner.delta.marginPct)}), range {signedRupees(winner.abs.gpChangeRange[0], currency)} to {signedRupees(winner.abs.gpChangeRange[1], currency)}</span>
        </div>
        <p className="text-sm text-white/65">Volume {signed(winner.delta.volumePct)} ({units(winner.abs.units)} units a week) · revenue {rupees(winner.abs.revenue, currency)} · margin {winner.abs.marginPct.toFixed(1)}% · modeled by the deterministic engine, Aurora only.</p>
        {winner.bridge && <div className="rounded-xl bg-white p-3.5 text-foreground shadow-sm"><Why bridge={winner.bridge} /></div>}
        {winner.assumptionIds && <button type="button" onClick={() => openAssumptions(winner.assumptionIds)} className="rounded text-sm font-medium text-white underline underline-offset-4">See the {winner.assumptionIds.length} assumptions this rests on</button>}
      </> : <>
        <p className="text-sm text-white/55">Best option on the table</p>
        <p className="font-display text-2xl font-semibold tracking-tight">{results.length > 1 ? "No option beats the baseline within the volume guardrail yet." : "Add options to compare them with the baseline."}</p>
        <p className="text-sm text-white/65">Try the opportunities on the Situation step, build your own on Options, or ask the assistant below to propose some.</p>
      </>}
      <div className="pt-1"><LabelTag label="Modeled" /></div>
    </section>

    <AgentPanel />
  </>
}
