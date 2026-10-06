import { useNavigate } from "react-router-dom"
import { signed } from "@/lib/catalog"
import { useWorkspace } from "@/workspace/workspace-context"

export function OverviewPage() {
  const { best, loading, scenarios, supportedCount, refusedCount, workspaceId } = useWorkspace()
  const navigate = useNavigate()
  const base = `/w/${workspaceId}/`
  return (
    <>
            <section aria-label="Headline" className="grid gap-6 rounded-xl bg-ink p-6 text-white md:grid-cols-[1fr_auto] md:p-8">
              <div>
                <p className="text-sm text-white/60">{best ? "Best margin move within the volume guardrail" : "Waiting for results"}</p>
                <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <span className="num text-6xl font-bold leading-none md:text-7xl" style={{ color: best && (best.delta?.marginPct ?? 0) < 0 ? "#fb7185" : "#4ade80" }}>{best?.delta ? signed(best.delta.marginPct) : "—"}</span>
                  <span className="font-display text-xl">{best ? "gross profit, " + best.name : loading ? "Evaluating…" : "No scenario fits the guardrail."}</span>
                </div>
                {best?.delta && <p className="mt-3 max-w-xl text-sm text-white/70">Volume {signed(best.delta.volumePct)}, revenue {signed(best.delta.revenuePct)} against the baseline. The engine is deterministic: the same levers always give the same numbers.</p>}
              </div>
              <dl className="grid grid-cols-3 gap-x-8 self-end text-sm md:grid-cols-1 md:gap-y-3 md:text-right">
                <div><dt className="text-white/50">Compared</dt><dd className="num text-2xl font-semibold">{scenarios.length}</dd></div>
                <div><dt className="text-white/50">Supported</dt><dd className="num text-2xl font-semibold">{supportedCount}</dd></div>
                <div><dt className="text-white/50">Refused</dt><dd className="num text-2xl font-semibold">{refusedCount}</dd></div>
              </dl>
            </section>
            <section aria-label="How a decision is made">
              <h2 className="font-display text-xl font-semibold">How a decision is made</h2>
              <ol className="mt-4 grid gap-3 md:grid-cols-5">
                {([["Price, pack and promotion", "Set the three levers together for each scenario.", "simulator", "Open the simulator"],
                  ["Deterministic engine", "A documented elasticity model. Out-of-range requests are refused, never extrapolated.", undefined, ""],
                  ["Volume, revenue and margin", "Every number, with its sensitivity band, comes from the engine.", undefined, ""],
                  ["Comparison", "Baseline, winners, losers and refusals side by side.", "board", "Open the board"],
                  ["Decision", "The assistant recommends from engine results; an auditor checks every number.", "assistant", "Ask the assistant"]] as const)
                  .map(([title, body, target, cta], i) => <li key={title} className="flex flex-col rounded-lg border bg-card p-4">
                    <span className="num text-sm text-muted-foreground">{i + 1}</span><h3 className="mt-1 font-display text-base font-semibold">{title}</h3>
                    <p className="mt-1 flex-1 text-sm text-muted-foreground">{body}</p>
                    {target && <button type="button" onClick={() => navigate(base + target)} className="mt-3 self-start rounded text-sm font-medium text-primary underline-offset-4 hover:underline">{cta}</button>}</li>)}
              </ol>
            </section>
            <section className="grid gap-4 rounded-lg border border-edge/40 bg-edge/5 p-5 md:grid-cols-[1fr_auto]" aria-label="Supporting evidence">
              <div><h2 className="font-display text-lg font-semibold">Supporting synthetic consumer evidence</h2>
                <p className="mt-1 max-w-2xl text-sm text-foreground/80">Synthetic willingness to pay, Gabor-Granger, Van Westendorp and a conjoint simulation suggest candidate prices. The candidates enter the same simulator and are judged by the same engine. Nothing here is real consumer research.</p></div>
              <div className="flex flex-wrap items-center gap-2"><button type="button" onClick={() => navigate(base + "evidence")} className="rounded-md border bg-card px-3 py-2 text-sm font-medium hover:bg-secondary">Pricing evidence</button>
                <button type="button" onClick={() => navigate(base + "conjoint")} className="rounded-md border bg-card px-3 py-2 text-sm font-medium hover:bg-secondary">Conjoint simulation</button></div>
            </section>
    </>
  )
}
