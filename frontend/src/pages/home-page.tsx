import { useCallback, useEffect, useState } from "react"
import type { FormEvent } from "react"
import { Link, useNavigate, useOutletContext } from "react-router-dom"
import { evaluateScenarios, getSituation, listMarkets } from "@/lib/api"
import type { MarketInfo } from "@/lib/api"
import { PACKS, signed, signedRupees } from "@/lib/catalog"
import { asCurrency, INR } from "@/lib/currency"
import { createWorkspace, getHubSummary, getWorkspaceScenarios, listWorkspaces, updateWorkspace } from "@/lib/workspaces"
import type { HubSummary, WorkspaceMeta } from "@/lib/workspaces"
import type { AppOutletContext } from "@/layout/app-layout"
import { canEdit, useRole } from "@/lib/user-context"
import { pickBest, toUiResults } from "@/workspace/helpers"
import { DEFAULT_INPUT, TEMPLATES } from "@/workspace/templates"
import type { TemplateInput } from "@/workspace/templates"

const GUARDRAIL_PCT = 5

type Starter = {
  id: string
  label: string
  hint: string
  marketId: string
  templateId: string
  input: TemplateInput
}

/** One-click examples that teach the product by starting a real case. */
const STARTERS: Starter[] = [
  { id: "costs8", label: "Costs +8%", hint: "Protect GP when inputs rise", marketId: "in", templateId: "costs", input: { pack: "bottle_1500ml", costPct: 8 } },
  { id: "price-can", label: "Take price on can", hint: "Test +2% to +5% on 330 ml", marketId: "in", templateId: "price", input: { pack: "can_330ml", costPct: 8 } },
  { id: "promo-15", label: "Promo on 1.5 L", hint: "Is 10–40% TPR worth it?", marketId: "in", templateId: "promo", input: { pack: "bottle_1500ml", costPct: 8 } },
  { id: "mix", label: "Bigger packs", hint: "Steer volume to 1.5 L / 6-pack", marketId: "in", templateId: "mix", input: DEFAULT_INPUT },
  { id: "us-tour", label: "US market tour", hint: "Same decisions in USD", marketId: "us", templateId: "example", input: DEFAULT_INPUT },
]

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return "just now"
  const units: Array<[number, string]> = [[86400, "day"], [3600, "hour"], [60, "minute"]]
  for (const [size, label] of units) {
    if (seconds >= size) { const n = Math.floor(seconds / size); return `${n} ${label}${n === 1 ? "" : "s"} ago` }
  }
  return "just now"
}
const firstName = (displayName: string) => displayName.split(" ")[0] || displayName

type Headline = { kind: "loading" } | { kind: "none" } | { kind: "best"; name: string; marginPct: number; gpChange: number } | { kind: "error" }
const headlineCache = new Map<string, Headline>()

/** Evaluates a workspace's saved scenarios with the engine and names its best move. Numbers come only from the engine. */
function useHeadline(workspace: WorkspaceMeta): Headline {
  const key = workspace.id + ":" + workspace.updated_at
  const [state, setState] = useState<{ key: string; headline: Headline }>({ key, headline: headlineCache.get(key) ?? { kind: "loading" } })
  useEffect(() => {
    if (headlineCache.has(key)) return
    let active = true
    ;(async () => {
      let headline: Headline
      try {
        const saved = await getWorkspaceScenarios(workspace.id)
        const scenarios = saved.scenarios && saved.scenarios.length > 1 ? saved.scenarios : null
        if (!scenarios) headline = { kind: "none" }
        else {
          const marketId = workspace.market_id || "in"
          const baseline = (await getSituation(marketId)).totals.focal
          const best = pickBest(toUiResults(await evaluateScenarios(scenarios, 0, 42, undefined, marketId), scenarios, baseline), GUARDRAIL_PCT)
          headline = best?.delta && best.abs && best.abs.gpChange > 0 ? { kind: "best", name: best.name, marginPct: best.delta.marginPct, gpChange: best.abs.gpChange } : { kind: "none" }
        }
      } catch {
        headline = { kind: "error" }
      }
      headlineCache.set(key, headline)
      if (active) setState({ key, headline })
    })()
    return () => { active = false }
  }, [key, workspace.id, workspace.market_id])
  return state.key === key ? state.headline : headlineCache.get(key) ?? { kind: "loading" }
}

