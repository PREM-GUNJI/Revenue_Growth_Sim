import { AgentPanel } from "@/components/agent-panel"
import { Why } from "@/components/comparison-board"
import { LabelTag } from "@/components/label-tag"
import { rupees, signed, signedRupees, units } from "@/lib/catalog"
import { useWorkspace } from "@/workspace/workspace-context"

/** Step 4: the best option on the table, why it wins, and the assistant for a recommendation with audited claims. */
export function AssistantPage() {
  const { best, guardrail, results, openAssumptions, workspace } = useWorkspace()
  const winner = best && best.abs && best.abs.gpChange > 0 ? best : undefined
  return <>
    <header className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Step 4 of 4 · Recommend</p>
      <h1 className="font-display text-3xl font-semibold">{workspace?.name}</h1>
    </header>

    <section aria-label="Best option" className="space-y-3 rounded-xl bg-ink p-6 text-white">
      {winner?.abs && winner.delta ? <>
        <p className="text-sm text-white/60">Best option on the table, keeping volume loss within {guardrail}%</p>
        <p className="font-display text-xl">{winner.name}</p>
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="num text-5xl font-bold leading-none text-[#4ade80]">{signedRupees(winner.abs.gpChange)}</span>
          <span className="text-lg">gross profit a week ({signed(winner.delta.marginPct)}), range {signedRupees(winner.abs.gpChangeRange[0])} to {signedRupees(winner.abs.gpChangeRange[1])}</span>
        </div>
        <p className="text-sm text-white/70">Volume {signed(winner.delta.volumePct)} ({units(winner.abs.units)} units a week) · revenue {rupees(winner.abs.revenue)} · margin {winner.abs.marginPct.toFixed(1)}% · all modeled by the deterministic engine, Aurora only.</p>
        {winner.bridge && <div className="rounded-lg bg-white p-3 text-foreground"><Why bridge={winner.bridge} /></div>}
        {winner.assumptionIds && <button type="button" onClick={() => openAssumptions(winner.assumptionIds)} className="rounded text-sm font-medium text-white underline underline-offset-4">See the {winner.assumptionIds.length} assumptions this rests on</button>}
      </> : <>
        <p className="text-sm text-white/60">Best option on the table</p>
        <p className="font-display text-xl">{results.length > 1 ? "No option beats the baseline within the volume guardrail yet." : "Add options to compare them with the baseline."}</p>
        <p className="text-sm text-white/70">Try the opportunities on the Situation step, build your own on Options, or ask the assistant below to propose some.</p>
      </>}
      <div className="pt-1"><LabelTag label="Modeled" /></div>
    </section>

    <AgentPanel />
  </>
}
