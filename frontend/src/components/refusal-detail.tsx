import type { RefusalReason } from "@/lib/types"

const LEVER_LABEL: Record<string, string> = { price_index: "Price index", promo_depth_pct: "Promo depth %", joint_support: "Price + promo combination" }
const fmt = (v: number | string) => typeof v === "number" ? Number(v.toFixed(3)).toString() : v

/** Which SKU and lever broke the supported range, what was asked for, and what the data supports. */
export function RefusalDetail({ reasons }: { reasons: RefusalReason[] }) {
  return <ul className="mt-2 space-y-2">
    {reasons.map((r) => {
      const [lo, hi] = r.range
      const numeric = typeof r.requested === "number" && typeof lo === "number" && typeof hi === "number" && r.lever === "price_index"
      const pos = numeric ? Math.min(100, Math.max(0, ((r.requested as number) - (lo as number)) / ((hi as number) - (lo as number)) * 50 + 25)) : 0
      return <li key={r.skuId + r.lever} className="rounded border border-loss/30 bg-card/70 p-2 text-sm">
        <div className="font-medium">{r.skuId} <span className="font-normal text-muted-foreground">· {LEVER_LABEL[r.lever] ?? r.lever}</span></div>
        <div className="text-xs text-muted-foreground">Requested <strong className="text-loss">{fmt(r.requested)}</strong> · supported {r.range.map(fmt).join(" to ")}</div>
        {numeric && <div className="relative mt-1 h-2 rounded bg-secondary" aria-hidden>
          <div className="absolute inset-y-0 left-1/4 w-1/2 rounded bg-gain/40" />
          <div className="absolute -top-0.5 h-3 w-1 rounded bg-loss" style={{ left: `${pos}%` }} />
        </div>}
      </li>
    })}
  </ul>
}
