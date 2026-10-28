import { useCallback, useEffect, useState } from "react"
import type { FormEvent } from "react"
import { Link, useNavigate, useOutletContext } from "react-router-dom"
import { evaluateScenarios, getSituation } from "@/lib/api"
import type { Situation } from "@/lib/api"
import { PACKS, signed, signedRupees } from "@/lib/catalog"
import { createWorkspace, getHubSummary, getWorkspaceScenarios, listWorkspaces, updateWorkspace } from "@/lib/workspaces"
import type { HubSummary, WorkspaceMeta } from "@/lib/workspaces"
import type { AppOutletContext } from "@/layout/app-layout"
import { canEdit, useRole } from "@/lib/user-context"
import { pickBest, toUiResults } from "@/workspace/helpers"
import { DEFAULT_INPUT, TEMPLATES } from "@/workspace/templates"
import type { TemplateInput } from "@/workspace/templates"

const GUARDRAIL_PCT = 5

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
// The engine's own baseline is the same for every case, so it is fetched once.
let situationOnce: Promise<Situation> | undefined
const baselineOnce = () => (situationOnce ??= getSituation().catch((cause: unknown) => { situationOnce = undefined; throw cause }))

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
          const baseline = (await baselineOnce()).totals.focal
          const best = pickBest(toUiResults(await evaluateScenarios(scenarios, 0, 42), scenarios, baseline), GUARDRAIL_PCT)
          // Only a real improvement is a headline; "best of a bad lot" is not.
          headline = best?.delta && best.abs && best.abs.gpChange > 0 ? { kind: "best", name: best.name, marginPct: best.delta.marginPct, gpChange: best.abs.gpChange } : { kind: "none" }
        }
      } catch {
        headline = { kind: "error" }
      }
      headlineCache.set(key, headline)
      if (active) setState({ key, headline })
    })()
    return () => { active = false }
  }, [key, workspace.id])
  return state.key === key ? state.headline : headlineCache.get(key) ?? { kind: "loading" }
}

