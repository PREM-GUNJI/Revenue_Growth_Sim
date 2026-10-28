import { Link } from "react-router-dom"
import { LabelTag } from "@/components/label-tag"
import { rupees, signed, signedRupees, tone } from "@/lib/catalog"
import type { ScenarioBridge, ScenarioResult } from "@/lib/types"
import { pickBest } from "@/workspace/helpers"

const BRIDGE_LABELS: Array<[keyof Omit<ScenarioBridge, "total">, string]> = [
  ["price", "price"],
  ["volume", "volume"],
  ["crossPack", "cross-pack mix"],
  ["promo", "promotion"],
  ["trade", "trade terms"],
  ["cogs", "unit costs"],
]

/** One plain sentence from the margin bridge — top drivers only, for a boardroom audience. */
export function whySentence(bridge: ScenarioBridge | undefined): string | undefined {
  if (!bridge) return undefined
  const drivers = BRIDGE_LABELS
    .map(([key, label]) => ({ key, label, value: bridge[key] }))
    .filter((d) => Math.abs(d.value) >= 0.5)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 2)
  if (!drivers.length) return undefined
  const parts = drivers.map((d) => `${d.label} (${signedRupees(d.value)})`)
  if (parts.length === 1) return `Profit moved mainly on ${parts[0]}.`
  return `Profit moved mainly on ${parts[0]} and ${parts[1]}.`
}

/** Up to three non-baseline supported options, ranked by gross-profit change (losers included). */
export function glanceOptions(results: ScenarioResult[], limit = 3): ScenarioResult[] {
  return results
    .filter((item) => item.status !== "REFUSED" && !item.isBaseline && item.delta && item.abs)
    .sort((a, b) => (b.delta?.marginPct ?? -Infinity) - (a.delta?.marginPct ?? -Infinity))
    .slice(0, limit)
}

