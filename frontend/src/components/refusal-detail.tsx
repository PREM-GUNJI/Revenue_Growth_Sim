import { useContext } from "react"
import { BRAND, inr, packLabel, packOf } from "@/lib/catalog"
import { useDetailMode } from "@/lib/preferences"
import type { RefusalReason } from "@/lib/types"
import { WorkspaceContext } from "@/workspace/workspace-context"

const LEVER_LABEL: Record<string, string> = { price_index: "Shelf price", promo_depth_pct: "Promotion depth", joint_support: "Price and promotion together" }
const fmt = (v: number | string) => typeof v === "number" ? Number(v.toFixed(3)).toString() : v

/** Which pack and lever went past the data, what was asked for, and what the data supports, in rupees where possible. */
export function RefusalDetail({ reasons }: { reasons: RefusalReason[] }) {
  const situation = useContext(WorkspaceContext)?.situation
  const [detail] = useDetailMode()
  const refPrice = (sku: string) => situation?.skus.find((s) => s.sku_id === sku)?.price
  return <ul className="mt-2 space-y-2">
    {reasons.map((r) => {
      const [lo, hi] = r.range
      const numeric = typeof r.requested === "number" && typeof lo === "number" && typeof hi === "number" && r.lever === "price_index"
      const pos = numeric ? Math.min(100, Math.max(0, ((r.requested as number) - (lo as number)) / ((hi as number) - (lo as number)) * 50 + 25)) : 0
      const ref = numeric ? refPrice(r.skuId) : undefined
      const pack = r.skuId.startsWith(BRAND + "-") ? packLabel(packOf(r.skuId)) : r.skuId
      const show = (v: number | string) => ref !== undefined && typeof v === "number" ? inr(ref * v) : r.lever === "promo_depth_pct" && typeof v === "number" ? `${fmt(v)}%` : fmt(v)
      return <li key={r.skuId + r.lever} className="rounded border border-loss/30 bg-card/70 p-2 text-sm">
        <div className="font-medium">{pack} <span className="font-normal text-muted-foreground">· {LEVER_LABEL[r.lever] ?? r.lever}</span></div>
        <div className="text-xs text-muted-foreground">You asked for <strong className="text-loss">{show(r.requested)}</strong>; we have data between {r.range.map(show).join(" and ")}, so we won't guess.
          {detail && <span className="ml-1 font-mono">({r.skuId} {r.lever} {fmt(r.requested)}, supported {r.range.map(fmt).join(" to ")})</span>}</div>
        {numeric && <div className="relative mt-1 h-2 rounded bg-secondary" aria-hidden>
          <div className="absolute inset-y-0 left-1/4 w-1/2 rounded bg-gain/40" />
          <div className="absolute -top-0.5 h-3 w-1 rounded bg-loss" style={{ left: `${pos}%` }} />
        </div>}
      </li>
    })}
  </ul>
}
