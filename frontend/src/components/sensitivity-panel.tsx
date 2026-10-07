import { useState } from "react"
import { getSensitivity, type ApiScenario, type SensitivityResult } from "@/lib/api"

/** Which documented assumptions the answer depends on, and whether the leader changes at the ends of their ranges. */
export function SensitivityTable({ data, names }: { data: SensitivityResult; names: string[] }) {
  const name = (i: number | null) => i === null ? "none" : names[i] || `Scenario ${i + 1}`
  const rows = data.assumptions.filter((r) => (r.swing ?? 0) > 0).slice(0, 6)
  const flips = rows.filter((r) => r.flips_winner)
  return <div className="space-y-2">
    <p className="text-sm">Leader on the central assumptions: <strong>{name(data.base_winner)}</strong>. {flips.length ? `${flips.length} assumption${flips.length > 1 ? "s" : ""} can change the leader within their documented ranges.` : "No single assumption changes the leader within its documented range."}</p>
    <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead className="text-xs text-muted-foreground"><tr><th className="py-1 pr-3">Assumption</th><th className="pr-3">Low → leader</th><th className="pr-3">High → leader</th><th className="text-right">Swing in leader GP</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r.assumption_id} className="border-t">
        <td className="py-1.5 pr-3"><code className="text-xs">{r.assumption_id}</code> {r.label}</td>
        <td className="pr-3">{r.low.value}: {name(r.low.winner)}</td><td className="pr-3">{r.high.value}: {name(r.high.winner)}</td>
        <td className={`num text-right ${r.flips_winner ? "font-medium text-loss" : ""}`}>{(r.swing ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}{r.flips_winner ? " · flips" : ""}</td></tr>)}</tbody>
    </table></div>
  </div>
}

export function SensitivityPanel({ scenarios }: { scenarios: ApiScenario[] }) {
  const [data, setData] = useState<SensitivityResult>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  async function run() {
    setBusy(true); setError(undefined)
    try { setData(await getSensitivity(scenarios)) } catch (e) { setError(e instanceof Error ? e.message : "Sensitivity failed") } finally { setBusy(false) }
  }
  return <section className="space-y-3 rounded-lg border bg-card p-5">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div><h3 className="font-display text-lg font-semibold">What would change this answer?</h3>
        <p className="text-sm text-muted-foreground">Re-runs every scenario with each assumption at the low and high end of its documented range.</p></div>
      <button type="button" disabled={busy || scenarios.length < 2} onClick={() => void run()} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Testing…" : "Test assumptions"}</button>
    </div>
    {error && <p role="alert" className="text-sm text-loss">{error}</p>}
    {data && <SensitivityTable data={data} names={scenarios.map((s) => s.name)} />}
  </section>
}
