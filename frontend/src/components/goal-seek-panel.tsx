import { useState } from "react"
import { goalSeek, type ApiScenario, type GoalSeekResult } from "@/lib/api"

export function GoalSeekPanel({ onAdd }: { onAdd: (scenario: ApiScenario) => void }) {
  const [cap, setCap] = useState(5)
  const [data, setData] = useState<GoalSeekResult>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  async function run() {
    setBusy(true); setError(undefined)
    try { setData(await goalSeek(cap)) } catch (e) { setError(e instanceof Error ? e.message : "Search failed") } finally { setBusy(false) }
  }
  return <section className="space-y-3 rounded-lg border bg-card p-5">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><h3 className="font-display text-lg font-semibold">Find me the best option</h3>
        <p className="text-sm text-muted-foreground">Searches single-SKU and portfolio-wide price and promo moves for the highest gross profit within your volume limit. Unsupported moves are dropped, never estimated.</p></div>
      <div className="flex items-end gap-2">
        <label className="text-xs text-muted-foreground">Max volume loss %<input type="number" min={0} max={100} value={cap} onChange={(e) => setCap(Number(e.target.value))} className="mt-1 block w-24 rounded-md border bg-background p-2 text-sm text-foreground" /></label>
        <button type="button" disabled={busy} onClick={() => void run()} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Searching…" : "Search"}</button>
      </div>
    </div>
    {error && <p role="alert" className="text-sm text-loss">{error}</p>}
    {data && <div className="space-y-2">
      <p className="text-xs text-muted-foreground">{data.evaluated} options evaluated, {data.feasible} beat the baseline within the limit.</p>
      {data.top.length === 0 && <p className="text-sm">No option beats the baseline within that volume limit.</p>}
      {data.top.map((item) => <div key={item.scenario_id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
        <div><span className="font-medium">{item.scenario.name}</span>
          <span className="num ml-2 text-gain">gross profit +{item.gp_change.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
          <span className="num ml-2 text-muted-foreground">volume {item.volume_loss_pct > 0 ? "−" : "+"}{Math.abs(item.volume_loss_pct).toFixed(1)}%</span></div>
        <button type="button" onClick={() => onAdd(item.scenario)} className="rounded-md border px-2.5 py-1.5 text-xs font-medium hover:bg-secondary">Add to simulator</button>
      </div>)}
    </div>}
  </section>
}
