import { useState } from "react"
import { CandidateTable, SyntheticBanner } from "@/components/evidence-parts"
import {
  designPersonas, personaCandidates, personaReport, personaVoices,
  type ApiScenario, type ApiScenarioResult, type PersonaDesign, type PersonaReport, type PersonaVoicesResult, type ResearchBridgeResponse,
} from "@/lib/api"
import { inr, packLabel } from "@/lib/catalog"

const PACKS = ["can_330ml", "pet_500ml", "bottle_1500ml", "multipack_6x330ml"]
const BRIEFS = [
  "A student-heavy market near a university, with some young families and a few premium health-seekers.",
  "A suburban family market where bigger packs and weekly stock-ups matter most.",
  "A price-war market where shoppers switch brands for promotions.",
]
const msg = (e: unknown) => e instanceof Error ? e.message : "Request failed"
const bar = (value: number) => <div className="h-2 rounded bg-secondary"><div className="h-2 rounded bg-primary" style={{ width: `${Math.min(100, value * 100)}%` }} /></div>

export function PersonasPanel({ baseline, onAdd }: { baseline?: ApiScenarioResult; onAdd: (scenario: ApiScenario) => void }) {
  const [brief, setBrief] = useState(BRIEFS[0])
  const [pack, setPack] = useState("pet_500ml")
  const [design, setDesign] = useState<PersonaDesign>()
  const [report, setReport] = useState<PersonaReport>()
  const [voices, setVoices] = useState<PersonaVoicesResult>()
  const [candidates, setCandidates] = useState<ResearchBridgeResponse>()
  const [price, setPrice] = useState("45")
  const [busy, setBusy] = useState<string>()
  const [error, setError] = useState<string>()

  async function run<T>(name: string, job: () => Promise<T>, done: (value: T) => void) {
    setBusy(name); setError(undefined)
    try { done(await job()) } catch (e) { setError(msg(e)) } finally { setBusy(undefined) }
  }
  const mix = design?.mix
  const reset = () => { setReport(undefined); setVoices(undefined); setCandidates(undefined) }
  const priceGrid = report?.personas.find((p) => p.acceptance_by_price)?.acceptance_by_price
  const prices = priceGrid ? Object.keys(priceGrid) : []

  return <div className="space-y-6">
    <SyntheticBanner>Personas are synthetic customer types designed by an AI model from your brief. The seeded generator turns them into respondents, so the numbers are reproducible. The reactions further down are illustrative wording only and never feed a calculation.</SyntheticBanner>
    <div><h2 className="font-display text-2xl font-semibold">Customer personas</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Describe your market in plain words. The AI proposes who your customers are; you check the numbers it chose before anything is generated.</p></div>

    <section className="space-y-3 rounded-lg border bg-card p-5">
      <label htmlFor="persona-brief" className="block text-sm font-medium">Describe the market</label>
      <textarea id="persona-brief" rows={3} maxLength={1000} value={brief} onChange={(e) => setBrief(e.target.value)} className="w-full rounded-md border bg-background p-3 text-sm" />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" disabled={!!busy || brief.trim().length < 3} onClick={() => void run("design", () => designPersonas(brief), (d) => { setDesign(d); reset() })} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy === "design" ? "Designing…" : "Design personas"}</button>
        {BRIEFS.map((text) => <button key={text} type="button" onClick={() => setBrief(text)} className="rounded-md border px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground">{text.slice(0, 40)}…</button>)}
      </div>
      {error && <p role="alert" className="text-sm text-loss">{error}</p>}
    </section>

    {design && mix && <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-lg font-semibold">Proposed personas</h3>
        <span className="rounded border border-edge/40 bg-edge/10 px-2 py-0.5 text-xs text-edge">{design.label}</span>
        <span className="text-xs text-muted-foreground">{design.model_id} · mix {design.mix_hash.slice(0, 10)}</span></div>
      <div className="overflow-x-auto rounded-lg border bg-card"><table className="w-full min-w-[640px] text-left text-sm">
        <thead className="bg-secondary text-xs text-muted-foreground"><tr><th className="p-2">Persona</th><th className="p-2 text-right">Share</th><th className="p-2">Price sensitivity</th><th className="p-2">Promo sensitivity</th></tr></thead>
        <tbody>{mix.personas.map((p) => <tr key={p.name} className="border-t align-top">
          <td className="p-2"><span className="font-medium">{p.name}</span><p className="text-xs text-muted-foreground">{p.description}</p></td>
          <td className="num p-2 text-right">{(p.share * 100).toFixed(0)}%</td>
          <td className="p-2"><div className="flex items-center gap-2"><span className="num w-8 text-xs">{p.price_sensitivity.toFixed(2)}</span><div className="w-24">{bar(p.price_sensitivity)}</div></div></td>
          <td className="p-2"><div className="flex items-center gap-2"><span className="num w-8 text-xs">{p.promotion_sensitivity.toFixed(2)}</span><div className="w-24">{bar(p.promotion_sensitivity)}</div></div></td></tr>)}</tbody></table></div>
      <p className="text-xs text-muted-foreground">Sensitivity runs from 0 (indifferent to price) to 1 (extremely sensitive). These are the AI's proposals: if a value looks wrong, change the brief and design again.</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-muted-foreground">Pack<select value={pack} onChange={(e) => { setPack(e.target.value); reset() }} className="mt-1 block rounded-md border bg-background p-2 text-sm text-foreground">{PACKS.map((p) => <option key={p} value={p}>{packLabel(p)}</option>)}</select></label>
        <button type="button" disabled={!!busy} onClick={() => void run("report", () => personaReport(mix, pack), (r) => { setReport(r); setVoices(undefined); setCandidates(undefined); const first = Object.keys(r.personas.find((p) => p.acceptance_by_price)?.acceptance_by_price ?? {}); if (first.length) setPrice(first[Math.floor(first.length / 2)]) })} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy === "report" ? "Generating…" : "Generate synthetic respondents"}</button>
      </div>
    </section>}

    {report && mix && <section className="space-y-4">
      <h3 className="font-display text-lg font-semibold">Who accepts which price</h3>
      <p className="text-xs text-muted-foreground">{report.sample_size} synthetic respondents, data {report.data_hash.slice(0, 10)}. Share of each persona's respondents who would still buy the {packLabel(report.pack)} at each price.</p>
      <div className="grid gap-4 md:grid-cols-2">{report.personas.map((p) => <article key={p.name} className="rounded-lg border bg-card p-4">
        <h4 className="font-medium">{p.name} <span className="text-xs font-normal text-muted-foreground">{p.respondents} respondents</span></h4>
        {p.acceptance_by_price ? <div className="mt-2 space-y-1.5">{Object.entries(p.acceptance_by_price).map(([at, share]) => <div key={at} className="grid grid-cols-[4rem_1fr_3rem] items-center gap-3 text-xs">
          <span className="num">{inr(Number(at))}</span>{bar(share)}<span className="num text-right">{(share * 100).toFixed(0)}%</span></div>)}</div>
          : <p className="mt-2 text-xs text-muted-foreground">Too few respondents buy this pack to draw a curve.</p>}
      </article>)}</div>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4">
        <button type="button" disabled={!!busy} onClick={() => void run("candidates", () => personaCandidates(mix, "Gabor-Granger", pack), setCandidates)} className="rounded-md border px-3 py-2 text-sm font-medium hover:bg-secondary disabled:opacity-50">{busy === "candidates" ? "Running engine…" : "Turn into candidate prices"}</button>
        <span className="text-xs text-muted-foreground">Candidates go through the support check and the engine like any other option.</span>
      </div>
      {candidates && <CandidateTable rows={candidates.scenarios} baseline={baseline} onAdd={onAdd} />}

      <div className="space-y-3 rounded-lg border border-dashed bg-card p-4">
        <div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-lg font-semibold">Hear their reactions</h3>
</div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-muted-foreground">Price to test (₹)<input type="number" min={1} step={0.5} list="persona-prices" value={price} onChange={(e) => { setPrice(e.target.value); setVoices(undefined) }} className="mt-1 block w-32 rounded-md border bg-background p-2 text-sm text-foreground" />
            <datalist id="persona-prices">{prices.map((g) => <option key={g} value={Number(g)} />)}</datalist></label>
          <button type="button" disabled={!!busy || !(Number(price) > 0)} onClick={() => void run("voices", () => personaVoices(mix, pack, Number(price)), setVoices)} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy === "voices" ? "Listening…" : "Voice the personas"}</button>
        </div>
        {voices && <div className="space-y-3">{voices.voices.map((v) => <blockquote key={v.persona} className="rounded-md border-l-4 border-edge/60 bg-secondary/40 p-3 text-sm">
          <p className="font-medium">{v.persona}</p><p className="mt-1">“{v.quote}”</p>
          {v.objections.length > 0 && <ul className="mt-2 list-disc pl-5 text-xs text-muted-foreground">{v.objections.map((o) => <li key={o}>{o}</li>)}</ul>}
          {v.would_change_mind && <p className="mt-2 text-xs"><strong>Would change their mind:</strong> {v.would_change_mind}</p>}</blockquote>)}
          <p className="text-xs text-muted-foreground">Written by {voices.model_id} from the figures above. Any number in a quote was checked against those figures. It is wording, not research.</p></div>}
      </div>
    </section>}
  </div>
}
