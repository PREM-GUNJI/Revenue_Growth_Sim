import { useState } from "react"
import type { ScenarioResult } from "@/lib/types"
export type HeatCell = { price: number; depth: number; status: "SUPPORTED" | "EDGE" | "REFUSED"; gp: number | null }

type BridgeParts = {
  price_cents: number
  volume_cents: number
  cross_pack_cents: number
  promo_cents: number
  trade_cents: number
  cogs_cents: number
}
type BridgeMap = Record<string, BridgeParts>


const W = 620
const H = 280
const labels = ["Price", "Volume", "Cross-pack", "Promo", "Trade", "COGS"] as const
const keys = ["price_cents", "volume_cents", "cross_pack_cents", "promo_cents", "trade_cents", "cogs_cents"] as const

function TradeoffPlane({ scenarios }: { scenarios: ScenarioResult[] }) {
  const points = scenarios.filter((s) => s.status !== "REFUSED" && s.delta)
  const x = (value: number) => 38 + ((value + 20) / 40) * 550
  const y = (value: number) => 230 - ((value + 50) / 100) * 200
  return <section className="rounded-lg border p-4">
    <h3 className="font-semibold">Trade-off plane</h3>
    <p className="mb-2 text-xs text-muted-foreground">Scenario changes versus baseline; refused requests have no plotted values.</p>
    <div className="overflow-x-auto"><svg role="img" aria-label="Trade-off plane of volume change and margin change" viewBox={"0 0 " + W + " " + H} className="h-64 min-w-[520px] w-full">
      <line x1="38" y1={y(0)} x2="588" y2={y(0)} stroke="currentColor" opacity=".22" />
      <line x1={x(0)} y1="30" x2={x(0)} y2="230" stroke="currentColor" opacity=".22" />
      <text x="300" y="270" textAnchor="middle" fontSize="12" fill="currentColor">Δ Volume (%)</text>
      <text x="12" y="18" fontSize="12" fill="currentColor">Δ Margin (%)</text>
      {points.map((s, i) => {
        const dx = s.delta?.volumePct ?? 0
        const dy = s.delta?.marginPct ?? 0
        return <g key={s.scenarioId + "-" + i}>
          <circle cx={x(Math.max(-20, Math.min(20, dx)))} cy={y(Math.max(-50, Math.min(50, dy)))} r={s.isBaseline ? 7 : 6} fill={dy < 0 ? "var(--color-destructive)" : "var(--color-primary)"} />
          <text x={x(Math.max(-20, Math.min(20, dx))) + 9} y={y(Math.max(-50, Math.min(50, dy))) - 7} fontSize="10" fill="currentColor">{s.name.slice(0, 18)}</text>
        </g>
      })}
      <text x="38" y="248" fontSize="10" fill="currentColor">-20</text><text x="570" y="248" fontSize="10" fill="currentColor">+20</text>
    </svg></div>
  </section>
}

function MarginWaterfall({ bridge }: { bridge?: BridgeMap }) {
  const totals = keys.map((key) => Object.values(bridge ?? {}).reduce((sum, item) => sum + item[key], 0) / 100)
  const cumulative = [0]
  totals.forEach((amount) => cumulative.push(cumulative[cumulative.length - 1] + amount))
  const min = Math.min(0, ...cumulative), max = Math.max(0, ...cumulative)
  const span = max - min || 1
  const y = (value: number) => 220 - ((value - min) / span) * 175
  const zero = y(0)
  return <section className="rounded-lg border p-4">
    <h3 className="font-semibold">Margin waterfall</h3>
    <p className="mb-2 text-xs text-muted-foreground">Engine margin bridge aggregated across SKUs for the selected evaluated scenario.</p>
    {!bridge ? <p className="text-sm text-muted-foreground">Select an evaluated scenario to view its bridge.</p> :
      <div className="overflow-x-auto"><svg role="img" aria-label="Margin change waterfall in dollars" viewBox={"0 0 " + W + " 280"} className="h-64 min-w-[520px] w-full">
        <line x1="28" y1={zero} x2="600" y2={zero} stroke="currentColor" opacity=".3" />
        {totals.map((amount, i) => {
          const start = cumulative[i], end = cumulative[i + 1]
          const top = y(Math.max(start, end)), height = Math.max(2, Math.abs(y(start) - y(end)))
          return <g key={keys[i]}>
            <rect x={42 + i * 94} y={top} width="48" height={height} rx="3" fill={amount < 0 ? "var(--color-destructive)" : "var(--color-primary)"} opacity=".82" />
            <text x={66 + i * 94} y="246" textAnchor="middle" fontSize="9" fill="currentColor">{labels[i]}</text>
            <text x={66 + i * 94} y={top - 5} textAnchor="middle" fontSize="9" fill="currentColor">{amount >= 0 ? "+" : ""}{amount.toFixed(0)}</text>
          </g>
        })}
      </svg></div>}
  </section>
}

