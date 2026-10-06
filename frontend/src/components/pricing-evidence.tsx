import { useEffect, useState } from "react"
import { CandidateTable, SyntheticBanner } from "@/components/evidence-parts"
import { getConsumerSummary, researchToScenarios } from "@/lib/api"
import type { ApiScenario, ApiScenarioResult, ConsumerSummary, ResearchBridgeResponse } from "@/lib/api"
import { PACKS, inr, packLabel } from "@/lib/catalog"

const METHODS = [
  { id: "Willingness to Pay", blurb: "What synthetic respondents say they would pay. Percentiles become candidate prices." },
  { id: "Gabor-Granger", blurb: "Share who would still buy at each tested price. The revenue-index peak and the highest accepted price become candidates." },
  { id: "Van Westendorp Price Sensitivity Meter", blurb: "Four price questions give an acceptable range. The optimal and indifference points become candidates." },
]

function PriceStrip({ points }: { points: Array<{ label: string; value: number }> }) {
  const values = points.map((p) => p.value), lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1
  return <div className="relative mx-6 mb-8 mt-8 h-1 rounded bg-secondary">
    {points.map((p, i) => <div key={p.label} className="absolute -top-1" style={{ left: `${((p.value - lo) / span) * 100}%` }}>
      <span className="block size-3 -translate-x-1/2 rounded-full bg-primary" />
      <span className={`num absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-xs ${i % 2 ? "top-5" : "-top-6"}`}>{p.label} {inr(p.value)}</span></div>)}
  </div>
}

function Outputs({ result }: { result: ResearchBridgeResponse["research"] }) {
  const o = result.outputs as Record<string, number | Record<string, number>>
  if (result.methodology === "Willingness to Pay")
    return <PriceStrip points={["p25", "p50", "p75"].filter((k) => k in o).map((k) => ({ label: k.toUpperCase(), value: o[k] as number }))} />
  if (result.methodology === "Van Westendorp Price Sensitivity Meter")
    return <PriceStrip points={[["pmc", "Too cheap edge"], ["opp", "Optimal"], ["ipp", "Indifference"], ["pme", "Too dear edge"]].flatMap(([k, label]) => o[k] == null ? [] : [{ label, value: o[k] as number }])} />
  const accept = o.acceptance_share_by_price as Record<string, number>
  return <div className="space-y-1.5">{Object.entries(accept).map(([price, share]) => <div key={price} className="grid grid-cols-[4.5rem_1fr_3rem] items-center gap-3 text-xs">
    <span className="num">{inr(Number(price))}</span><div className="h-2 rounded bg-secondary"><div className="bar h-2 rounded bg-primary" style={{ width: `${share * 100}%` }} /></div><span className="num text-right">{(share * 100).toFixed(0)}%</span></div>)}
    <p className="pt-1 text-xs text-muted-foreground">Share of synthetic respondents who would still buy at each tested price.</p></div>
}

export function PricingEvidence({ baseline, onAdd, onOpenConjoint }: {
  baseline?: ApiScenarioResult; onAdd: (scenario: ApiScenario) => void; onOpenConjoint: () => void
}) {
  const [method, setMethod] = useState(METHODS[0].id)
  const [pack, setPack] = useState<string>("pet_500ml")
  const [summary, setSummary] = useState<ConsumerSummary>()
  const [result, setResult] = useState<ResearchBridgeResponse>()
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(false)
  useEffect(() => { getConsumerSummary().then(setSummary).catch(() => undefined) }, [])
  useEffect(() => {
    let live = true
    setLoading(true); setError(undefined)
    researchToScenarios(method, pack)
      .then((r) => { if (live) setResult(r) })
      .catch((cause: unknown) => { if (live) setError(cause instanceof Error ? cause.message : "Pricing evidence unavailable") })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [method, pack])
  const blurb = METHODS.find((m) => m.id === method)?.blurb
  return <div className="space-y-6">
    <SyntheticBanner />
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><h2 className="font-display text-2xl font-semibold">Pricing evidence</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Consumer evidence suggests candidate prices. Each candidate goes through the support check and the deterministic engine before it can be compared.</p></div>
      <button type="button" onClick={onOpenConjoint} className="rounded-md border px-3 py-2 text-sm font-medium hover:bg-secondary">Open conjoint simulation</button>
    </div>

    <section className="grid gap-4 rounded-lg border bg-card p-5 md:grid-cols-[1fr_auto]">
      <div>
        <div role="tablist" aria-label="Methodology" className="flex flex-wrap gap-1 rounded-lg bg-secondary p-1">
          {METHODS.map((m) => <button key={m.id} role="tab" aria-selected={method === m.id} type="button" onClick={() => setMethod(m.id)} className={`rounded-md px-3 py-1.5 text-sm ${method === m.id ? "bg-ink font-medium text-white" : "hover:bg-card"}`}>{m.id === "Van Westendorp Price Sensitivity Meter" ? "Van Westendorp" : m.id}</button>)}
        </div>
        <p className="mt-3 text-sm text-muted-foreground">{blurb}</p>
      </div>
      <label className="text-xs text-muted-foreground">Pack<select aria-label="Pack" value={pack} onChange={(e) => setPack(e.target.value)} className="mt-1 block rounded-md border bg-card px-2 py-2 text-sm text-foreground">
        {PACKS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
    </section>

    {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
    {result && <div className={`space-y-6 transition-opacity ${loading ? "opacity-60" : ""}`}>
      <section className="rounded-lg border bg-card p-5">
        <h3 className="font-display text-lg font-semibold">What the synthetic respondents said</h3>
        <p className="mb-2 text-xs text-muted-foreground">{result.research.methodology}, {packLabel(pack)}, {result.research.sample_size.toLocaleString()} synthetic respondents, <code>{result.research.research_id}</code></p>
        <Outputs result={result.research} />
      </section>
      <section>
        <h3 className="font-display text-lg font-semibold">Candidate prices and their modeled outcomes</h3>
        <p className="mb-3 text-sm text-muted-foreground">Changes are against the baseline on the comparison board. Outcomes come from the engine, never from the research.</p>
        <CandidateTable rows={result.scenarios} baseline={baseline} onAdd={onAdd} />
      </section>
      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border bg-card p-5"><h3 className="font-display text-lg font-semibold">Limitations</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">{result.research.limitations.map((l) => <li key={l}>{l}</li>)}</ul></div>
        <div className="rounded-lg border bg-card p-5"><h3 className="font-display text-lg font-semibold">Assumptions used</h3>
          <ul className="mt-2 space-y-1 text-sm text-muted-foreground">{result.research.assumptions.map((a) => <li key={a}><code>{a.split(":")[0]}</code>{a.slice(a.indexOf(":"))}</li>)}</ul></div>
      </section>
    </div>}

    {summary && <section className="rounded-lg border bg-card p-5">
      <h3 className="font-display text-lg font-semibold">Respondent comments</h3>
      <p className="mb-3 text-xs text-muted-foreground">{summary.note}</p>
      <ul className="grid gap-3 md:grid-cols-2">{summary.sample_comments.map((c) => <li key={c.respondent_id} className="rounded-md bg-secondary/60 p-3 text-sm">
        <p>&ldquo;{c.comment}&rdquo;</p><p className="mt-1 text-xs text-muted-foreground">{c.respondent_id}, {c.segment.replace("_", " ")} (synthetic)</p></li>)}</ul>
    </section>}
  </div>
}
