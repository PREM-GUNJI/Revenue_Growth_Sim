import { useState } from "react"
import { runResearchToScenarios, type ApiScenario, type ResearchCandidateResponse } from "@/lib/api"

export function PricingEvidence({ onAdd }: { onAdd: (scenarios: ApiScenario[]) => void }) {
  const [method, setMethod] = useState("Willingness to Pay")
  const [result, setResult] = useState<ResearchCandidateResponse>()
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(false)
  async function run() {
    setLoading(true); setError(undefined)
    try { setResult(await runResearchToScenarios(method)) }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pricing evidence unavailable") }
    finally { setLoading(false) }
  }
  return <section className="space-y-4 rounded-xl border bg-card p-5">
    <div><p className="text-xs font-semibold uppercase tracking-wider text-primary">SYNTHETIC CONSUMER EVIDENCE</p>
      <h2 className="mt-1 text-lg font-semibold">Pricing evidence</h2>
      <p className="mt-1 text-sm text-muted-foreground">Illustrative synthetic research creates candidate prices. Volume, revenue and margin are calculated only by the deterministic RGM engine.</p></div>
    <div className="flex flex-wrap gap-2"><select aria-label="Pricing methodology" value={method} onChange={(event) => setMethod(event.target.value)} className="rounded border bg-background px-3 py-2 text-sm">
      <option>Willingness to Pay</option><option>Gabor-Granger</option><option>Van Westendorp Price Sensitivity Meter</option></select>
      <button disabled={loading} onClick={() => void run()} className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50">{loading ? "Running…" : "Generate candidates"}</button></div>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {result && <div className="space-y-3 rounded-lg bg-muted/40 p-3 text-sm">
      <p>{result.research.methodology} · {result.research.research_id} · {result.research.sample_size.toLocaleString()} synthetic respondents</p>
      <p className="break-all font-mono text-xs text-muted-foreground">Source data hash: {result.research.source_data_hash}</p>
      {result.scenarios.map((item) => <div key={item.scenario_id} className="flex flex-wrap items-center justify-between gap-2 border-t pt-2">
        <span>₹{item.provenance.candidate.price.toFixed(2)} / {item.provenance.candidate.pack} · {item.status}{item.status === "REFUSED" ? " · no modeled values" : " · deterministic engine result · " + item.result_hash.slice(0, 10)}</span>
        {item.status !== "REFUSED" && <button className="underline" onClick={() => onAdd([item.scenario])}>Add scenario</button>}
      </div>)}
    </div>}
  </section>
}