function PricePromoHeatmap({ cells, baselineGp, onGenerate, loading }: {
  cells: HeatCell[]; baselineGp: number; onGenerate: () => void; loading: boolean
}) {
  const prices = [0.92, 0.96, 1, 1.04, 1.08]
  const depths = [0, 10, 20, 30]
  const byKey = new Map(cells.map((cell) => [cell.price.toFixed(2) + ":" + cell.depth, cell]))
  return <section className="rounded-lg border p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-semibold">Price × promotion sweep</h3><p className="text-xs text-muted-foreground">Margin change for Aurora can; striped cells are refused by the support envelope.</p></div>
      <button type="button" onClick={onGenerate} disabled={loading} className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50">{loading ? "Calculating…" : cells.length ? "Refresh heatmap" : "Generate heatmap"}</button>
    </div>
    <div className="mt-3 grid grid-cols-[auto_repeat(5,minmax(3.5rem,1fr))] gap-1 text-center text-xs">
      <span className="p-2">Depth ↓ / Price →</span>{prices.map((price) => <span key={price} className="p-2">{price.toFixed(2)}</span>)}
      {depths.map((depth) => <div key={depth} className="contents"><span className="p-2">{depth}%</span>{prices.map((price) => {
        const cell = byKey.get(price.toFixed(2) + ":" + depth)
        if (!cell) return <span key={price} className="rounded border bg-muted/30 p-2 text-muted-foreground">—</span>
        if (cell.status === "REFUSED" || cell.gp === null) return <span key={price} title="REFUSED: outside supported joint data" className="rounded border p-2 text-destructive" style={{ backgroundImage: "repeating-linear-gradient(135deg, transparent, transparent 5px, rgb(127 29 29 / 12%) 5px, rgb(127 29 29 / 12%) 10px)" }}>REF</span>
        const deltaPct = baselineGp ? (cell.gp / baselineGp - 1) * 100 : 0
        return <span key={price} title={cell.status + " margin delta " + deltaPct.toFixed(1) + "%"} className={"rounded border p-2 " + (deltaPct >= 0 ? "bg-emerald-500/15" : "bg-destructive/10")}>{deltaPct > 0 ? "+" : ""}{deltaPct.toFixed(1)}%</span>
      })}</div>)}
    </div>
  </section>
}

export function AnalyticsViews({ scenarios, bridges, heatmap, baselineGp, onGenerateHeatmap, heatmapLoading }: {
  scenarios: ScenarioResult[]
  bridges: Record<string, BridgeMap>
  heatmap: HeatCell[]
  baselineGp: number
  onGenerateHeatmap: () => void
  heatmapLoading: boolean
}) {
  const evaluated = scenarios.filter((s) => s.status !== "REFUSED")
  const [selected, setSelected] = useState(evaluated[0]?.scenarioId ?? "")
  const chosen = evaluated.find((s) => s.scenarioId === selected)
  return <div className="space-y-4">
    <TradeoffPlane scenarios={scenarios} />
    <label className="flex items-center gap-2 text-sm">Waterfall scenario<select value={selected} onChange={(event) => setSelected(event.target.value)} className="rounded border bg-background px-2 py-1">{evaluated.map((item) => <option key={item.scenarioId} value={item.scenarioId}>{item.name}</option>)}</select></label>
    <MarginWaterfall bridge={chosen ? bridges[chosen.scenarioId] : undefined} />
    <PricePromoHeatmap cells={heatmap} baselineGp={baselineGp} onGenerate={onGenerateHeatmap} loading={heatmapLoading} />
  </div>
}