function MarketBadge({ code, symbol }: { code?: string; symbol?: string }) {
  const label = code ?? "INR"
  return <span className="inline-flex items-center gap-1 rounded-md border bg-secondary/80 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-secondary-foreground">
    <span className="num opacity-80">{symbol ?? ""}</span>{label}
  </span>
}

function WorkspaceCard({ workspace, onChanged }: { workspace: WorkspaceMeta; onChanged: () => void }) {
  const headline = useHeadline(workspace)
  const editor = canEdit(useRole())
  const edited = new Date(workspace.updated_at).getTime() - new Date(workspace.created_at).getTime() > 2000
  const [confirming, setConfirming] = useState(false)
  const [failed, setFailed] = useState(false)
  async function setArchived(archived: boolean) {
    setFailed(false)
    try { await updateWorkspace(workspace.id, { archived }); setConfirming(false); onChanged() } catch { setFailed(true) }
  }
  return (
    <li className={`group flex flex-col rounded-2xl border bg-card p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md ${workspace.archived ? "opacity-70" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-lg font-semibold leading-tight tracking-tight">{workspace.name}</h3>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
          <MarketBadge code={workspace.currency?.code} symbol={workspace.currency?.symbol} />
          {workspace.archived && <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">Archived</span>}
        </div>
      </div>
      {workspace.description && <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-muted-foreground" title={workspace.description}>{workspace.description}</p>}
      <div className="mt-4 min-h-[3.25rem]">
        {headline.kind === "loading" && <p className="text-sm text-muted-foreground">Evaluating…</p>}
        {headline.kind === "none" && <p className="text-sm text-muted-foreground">{workspace.scenario_count > 1 ? `No option beats baseline within a ${GUARDRAIL_PCT}% volume guardrail yet` : "Add options to compare them with the baseline"}</p>}
        {headline.kind === "error" && <p className="text-sm text-muted-foreground">Results unavailable</p>}
        {headline.kind === "best" && <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Best weekly gross profit</p>
          <p className="mt-0.5"><span className="num text-2xl font-bold tracking-tight text-gain">{signedRupees(headline.gpChange, asCurrency(workspace.currency ?? INR))}</span>
            <span className="ml-2 text-sm text-muted-foreground">({signed(headline.marginPct)}) · {headline.name}</span></p>
        </div>}
      </div>
      <p className="mt-auto pt-4 text-xs text-muted-foreground">{workspace.scenario_count} option{workspace.scenario_count === 1 ? "" : "s"} · {edited ? `edited ${timeAgo(workspace.updated_at)} by ${workspace.updated_by}` : `created ${timeAgo(workspace.created_at)} by ${workspace.created_by}`}</p>
      <div className="mt-3 flex items-center gap-2 border-t pt-3">
        {!workspace.archived && <Link to={editor ? `/w/${workspace.id}` : `/w/${workspace.id}/executive`} className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition hover:brightness-110">{editor ? "Open" : "Open brief"}</Link>}
        {editor && (workspace.archived
          ? <button type="button" onClick={() => void setArchived(false)} className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-secondary">Restore</button>
          : confirming
            ? <><span className="text-xs text-muted-foreground">Archive this case?</span>
              <button type="button" onClick={() => void setArchived(true)} className="rounded px-2 py-1 text-xs font-medium text-loss hover:bg-loss/10">Archive</button>
              <button type="button" onClick={() => setConfirming(false)} className="rounded px-2 py-1 text-xs hover:bg-secondary">Cancel</button></>
            : <button type="button" onClick={() => setConfirming(true)} className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground">Archive</button>)}
        {failed && <span role="alert" className="text-xs text-loss">Could not update</span>}
      </div>
    </li>
  )
}

function StepDot({ n, label, active, done }: { n: number; label: string; active: boolean; done: boolean }) {
  return <div className={`flex items-center gap-2 text-sm ${active ? "font-semibold text-foreground" : done ? "text-foreground/70" : "text-muted-foreground"}`}>
    <span className={`flex size-7 items-center justify-center rounded-full text-xs ${active ? "bg-ink text-white" : done ? "bg-primary/15 text-primary" : "border bg-card"}`}>{done && !active ? "✓" : n}</span>
    <span className="hidden sm:inline">{label}</span>
  </div>
}

function NewWorkspaceForm({
  onCancel, markets, initial,
}: {
  onCancel?: () => void
  markets: MarketInfo[]
  initial?: Partial<{ marketId: string; templateId: string; input: TemplateInput }>
}) {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [templateId, setTemplateId] = useState(initial?.templateId ?? "example")
  const [marketId, setMarketId] = useState(initial?.marketId ?? "in")
  const [input, setInput] = useState<TemplateInput>(initial?.input ?? DEFAULT_INPUT)
  const [nameOverride, setNameOverride] = useState<string>()
  const [descriptionOverride, setDescriptionOverride] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const template = TEMPLATES.find((t) => t.id === templateId) ?? TEMPLATES[0]
  const name = nameOverride ?? template.name(input)
  const description = descriptionOverride ?? template.question(input)
  const costValid = Number.isFinite(input.costPct) && input.costPct >= 1 && input.costPct <= 50
  const optionCount = template.build(input).length
  const marketList = markets.length ? markets : [{ id: "in", label: "India", currency: INR }]

  useEffect(() => {
    if (!initial) return
    if (initial.marketId) setMarketId(initial.marketId)
    if (initial.templateId) setTemplateId(initial.templateId)
    if (initial.input) setInput(initial.input)
    setNameOverride(undefined)
    setDescriptionOverride(undefined)
    setStep(0)
  }, [initial])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (step < 2) { setStep(step + 1); return }
    if (!name.trim()) { setError("Give the case a name"); return }
    if (template.needs.includes("cost") && !costValid) { setError("Enter a cost increase between 1% and 50%"); return }
    setBusy(true); setError(undefined)
    try {
      const created = await createWorkspace({ name: name.trim(), description: description.trim(), market_id: marketId, scenarios: template.build(input) })
      navigate(`/w/${created.id}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the case")
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5 overflow-hidden rounded-2xl border bg-card shadow-sm" aria-label="New case">
      <div className="border-b bg-[linear-gradient(135deg,color-mix(in_oklab,var(--ink)_6%,white),color-mix(in_oklab,var(--primary)_8%,white))] px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-display text-xl font-semibold tracking-tight">New case</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">One pricing question, locked to a market. The engine calculates every figure.</p>
          </div>
          {onCancel && <button type="button" onClick={onCancel} className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground">Close</button>}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-4" aria-label="Creation steps">
          <StepDot n={1} label="Market" active={step === 0} done={step > 0} />
          <span className="hidden h-px w-6 bg-border sm:block" aria-hidden />
          <StepDot n={2} label="Decision" active={step === 1} done={step > 1} />
          <span className="hidden h-px w-6 bg-border sm:block" aria-hidden />
          <StepDot n={3} label="Details" active={step === 2} done={false} />
        </div>
      </div>

      <div className="space-y-4 px-5 pb-5">
        {step === 0 && <fieldset className="space-y-2 text-sm"><legend className="font-medium">Which market?</legend>
          <p className="text-xs text-muted-foreground">Synthetic data for that market — not live FX of one India dataset. Locked after create.</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {marketList.map((m) => (
              <label key={m.id} className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 transition hover:bg-secondary/60 ${m.id === marketId ? "border-primary bg-primary/5 ring-1 ring-primary" : ""}`}>
                <input type="radio" name="market" value={m.id} checked={m.id === marketId} onChange={() => setMarketId(m.id)} className="mt-1" />
                <span><span className="font-medium">{m.label}</span><span className="mt-0.5 block text-muted-foreground">{m.currency.code} ({m.currency.symbol})</span></span>
              </label>
            ))}
          </div>
        </fieldset>}

        {step === 1 && <fieldset className="space-y-2 text-sm"><legend className="font-medium">What do you want to decide?</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {TEMPLATES.map((t) => (
              <label key={t.id} className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 transition hover:bg-secondary/60 ${t.id === templateId ? "border-primary bg-primary/5 ring-1 ring-primary" : ""}`}>
                <input type="radio" name="template" value={t.id} checked={t.id === templateId} onChange={() => setTemplateId(t.id)} className="mt-1" />
                <span><span className="font-medium">{t.title}</span><span className="mt-0.5 block text-muted-foreground">{t.blurb}</span></span>
              </label>
            ))}
          </div>
          {template.needs.length > 0 && <div className="flex flex-wrap gap-4 rounded-xl border bg-secondary/30 p-3">
            {template.needs.includes("pack") && <label className="font-medium">Pack
              <select aria-label="Pack" value={input.pack} onChange={(e) => setInput({ ...input, pack: e.target.value })} className="mt-1 block rounded-md border bg-background px-3 py-2 font-normal">
                {PACKS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select></label>}
            {template.needs.includes("cost") && <label className="font-medium">Input cost increase (%)
              <input type="number" min={1} max={50} step={1} value={Number.isFinite(input.costPct) ? input.costPct : ""} onChange={(e) => setInput({ ...input, costPct: e.target.valueAsNumber })} className="mt-1 block w-28 rounded-md border bg-background px-3 py-2 font-normal" />
              <span className="mt-1 block text-xs font-normal text-muted-foreground">Aluminium, PET and sugar</span></label>}
          </div>}
        </fieldset>}

        {step === 2 && <>
          <div className="rounded-xl border bg-secondary/25 px-4 py-3 text-sm">
            <p className="font-medium">Ready to create</p>
            <p className="mt-1 text-muted-foreground">{marketList.find((m) => m.id === marketId)?.label ?? marketId} · {template.title} · starts with <span className="num font-semibold text-foreground">{optionCount}</span> option{optionCount === 1 ? "" : "s"}
              {optionCount > 1 && " (includes a loser and a refused extreme where the template provides them)"}.</p>
          </div>
          <label className="block text-sm font-medium">Name
            <input value={name} onChange={(e) => setNameOverride(e.target.value)} maxLength={120} placeholder="e.g. Input cost response, Q3" className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm font-normal" /></label>
          <label className="block text-sm font-medium">Business question <span className="font-normal text-muted-foreground">(what are you trying to decide?)</span>
            <textarea value={description} onChange={(e) => setDescriptionOverride(e.target.value)} maxLength={500} rows={3} placeholder="e.g. Input costs are up 8%. Which moves protect gross profit?" className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm font-normal" /></label>
        </>}

        {error && <p role="alert" className="text-sm text-loss">{error}</p>}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {step > 0 && <button type="button" onClick={() => setStep(step - 1)} className="rounded-md border px-3 py-2 text-sm font-medium hover:bg-secondary">Back</button>}
          <button type="submit" disabled={busy} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:brightness-110 disabled:opacity-60">
            {busy ? "Creating…" : step < 2 ? "Continue" : "Create case"}
          </button>
        </div>
      </div>
    </form>
  )
}

export function HomePage() {
  const { user } = useOutletContext<AppOutletContext>()
  const [workspaces, setWorkspaces] = useState<WorkspaceMeta[]>()
  const [summary, setSummary] = useState<HubSummary>()
  const [markets, setMarkets] = useState<MarketInfo[]>([])
  const [showArchived, setShowArchived] = useState(false)
  const [creating, setCreating] = useState(false)
  const [starter, setStarter] = useState<Partial<{ marketId: string; templateId: string; input: TemplateInput }> | undefined>()
  const [error, setError] = useState<string>()

  const load = useCallback(() => {
    listWorkspaces(showArchived).then(setWorkspaces).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Could not load cases"))
    getHubSummary().then(setSummary).catch(() => undefined)
  }, [showArchived])
  useEffect(() => { load() }, [load])
  useEffect(() => { listMarkets().then(setMarkets).catch(() => setMarkets([{ id: "in", label: "India", currency: INR }])) }, [])

  const empty = workspaces !== undefined && workspaces.length === 0 && !showArchived
  const editor = canEdit(user.role)
  const openForm = creating || empty

  function beginStarter(s: Starter) {
    setStarter({ marketId: s.marketId, templateId: s.templateId, input: s.input })
    setCreating(true)
  }

  return (
    <main className="mx-auto w-full max-w-[1200px] flex-1 space-y-8 px-5 py-8 md:px-8">
      <section className="relative overflow-hidden rounded-2xl border bg-card px-6 py-7 shadow-sm md:px-8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(900px_280px_at_10%_-20%,color-mix(in_oklab,var(--primary)_18%,transparent),transparent_60%),radial-gradient(700px_240px_at_90%_0%,color-mix(in_oklab,var(--ink)_10%,transparent),transparent_55%)]" aria-hidden />
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-wider text-primary">Revenue growth simulator</p>
            <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight md:text-4xl">Welcome back, {firstName(user.display_name)}</h1>
            <p className="mt-2 text-muted-foreground">{editor
              ? "Each case is one pricing question on Aurora. Start from an example, compare options the engine scores, then brief the room."
              : "Open a case to read its decision brief: recommendation, options considered, and what we refused to estimate."}</p>
          </div>
          {editor && !openForm && <button type="button" onClick={() => { setStarter(undefined); setCreating(true) }} className="rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-sm hover:brightness-110">New case</button>}
        </div>
        {editor && !openForm && <div className="relative mt-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Try an example</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {STARTERS.map((s) => (
              <button key={s.id} type="button" title={s.hint} onClick={() => beginStarter(s)}
                className="rounded-full border bg-background/80 px-3 py-1.5 text-sm font-medium transition hover:border-primary/40 hover:bg-primary/5">
                {s.label}
              </button>
            ))}
          </div>
        </div>}
      </section>

      {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
      {editor && openForm && <div className="max-w-3xl space-y-3">
        {empty && <div className="flex flex-wrap gap-2">
          {STARTERS.map((s) => (
            <button key={s.id} type="button" title={s.hint} onClick={() => beginStarter(s)}
              className="rounded-full border bg-card px-3 py-1.5 text-sm font-medium hover:border-primary/40 hover:bg-primary/5">{s.label}</button>
          ))}
        </div>}
        <NewWorkspaceForm markets={markets} initial={starter} onCancel={empty ? undefined : () => { setCreating(false); setStarter(undefined) }} />
      </div>}

      <section aria-label="Cases" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold tracking-tight">Cases</h2>
          {summary && summary.workspaces.archived > 0 && <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />Show archived ({summary.workspaces.archived})</label>}
        </div>
        {workspaces === undefined && !error && <p className="text-sm text-muted-foreground" role="status">Loading cases…</p>}
        {empty && <p className="text-sm text-muted-foreground">{editor ? "No cases yet. Pick an example above or create your first case." : "No cases have been shared yet. An analyst creates them; they will appear here."}</p>}
        {workspaces && workspaces.length > 0 && <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {workspaces.map((workspace) => <WorkspaceCard key={workspace.id + workspace.updated_at + workspace.archived} workspace={workspace} onChanged={load} />)}
        </ul>}
      </section>
    </main>
  )
}
