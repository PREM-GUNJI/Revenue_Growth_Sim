import { SupportBar } from "@/components/support-bar"
import { PACKS, baselineLever, packOf, packShort, signed, skuFor } from "@/lib/catalog"
import { useWorkspace } from "./workspace-context"

const PRICE_MIN = 0.8, PRICE_MAX = 1.6, DEPTH_MAX = 50

export function ScenarioBuilder() {
  const { scenarios, setScenarios, activePack, setActivePack, addScenario, updateLever, envelope } = useWorkspace()
  const sku = skuFor(activePack)
  // Where the engine has data for this pack: price between the 1st and 99th percentile of history, promotion at observed depths.
  const [priceLo, priceHi] = envelope?.price_index_p1_p99[sku] ?? [PRICE_MIN, PRICE_MAX]
  const depthHi = envelope ? Math.max(...envelope.depth_steps) : DEPTH_MAX
  const mechanics = (envelope?.mechanics ?? ["TPR", "feature_display", "BOGO"]).filter((m) => m !== "none")
  return (
    <aside className="space-y-4 lg:sticky lg:top-24 lg:max-h-[calc(100svh-7rem)] lg:overflow-y-auto lg:pr-1" aria-label="Scenario builder">
      <div><h2 className="font-display text-xl font-semibold">Options</h2><p className="text-sm text-muted-foreground">Pick a pack and set its price and promotion. The green part of each slider is where the engine has data; past it the engine refuses and shows no numbers.</p></div>
      <div role="group" aria-label="Pack to edit" className="grid grid-cols-4 gap-1 rounded-lg bg-secondary p-1">
        {PACKS.map((p) => <button key={p.id} type="button" aria-pressed={activePack === p.id} onClick={() => setActivePack(p.id)} className={`rounded-md py-1.5 text-xs ${activePack === p.id ? "bg-ink font-medium text-white" : "hover:bg-card"}`}>{p.short}</button>)}
      </div>
      {scenarios.map((scenario, index) => {
        const lever = scenario.levers[sku] ?? baselineLever
        const others = Object.entries(scenario.levers).filter(([k, l]) => k !== sku && (l.price_index !== 1 || l.promo_depth_pct > 0))
          .map(([k, l]) => `${packShort(packOf(k))} ${l.price_index !== 1 ? signed((l.price_index - 1) * 100, 0) + " price" : ""}${l.promo_depth_pct > 0 ? ` ${l.promo_depth_pct}% promo` : ""}`.trim())
        const outside = lever.price_index < priceLo || lever.price_index > priceHi || lever.promo_depth_pct > depthHi
        return <div key={index} className={`space-y-4 rounded-lg border p-4 ${index === 0 ? "border-dashed bg-transparent" : "bg-card"} ${outside ? "border-loss/40" : ""}`}>
          <div className="flex items-center gap-2">
            <input aria-label="Scenario name" value={scenario.name} readOnly={index === 0} onChange={(event) => setScenarios((current) => current.map((item, i) => i === index ? { ...item, name: event.target.value } : item))} className="min-w-0 flex-1 rounded border border-transparent bg-transparent px-1 py-1 font-display text-base font-semibold hover:border-input focus:border-input" />
            {index > 0 && <button type="button" onClick={() => addScenario(index)} className="rounded px-1.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">Duplicate</button>}
            {index > 0 && <button type="button" onClick={() => setScenarios((current) => current.filter((_, i) => i !== index))} className="rounded px-1.5 py-1 text-xs text-loss hover:bg-loss/10">Remove</button>}
          </div>
          {index === 0 ? <p className="px-1 text-xs text-muted-foreground">Current price, no promotion. Every other scenario is measured against this one.</p> : <>
            <label className="block text-xs text-muted-foreground"><span className="flex justify-between"><span>Price index, {packShort(activePack)}</span><span className="num text-sm font-semibold text-foreground">{lever.price_index.toFixed(2)} <span className="font-normal text-muted-foreground">({signed((lever.price_index - 1) * 100, 0)})</span></span></span>
              <input aria-label="Price index" type="range" min={PRICE_MIN} max={PRICE_MAX} step="0.01" value={lever.price_index} onChange={(event) => updateLever(index, { price_index: Number(event.target.value) })} />
              <SupportBar min={PRICE_MIN} max={PRICE_MAX} lo={priceLo} hi={priceHi} />
              <span className="mt-0.5 block">Supported {priceLo.toFixed(2)} to {priceHi.toFixed(2)}</span></label>
            <label className="block text-xs text-muted-foreground"><span className="flex justify-between"><span>Promo depth, {packShort(activePack)}</span><span className="num text-sm font-semibold text-foreground">{lever.promo_depth_pct}%</span></span>
              <input aria-label="Promo depth" type="range" min="0" max={DEPTH_MAX} step="5" value={lever.promo_depth_pct} onChange={(event) => {
                const depth = Number(event.target.value)
                updateLever(index, { promo_depth_pct: depth, mechanic: depth === 0 ? "none" : lever.mechanic === "none" ? "TPR" : lever.mechanic, promo_weeks_per_month: depth === 0 ? 0 : Math.max(1, lever.promo_weeks_per_month) })
              }} />
              <SupportBar min={0} max={DEPTH_MAX} lo={0} hi={depthHi} />
              <span className="mt-0.5 block">Observed depths up to {depthHi}%</span></label>
            {lever.promo_depth_pct > 0 && <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-muted-foreground">Mechanic
                <select aria-label="Promotion mechanic" value={lever.mechanic} onChange={(e) => updateLever(index, { mechanic: e.target.value })} className="mt-1 block w-full rounded-md border bg-card px-2 py-1.5 text-sm text-foreground">{mechanics.map((m) => <option key={m}>{m}</option>)}</select></label>
              <label className="block text-xs text-muted-foreground"><span className="flex justify-between"><span>Weeks a month</span><span className="num text-sm font-semibold text-foreground">{lever.promo_weeks_per_month}</span></span>
                <input aria-label="Promotion weeks per month" type="range" min="1" max="4" step="1" value={lever.promo_weeks_per_month} onChange={(e) => updateLever(index, { promo_weeks_per_month: Number(e.target.value) })} className="mt-2" /></label>
            </div>}
            {outside && <p className="rounded bg-loss/5 p-2 text-xs text-loss">This setting is outside the data. The engine will refuse it and show no numbers; use the nearest supported option on the Compare step.</p>}
            {others.length > 0 && <p className="text-xs text-muted-foreground">Also set: {others.join("; ")}</p>}
          </>}
        </div>
      })}
      <button type="button" onClick={() => addScenario()} className="w-full rounded-lg border border-dashed border-input py-2.5 text-sm font-medium text-muted-foreground hover:border-primary hover:text-primary">Add option</button>
    </aside>
  )
}
