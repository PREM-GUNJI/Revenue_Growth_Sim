import { useEffect, useState } from "react"
import { CandidateTable, SyntheticBanner } from "@/components/evidence-parts"
import { conjointToScenarios } from "@/lib/api"
import type { ApiScenario, ApiScenarioResult, ConjointAlternative, EvidenceDefaults, ResearchBridgeResponse } from "@/lib/api"
import { BRAND, PACKS, packShort } from "@/lib/catalog"

const select = "rounded-md border bg-card px-2 py-1.5 text-sm"

export function ConjointPanel({ defaults, baseline, onAdd }: {
  defaults?: EvidenceDefaults; baseline?: ApiScenarioResult; onAdd: (scenario: ApiScenario) => void
}) {
  const [alts, setAlts] = useState<ConjointAlternative[]>([])
  const [result, setResult] = useState<ResearchBridgeResponse>()
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(false)
  const [seeded, setSeeded] = useState(false)
  if (defaults && !seeded) { setAlts(defaults.default_alternatives); setSeeded(true) }
  const key = JSON.stringify(alts)
  useEffect(() => {
    if (!alts.length) return
    let live = true
    const timer = setTimeout(() => {
      setLoading(true); setError(undefined)
      conjointToScenarios(alts, BRAND)
        .then((r) => { if (live) setResult(r) })
        .catch((cause: unknown) => { if (live) setError(cause instanceof Error ? cause.message : "Simulation failed") })
        .finally(() => { if (live) setLoading(false) })
    }, 350)
    return () => { live = false; clearTimeout(timer) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  const set = (i: number, change: Partial<ConjointAlternative>) => setAlts((cur) => cur.map((a, j) => j === i ? { ...a, ...change } : a))
  const shares = (result?.research.outputs.choice_share_pct as number[] | undefined) ?? []
  const segments = (result?.research.outputs.choice_share_pct_by_segment as Record<string, number[]> | undefined) ?? {}
  const label = (a: ConjointAlternative) => `${a.brand} ${packShort(a.pack)}, ₹${a.price}${a.promotion !== "None" ? ", " + a.promotion : ""}`
  const top = Math.max(1, ...shares)
  return <div className="space-y-6">
    <SyntheticBanner />
    <div><h2 className="font-display text-2xl font-semibold">Conjoint simulation</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Compare brand, pack, price and promotion configurations to see which synthetic shoppers would choose. Winning {BRAND} configurations become candidates for the simulator.</p></div>
    <p role="note" className="rounded-md border border-primary/30 bg-primary/5 px-4 py-3 text-sm font-medium">{defaults?.statement ?? "This simulation uses supplied synthetic utilities. It does not estimate or fit consumer utilities."}</p>

    <section className="rounded-lg border bg-card p-5">
      <h3 className="font-display text-lg font-semibold">Configurations to compare</h3>
      <div className="mt-3 space-y-2">
        {alts.map((a, i) => <div key={i} className="grid grid-cols-2 items-end gap-2 md:grid-cols-[1fr_1fr_6rem_1fr_auto]">
          <label className="text-xs text-muted-foreground">Brand<select aria-label="Brand" value={a.brand} onChange={(e) => set(i, { brand: e.target.value })} className={select + " mt-1 block w-full"}>{defaults?.brands.map((b) => <option key={b}>{b}</option>)}</select></label>
          <label className="text-xs text-muted-foreground">Pack<select aria-label="Pack" value={a.pack} onChange={(e) => set(i, { pack: e.target.value })} className={select + " mt-1 block w-full"}>{PACKS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
          <label className="text-xs text-muted-foreground">Price (₹)<input aria-label="Price" type="number" min="1" step="0.5" value={a.price} onChange={(e) => set(i, { price: Number(e.target.value) })} className={select + " mt-1 block w-full"} /></label>
          <label className="text-xs text-muted-foreground">Promotion<select aria-label="Promotion" value={a.promotion} onChange={(e) => set(i, { promotion: e.target.value })} className={select + " mt-1 block w-full"}>{defaults?.promotions.map((p) => <option key={p}>{p}</option>)}</select></label>
          <button type="button" disabled={alts.length < 2} onClick={() => setAlts((cur) => cur.filter((_, j) => j !== i))} className="rounded px-2 py-1.5 text-xs text-loss hover:bg-loss/10 disabled:opacity-40">Remove</button>
        </div>)}
      </div>
      <button type="button" onClick={() => setAlts((cur) => [...cur, { ...cur[cur.length - 1] }])} className="mt-3 rounded-md border border-dashed px-3 py-1.5 text-sm text-muted-foreground hover:border-primary hover:text-primary">Add configuration</button>
    </section>

    {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
    {result && <div className={`space-y-6 transition-opacity ${loading ? "opacity-60" : ""}`}>
      <section className="rounded-lg border bg-card p-5">
        <h3 className="font-display text-lg font-semibold">Simulated choice share</h3>
        <p className="mb-3 text-xs text-muted-foreground">Share of {result.research.sample_size.toLocaleString()} synthetic respondents choosing each configuration. Shares add up to 100%. This is preference, not market share or a volume forecast.</p>
        <div className="space-y-2">{alts.map((a, i) => <div key={i} className="grid grid-cols-[minmax(0,15rem)_1fr_3.5rem] items-center gap-3 text-sm">
          <span className="truncate">{label(a)}</span><div className="h-3 rounded bg-secondary"><div className="bar h-3 rounded" style={{ width: `${((shares[i] ?? 0) / top) * 100}%`, background: a.brand === BRAND ? "var(--gain)" : "var(--muted-foreground)" }} /></div><span className="num text-right font-semibold">{(shares[i] ?? 0).toFixed(1)}%</span></div>)}</div>
        <details className="mt-4 text-sm"><summary className="cursor-pointer text-muted-foreground">Share by segment</summary>
          <table className="mt-2 w-full text-xs"><thead><tr className="text-left text-muted-foreground"><th className="py-1 pr-2">Segment</th>{alts.map((a, i) => <th key={i} className="px-2 text-right font-normal">{a.brand} {packShort(a.pack)} ₹{a.price}</th>)}</tr></thead>
            <tbody>{Object.entries(segments).map(([name, row]) => <tr key={name} className="border-t"><td className="py-1 pr-2">{name.replace("_", " ")}</td>{row.map((v, i) => <td key={i} className="num px-2 text-right">{v.toFixed(1)}%</td>)}</tr>)}</tbody></table></details>
      </section>
      <section>
        <h3 className="font-display text-lg font-semibold">{BRAND} candidates and their modeled outcomes</h3>
        <p className="mb-3 text-sm text-muted-foreground">Ordered by simulated choice share. Commercial results come from the engine after the support check.</p>
        <CandidateTable rows={result.scenarios} baseline={baseline} onAdd={onAdd} />
      </section>
      <section className="rounded-lg border bg-card p-5"><h3 className="font-display text-lg font-semibold">Limitations</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">{result.research.limitations.map((l) => <li key={l}>{l}</li>)}</ul></section>
    </div>}
  </div>
}
