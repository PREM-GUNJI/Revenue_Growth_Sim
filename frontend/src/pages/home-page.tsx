import { useCallback, useEffect, useState } from "react"
import type { FormEvent } from "react"
import { Link, useNavigate, useOutletContext } from "react-router-dom"
import { evaluateScenarios } from "@/lib/api"
import { signed } from "@/lib/catalog"
import { newScenario } from "@/lib/catalog"
import { createWorkspace, getHubSummary, getWorkspaceScenarios, listWorkspaces, updateWorkspace } from "@/lib/workspaces"
import type { HubSummary, WorkspaceMeta } from "@/lib/workspaces"
import type { AppOutletContext } from "@/layout/app-layout"
import { initialScenarios, pickBest, toUiResults } from "@/workspace/helpers"

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

type Headline = { kind: "loading" } | { kind: "none" } | { kind: "best"; name: string; marginPct: number } | { kind: "error" }
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
          const best = pickBest(toUiResults(await evaluateScenarios(scenarios, 0, 42), scenarios), GUARDRAIL_PCT)
          headline = best?.delta ? { kind: "best", name: best.name, marginPct: best.delta.marginPct } : { kind: "none" }
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
      {workspace.description && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{workspace.description}</p>}
      <p className="mt-3 text-sm">
        {headline.kind === "loading" && <span className="text-muted-foreground">Evaluating…</span>}
        {headline.kind === "none" && <span className="text-muted-foreground">{workspace.scenario_count > 1 ? `No scenario within the ${GUARDRAIL_PCT}% volume guardrail` : "Add scenarios to compare them with the baseline"}</span>}
        {headline.kind === "error" && <span className="text-muted-foreground">Results unavailable</span>}
        {headline.kind === "best" && <><span className="num text-xl font-bold text-gain">{signed(headline.marginPct)}</span> <span className="text-muted-foreground">gross profit, {headline.name}</span></>}
      </p>
      <p className="mt-auto pt-4 text-xs text-muted-foreground">{workspace.scenario_count} scenario{workspace.scenario_count === 1 ? "" : "s"} · {edited ? `edited ${timeAgo(workspace.updated_at)} by ${workspace.updated_by}` : `created ${timeAgo(workspace.created_at)} by ${workspace.created_by}`}</p>
      <div className="mt-3 flex items-center gap-2">
        {!workspace.archived && <Link to={`/w/${workspace.id}`} className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:brightness-110">Open</Link>}
        {workspace.archived
          ? <button type="button" onClick={() => void setArchived(false)} className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-secondary">Restore</button>
          : confirming
            ? <><span className="text-xs text-muted-foreground">Archive this workspace?</span>
              <button type="button" onClick={() => void setArchived(true)} className="rounded px-2 py-1 text-xs font-medium text-loss hover:bg-loss/10">Archive</button>
              <button type="button" onClick={() => setConfirming(false)} className="rounded px-2 py-1 text-xs hover:bg-secondary">Cancel</button></>
            : <button type="button" onClick={() => setConfirming(true)} className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground">Archive</button>}
        {failed && <span role="alert" className="text-xs text-loss">Could not update</span>}
      </div>
    </li>
  )
}

function NewWorkspaceForm({ onCancel }: { onCancel?: () => void }) {
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [starter, setStarter] = useState<"blank" | "demo">("demo")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) { setError("Give the workspace a name"); return }
    setBusy(true); setError(undefined)
    try {
      const created = await createWorkspace({ name: name.trim(), description: description.trim(), scenarios: starter === "demo" ? initialScenarios : [newScenario("Baseline")] })
      navigate(`/w/${created.id}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the workspace")
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border bg-card p-5" aria-label="New workspace">
      <h2 className="font-display text-lg font-semibold">New workspace</h2>
      <label className="block text-sm font-medium">Name
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="e.g. Q3 pack-price review" className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm font-normal" /></label>
      <label className="block text-sm font-medium">Description <span className="font-normal text-muted-foreground">(optional)</span>
        <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm font-normal" /></label>
      <fieldset className="space-y-2 text-sm"><legend className="font-medium">Start from</legend>
        <label className="flex items-start gap-2"><input type="radio" name="starter" checked={starter === "demo"} onChange={() => setStarter("demo")} className="mt-1" /><span>Demo scenarios <span className="text-muted-foreground">(baseline, +4% price, promotion, price defense and one out-of-range request)</span></span></label>
        <label className="flex items-start gap-2"><input type="radio" name="starter" checked={starter === "blank"} onChange={() => setStarter("blank")} className="mt-1" /><span>Blank <span className="text-muted-foreground">(baseline only)</span></span></label>
      </fieldset>
      {error && <p role="alert" className="text-sm text-loss">{error}</p>}
      <div className="flex items-center gap-2">
        <button type="submit" disabled={busy} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:brightness-110 disabled:opacity-60">{busy ? "Creating…" : "Create workspace"}</button>
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
    listWorkspaces(showArchived).then(setWorkspaces).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Could not load workspaces"))
    getHubSummary().then(setSummary).catch(() => undefined)
  }, [showArchived])
  useEffect(() => { load() }, [load])

  const empty = workspaces !== undefined && workspaces.length === 0 && !showArchived
  return (
    <main className="mx-auto w-full max-w-[1200px] flex-1 space-y-8 px-5 py-8 md:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold">Welcome back, {firstName(user.display_name)}</h1>
          <p className="mt-1 text-muted-foreground">Open a workspace and ask the AI decision assistant, or set the levers yourself. The assistant plans and explains; every number is calculated by the deterministic engine and checked by an auditor.</p>
        </div>
        {!creating && !empty && <button type="button" onClick={() => setCreating(true)} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:brightness-110">New workspace</button>}
      </div>

      {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
      {(creating || empty) && <div className="max-w-xl"><NewWorkspaceForm onCancel={empty ? undefined : () => setCreating(false)} /></div>}

      <section aria-label="Workspaces" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold">Workspaces</h2>
          {summary && summary.workspaces.archived > 0 && <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />Show archived ({summary.workspaces.archived})</label>}
        </div>
        {workspaces === undefined && !error && <p className="text-sm text-muted-foreground" role="status">Loading workspaces…</p>}
        {empty && <p className="text-sm text-muted-foreground">No workspaces yet. Create your first one above.</p>}
        {workspaces && workspaces.length > 0 && <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {workspaces.map((workspace) => <WorkspaceCard key={workspace.id + workspace.updated_at + workspace.archived} workspace={workspace} onChanged={load} />)}
        </ul>}
      </section>

    </main>
  )
}