export function ExecutiveDeck({
  caseName,
  question,
  results,
  guardrail,
  basePath,
  onExport,
  exportBusy,
  exportError,
}: {
  caseName: string
  question?: string
  results: ScenarioResult[]
  guardrail: number
  basePath: string
  onExport: () => void
  exportBusy: boolean
  exportError?: string
}) {
  const best = pickBest(results, guardrail)
  const winner = best && best.abs && best.abs.gpChange > 0 ? best : undefined
  const options = glanceOptions(results)
  const refused = results.filter((item) => item.status === "REFUSED")
  const why = whySentence(winner?.bridge)

  return (
    <article className="executive-deck mx-auto flex w-full max-w-5xl flex-col gap-10 px-5 py-10 md:px-10 md:py-14">
      <header className="space-y-3 print:space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">Decision brief · Aurora · weekly INR</p>
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink md:text-5xl">{caseName}</h1>
        <p className="max-w-2xl text-lg text-muted-foreground md:text-xl">
          {question?.trim() || "What price, pack or promotion move improves Aurora gross profit without breaking the volume guardrail?"}
        </p>
        <div className="flex flex-wrap items-center gap-2 print:hidden">
          <button type="button" onClick={() => window.print()} className="rounded-md border bg-card px-3 py-1.5 text-sm font-medium hover:bg-secondary">Print</button>
          <button type="button" onClick={onExport} disabled={exportBusy} className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">{exportBusy ? "Preparing…" : "Export deck"}</button>
          <Link to={basePath} className="rounded-md border bg-card px-3 py-1.5 text-sm font-medium hover:bg-secondary">Open workbench</Link>
          <Link to={`${basePath}/board`} className="text-sm text-muted-foreground underline-offset-4 hover:underline">Compare in detail</Link>
          {exportError && <span role="alert" className="text-xs text-loss">{exportError}</span>}
        </div>
      </header>

      <section aria-label="Recommendation" className="relative overflow-hidden rounded-2xl bg-ink px-7 py-8 text-white md:px-10 md:py-10">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(255,255,255,0.08),transparent_55%)]" aria-hidden="true" />
        <div className="relative space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-white/50">Recommendation</p>
            <LabelTag label={winner ? "Recommended" : "Modeled"} />
          </div>
          {winner?.abs && winner.delta ? <>
            <h2 className="font-display text-3xl font-semibold md:text-4xl">{winner.name}</h2>
            <p className={`num text-5xl font-bold leading-none tracking-tight md:text-6xl ${winner.abs.gpChange >= 0 ? "text-[#4ade80]" : "text-[#fca5a5]"}`}>
              {signedRupees(winner.abs.gpChange)}
            </p>
            <p className="text-lg text-white/75">gross profit a week · volume {signed(winner.delta.volumePct)} · margin {signed(winner.delta.marginPct)}</p>
            {why && <p className="max-w-2xl text-base text-white/80">{why}</p>}
            <p className="text-sm text-white/55">Volume loss kept within {guardrail}%. Aurora only. Modeled by the deterministic engine — not a forecast.</p>
          </> : <>
            <h2 className="font-display text-3xl font-semibold md:text-4xl">Hold the baseline</h2>
            <p className="max-w-2xl text-lg text-white/75">
              {results.filter((r) => !r.isBaseline).length === 0
                ? "Add options on the workbench, or ask the assistant to propose some, then return here."
                : `No supported option beats baseline on gross profit while keeping volume loss within ${guardrail}%.`}
            </p>
            <div className="flex flex-wrap gap-2 pt-1 print:hidden">
              <Link to={`${basePath}/simulator`} className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-ink">Build options</Link>
              <Link to={`${basePath}/assistant`} className="rounded-md border border-white/40 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/10">Open Recommend</Link>
            </div>
          </>}
        </div>
      </section>

      <section aria-label="Options at a glance" className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-display text-2xl font-semibold text-ink">Options at a glance</h2>
          <LabelTag label="Modeled" />
        </div>
        {options.length === 0 ? (
          <p className="text-muted-foreground">No supported options on the board yet.</p>
        ) : (
          <ul className="divide-y border-y">
            {options.map((item) => {
              const isWinner = winner?.scenarioId === item.scenarioId
              const loser = (item.delta?.marginPct ?? 0) < 0
              return (
                <li key={item.scenarioId} className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 py-4">
                  <div className="min-w-0 space-y-1">
                    <p className="font-medium text-ink">
                      {item.name}
                      {isWinner && <span className="ml-2 text-xs font-semibold uppercase tracking-wide text-gain">Chosen</span>}
                      {loser && !isWinner && <span className="ml-2 text-xs font-semibold uppercase tracking-wide text-loss">Worse than baseline</span>}
                    </p>
                    <p className="text-sm text-muted-foreground">Volume {signed(item.delta!.volumePct)}</p>
                  </div>
                  <div className="text-right">
                    <p className={`num text-2xl font-semibold ${tone(item.abs!.gpChange)}`}>{signedRupees(item.abs!.gpChange)}</p>
                    <p className="text-xs text-muted-foreground">a week · {signed(item.delta!.marginPct)} GP</p>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
        {refused.length > 0 && (
          <p className="text-sm text-loss">
            {refused.length} request{refused.length === 1 ? "" : "s"} refused as outside observed data
            ({refused.map((r) => r.name).join(", ")}). No figures shown for those.
          </p>
        )}
      </section>

      <footer className="space-y-2 border-t pt-6 text-sm text-muted-foreground">
        <p>Synthetic data. Modeled figures, not observed outcomes. Recommendation rests on engine results inside the support envelope.</p>
        <p className="text-xs">Baseline weekly gross profit context: options are measured against Aurora’s current position{results.find((r) => r.isBaseline)?.abs ? ` (${rupees(results.find((r) => r.isBaseline)!.abs!.gp)} a week)` : ""}).</p>
      </footer>
    </article>
  )
}
