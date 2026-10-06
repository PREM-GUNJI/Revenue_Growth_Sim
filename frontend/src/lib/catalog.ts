import type { ApiBand, ApiScenario, ApiScenarioResult } from "@/lib/api"

/** Static catalog facts (observed pack formats). Nothing here is a research or engine parameter. */
export const BRAND = "Aurora"
export const PACKS = [
  { id: "can_330ml", label: "330 ml can", short: "330 ml", litres: 0.33 },
  { id: "pet_500ml", label: "500 ml PET", short: "500 ml", litres: 0.5 },
  { id: "bottle_1500ml", label: "1.5 L bottle", short: "1.5 L", litres: 1.5 },
  { id: "multipack_6x330ml", label: "6 × 330 ml multipack", short: "6-pack", litres: 1.98 },
] as const
export type PackId = (typeof PACKS)[number]["id"]
export const skuFor = (pack: string, brand = BRAND) => `${brand}-${pack}`
export const packOf = (sku: string) => sku.slice(sku.indexOf("-") + 1)
export const packShort = (pack: string) => PACKS.find((p) => p.id === pack)?.short ?? pack
export const packLabel = (pack: string) => PACKS.find((p) => p.id === pack)?.label ?? pack

export const NO_COST_SHOCK = { aluminium_pct: 0, pet_resin_pct: 0, sugar_pct: 0 }
export const baselineLever = { price_index: 1, promo_depth_pct: 0, mechanic: "none", promo_weeks_per_month: 0 }
export const newScenario = (name: string, levers: ApiScenario["levers"] = {}, source?: ApiScenario["source"]): ApiScenario =>
  ({ schema_version: 1, name, levers, cost_shock: NO_COST_SHOCK, ...(source ? { source } : {}) })

export const sum = (values: Record<string, ApiBand>, edge: keyof ApiBand = "value") =>
  Object.values(values).reduce((total, band) => total + band[edge], 0)
export const totals = (r: ApiScenarioResult) => ({
  volume: sum(r.volume), gsv: sum(r.gsv), nsv: sum(r.nsv), gp: sum(r.gp),
  promoSpend: -Object.values(r.bridge).reduce((t, b) => t + b.promo_cents + b.trade_cents, 0) / 100,
  crossPack: Object.values(r.bridge).reduce((t, b) => t + b.cross_pack_cents, 0) / 100,
})
export const changePct = (value: number, base: number) => (base ? (value / base - 1) * 100 : 0)

export const signed = (v: number, digits = 1) =>
  `${v >= 0.5 * 10 ** -digits ? "+" : v <= -0.5 * 10 ** -digits ? "−" : ""}${Math.abs(v).toFixed(digits)}%`
export const tone = (v: number) => (v < -0.05 ? "text-loss" : v > 0.05 ? "text-gain" : "text-muted-foreground")
export const compact = (v: number) => new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(v)
export const inr = (v: number) => "₹" + v.toFixed(2)
export const SYNTHETIC = "SYNTHETIC CONSUMER EVIDENCE"