function WorkspaceCard({ workspace, onChanged }: { workspace: WorkspaceMeta; onChanged: () => void }) {
  const headline = useHeadline(workspace)
  const editor = canEdit(useRole())
  // A workspace nobody has changed since it was created says "created", not "edited".
  const edited = new Date(workspace.updated_at).getTime() - new Date(workspace.created_at).getTime() > 2000
  const [confirming, setConfirming] = useState(false)
  const [failed, setFailed] = useState(false)
  async function setArchived(archived: boolean) {
    setFailed(false)
    try { await updateWorkspace(workspace.id, { archived }); setConfirming(false); onChanged() } catch { setFailed(true) }
  }
  return (
    <li className={`flex flex-col rounded-xl border bg-card p-5 ${workspace.archived ? "opacity-70" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-lg font-semibold leading-tight">{workspace.name}</h3>
        {workspace.archived && <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">Archived</span>}
      </div>
      {workspace.description && <p className="mt-1 line-clamp-3 text-sm text-muted-foreground" title={workspace.description}>{workspace.description}</p>}
      <p className="mt-3 text-sm">
        {headline.kind === "loading" && <span className="text-muted-foreground">Evaluating…</span>}
        {headline.kind === "none" && <span className="text-muted-foreground">{workspace.scenario_count > 1 ? `No option beats the baseline within a ${GUARDRAIL_PCT}% volume guardrail yet` : "Add options to compare them with the baseline"}</span>}
        {headline.kind === "error" && <span className="text-muted-foreground">Results unavailable</span>}
        {headline.kind === "best" && <><span className="num text-xl font-bold text-gain">{signedRupees(headline.gpChange)}</span> <span className="text-muted-foreground">a week ({signed(headline.marginPct)}) gross profit, {headline.name}</span></>}
      </p>
      <p className="mt-auto pt-4 text-xs text-muted-foreground">{workspace.scenario_count} option{workspace.scenario_count === 1 ? "" : "s"} · {edited ? `edited ${timeAgo(workspace.updated_at)} by ${workspace.updated_by}` : `created ${timeAgo(workspace.created_at)} by ${workspace.created_by}`}</p>
      <div className="mt-3 flex items-center gap-2">
        {!workspace.archived && <Link to={editor ? `/w/${workspace.id}` : `/w/${workspace.id}/executive`} className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:brightness-110">{editor ? "Open" : "Open brief"}</Link>}
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

function NewWorkspaceForm({ onCancel }: { onCancel?: () => void }) {
  const navigate = useNavigate()
  const [templateId, setTemplateId] = useState("example")
  const [input, setInput] = useState<TemplateInput>(DEFAULT_INPUT)
  // Name and question follow the chosen template until the user types their own.
  const [nameOverride, setNameOverride] = useState<string>()
  const [descriptionOverride, setDescriptionOverride] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const template = TEMPLATES.find((t) => t.id === templateId) ?? TEMPLATES[0]
  const name = nameOverride ?? template.name(input)
  const description = descriptionOverride ?? template.question(input)
  const costValid = Number.isFinite(input.costPct) && input.costPct >= 1 && input.costPct <= 50
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) { setError("Give the case a name"); return }
    if (template.needs.includes("cost") && !costValid) { setError("Enter a cost increase between 1% and 50%"); return }
    setBusy(true); setError(undefined)
    try {
      const created = await createWorkspace({ name: name.trim(), description: description.trim(), scenarios: template.build(input) })
      navigate(`/w/${created.id}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the case")
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border bg-card p-5" aria-label="New case">
      <h2 className="font-display text-lg font-semibold">New case</h2>
      <fieldset className="space-y-2 text-sm"><legend className="font-medium">What do you want to decide?</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {TEMPLATES.map((t) => (
            <label key={t.id} className={`flex cursor-pointer items-start gap-2 rounded-lg border p-3 hover:bg-secondary/60 ${t.id === templateId ? "border-primary ring-1 ring-primary" : ""}`}>
              <input type="radio" name="template" value={t.id} checked={t.id === templateId} onChange={() => setTemplateId(t.id)} className="mt-1" />
              <span><span className="font-medium">{t.title}</span><span className="block text-muted-foreground">{t.blurb}</span></span>
            </label>
          ))}
        </div>
      </fieldset>
      {template.needs.length > 0 && <div className="flex flex-wrap gap-4 text-sm">
        {template.needs.includes("pack") && <label className="font-medium">Pack
          <select aria-label="Pack" value={input.pack} onChange={(e) => setInput({ ...input, pack: e.target.value })} className="mt-1 block rounded-md border bg-background px-3 py-2 font-normal">
            {PACKS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select></label>}
        {template.needs.includes("cost") && <label className="font-medium">Input cost increase (%)
          <input type="number" min={1} max={50} step={1} value={Number.isFinite(input.costPct) ? input.costPct : ""} onChange={(e) => setInput({ ...input, costPct: e.target.valueAsNumber })} className="mt-1 block w-28 rounded-md border bg-background px-3 py-2 font-normal" />
          <span className="mt-1 block text-xs font-normal text-muted-foreground">Applied to aluminium, PET and sugar</span></label>}
      </div>}
      {template.build(DEFAULT_INPUT).length > 1 && <p className="text-xs text-muted-foreground">Starts with {template.build(DEFAULT_INPUT).length} options, including one that loses profit and one outside our data that the engine refuses. You can change them all.</p>}
      <label className="block text-sm font-medium">Name
        <input value={name} onChange={(e) => setNameOverride(e.target.value)} maxLength={120} placeholder="e.g. Input cost response, Q3" className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm font-normal" /></label>
      <label className="block text-sm font-medium">Business question <span className="font-normal text-muted-foreground">(what are you trying to decide?)</span>
        <textarea value={description} onChange={(e) => setDescriptionOverride(e.target.value)} maxLength={500} rows={3} placeholder="e.g. Input costs are up 8%. Which price, pack and promotion moves protect gross profit without losing more than 5% volume?" className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm font-normal" /></label>
      {error && <p role="alert" className="text-sm text-loss">{error}</p>}
      <div className="flex items-center gap-2">
        <button type="submit" disabled={busy} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:brightness-110 disabled:opacity-60">{busy ? "Creating…" : "Create case"}</button>
        {onCancel && <button type="button" onClick={onCancel} className="rounded-md px-3 py-2 text-sm hover:bg-secondary">Cancel</button>}
      </div>
    </form>
  )
}

export function HomePage() {
  const { user } = useOutletContext<AppOutletContext>()
  const [workspaces, setWorkspaces] = useState<WorkspaceMeta[]>()
  const [summary, setSummary] = useState<HubSummary>()
  const [showArchived, setShowArchived] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string>()

  const load = useCallback(() => {
    listWorkspaces(showArchived).then(setWorkspaces).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Could not load cases"))
    getHubSummary().then(setSummary).catch(() => undefined)
  }, [showArchived])
  useEffect(() => { load() }, [load])

  const empty = workspaces !== undefined && workspaces.length === 0 && !showArchived
  const editor = canEdit(user.role)
  return (
    <main className="mx-auto w-full max-w-[1200px] flex-1 space-y-8 px-5 py-8 md:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold">Welcome back, {firstName(user.display_name)}</h1>
          <p className="mt-1 max-w-3xl text-muted-foreground">{editor
            ? "Each case is one pricing question about the Aurora brand. Open one to see where the brand stands, build and compare options, and get a recommendation. The assistant plans and explains; every number is calculated by the deterministic engine and checked by an auditor."
            : "Each case is one pricing question about the Aurora brand. Open a case to read its decision brief: the recommendation, the options considered and what we refused to estimate."}</p>
        </div>
        {editor && !creating && !empty && <button type="button" onClick={() => setCreating(true)} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:brightness-110">New case</button>}
      </div>

      {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
      {editor && (creating || empty) && <div className="max-w-3xl"><NewWorkspaceForm onCancel={empty ? undefined : () => setCreating(false)} /></div>}

      <section aria-label="Cases" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold">Cases</h2>
          {summary && summary.workspaces.archived > 0 && <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />Show archived ({summary.workspaces.archived})</label>}
        </div>
        {workspaces === undefined && !error && <p className="text-sm text-muted-foreground" role="status">Loading cases…</p>}
        {empty && <p className="text-sm text-muted-foreground">{editor ? "No cases yet. Create your first one above." : "No cases have been shared yet. An analyst creates them; they will appear here."}</p>}
        {workspaces && workspaces.length > 0 && <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {workspaces.map((workspace) => <WorkspaceCard key={workspace.id + workspace.updated_at + workspace.archived} workspace={workspace} onChanged={load} />)}
        </ul>}
      </section>

    </main>
  )
}
