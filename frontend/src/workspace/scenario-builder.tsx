import { PACKS, baselineLever, packOf, packShort, signed, skuFor } from "@/lib/catalog"
import { useWorkspace } from "./workspace-context"

export function ScenarioBuilder() {
  const { scenarios, setScenarios, activePack, setActivePack, addScenario, updateLever } = useWorkspace()
  return (
    <aside className="space-y-4 lg:sticky lg:top-24 lg:max-h-[calc(100svh-7rem)] lg:overflow-y-auto lg:pr-1" aria-label="Scenario builder">
          <div><h2 className="font-display text-xl font-semibold">Scenarios</h2><p className="text-sm text-muted-foreground">Pick a pack, drag its levers, and results update.</p></div>
          <div role="group" aria-label="Pack to edit" className="grid grid-cols-4 gap-1 rounded-lg bg-secondary p-1">
            {PACKS.map((p) => <button key={p.id} type="button" aria-pressed={activePack === p.id} onClick={() => setActivePack(p.id)} className={`rounded-md py-1.5 text-xs ${activePack === p.id ? "bg-ink font-medium text-white" : "hover:bg-card"}`}>{p.short}</button>)}
          </div>
          {scenarios.map((scenario, index) => {
            const sku = skuFor(activePack)
            const lever = scenario.levers[sku] ?? baselineLever
            const others = Object.entries(scenario.levers).filter(([k, l]) => k !== sku && (l.price_index !== 1 || l.promo_depth_pct > 0))
              .map(([k, l]) => `${packShort(packOf(k))} ${l.price_index !== 1 ? signed((l.price_index - 1) * 100, 0) + " price" : ""}${l.promo_depth_pct > 0 ? ` ${l.promo_depth_pct}% promo` : ""}`.trim())
            return <div key={index} className={`space-y-4 rounded-lg border p-4 ${index === 0 ? "border-dashed bg-transparent" : "bg-card"}`}>
              <div className="flex items-center gap-2">
                <input aria-label="Scenario name" value={scenario.name} readOnly={index === 0} onChange={(event) => setScenarios((current) => current.map((item, i) => i === index ? { ...item, name: event.target.value } : item))} className="min-w-0 flex-1 rounded border border-transparent bg-transparent px-1 py-1 font-display text-base font-semibold hover:border-input focus:border-input" />
                {index > 0 && <button type="button" onClick={() => addScenario(index)} className="rounded px-1.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">Duplicate</button>}
                {index > 0 && <button type="button" onClick={() => setScenarios((current) => current.filter((_, i) => i !== index))} className="rounded px-1.5 py-1 text-xs text-loss hover:bg-loss/10">Remove</button>}
              </div>
              {index === 0 ? <p className="px-1 text-xs text-muted-foreground">Current price, no promotion. Every other scenario is measured against this one.</p> : <>
                <label className="block text-xs text-muted-foreground"><span className="flex justify-between"><span>Price index, {packShort(activePack)}</span><span className="num text-sm font-semibold text-foreground">{lever.price_index.toFixed(2)} <span className="font-normal text-muted-foreground">({signed((lever.price_index - 1) * 100, 0)})</span></span></span>
                  <input aria-label="Price index" type="range" min="0.8" max="1.6" step="0.01" value={lever.price_index} onChange={(event) => updateLever(index, { price_index: Number(event.target.value) })} /></label>
                <label className="block text-xs text-muted-foreground"><span className="flex justify-between"><span>Promo depth, {packShort(activePack)}</span><span className="num text-sm font-semibold text-foreground">{lever.promo_depth_pct}%</span></span>
                  <input aria-label="Promo depth" type="range" min="0" max="50" step="5" value={lever.promo_depth_pct} onChange={(event) => {
                    const depth = Number(event.target.value)
                    updateLever(index, { promo_depth_pct: depth, mechanic: depth === 0 ? "none" : "TPR", promo_weeks_per_month: depth === 0 ? 0 : Math.max(1, lever.promo_weeks_per_month) })
                  }} /></label>
                {others.length > 0 && <p className="text-xs text-muted-foreground">Also set: {others.join("; ")}</p>}
              </>}
            </div>
          })}
          <button type="button" onClick={() => addScenario()} className="w-full rounded-lg border border-dashed border-input py-2.5 text-sm font-medium text-muted-foreground hover:border-primary hover:text-primary">Add scenario</button>
        </aside>
  )
}
