import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { formatTokens, formatUsd, formatWhen } from "@/lib/format"
import { getAiUsage, getAuditLog } from "@/lib/governance"
import type { AiUsage, AuditFilters, AuditLogPage, UsageGroup } from "@/lib/governance"
import { listWorkspaces } from "@/lib/workspaces"
import type { WorkspaceMeta } from "@/lib/workspaces"

const PAGE_SIZE = 25
const field = "rounded-md border bg-background px-2 py-1.5 text-sm"
const ACTION_LABEL: Record<string, string> = {
  "auth.login": "Signed in", "auth.login_failed": "Failed sign-in", "auth.logout": "Signed out", "workspace.create": "Created workspace",
  "workspace.update": "Renamed or edited details", "workspace.archive": "Archived workspace", "workspace.restore": "Restored workspace",
  "workspace.edit": "Edited scenarios", "workspace.export": "Exported deck", "agent.run": "Asked the assistant",
}
const actionLabel = (action: string) => ACTION_LABEL[action] ?? action
const detailText = (detail: Record<string, unknown> | null) => detail ? Object.entries(detail).map(([k, v]) => `${k}: ${String(v)}`).join(" · ") : ""

type Tab = "log" | "usage"

function TabBar({ tab, setTab }: { tab: Tab; setTab: (tab: Tab) => void }) {
  const item = (id: Tab, label: string) => <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
    className={`rounded-md px-4 py-2 text-sm ${tab === id ? "bg-ink font-medium text-white" : "hover:bg-card"}`}>{label}</button>
  return <div role="tablist" aria-label="Audit sections" className="flex w-fit gap-1 rounded-lg bg-secondary p-1">{item("log", "Audit log")}{item("usage", "AI usage and cost")}</div>
}

function DateRange({ start, end, onChange }: { start: string; end: string; onChange: (start: string, end: string) => void }) {
  return <>
    <label className="text-xs text-muted-foreground">From<input type="date" value={start} max={end || undefined} onChange={(e) => onChange(e.target.value, end)} className={`${field} ml-1`} /></label>
    <label className="text-xs text-muted-foreground">To<input type="date" value={end} min={start || undefined} onChange={(e) => onChange(start, e.target.value)} className={`${field} ml-1`} /></label></>
}

function AuditLog({ workspaces }: { workspaces: WorkspaceMeta[] }) {
  const [filters, setFilters] = useState<AuditFilters>({})
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<AuditLogPage>()
  const [error, setError] = useState<string>()
  useEffect(() => {
    let active = true
    getAuditLog(filters, PAGE_SIZE, offset).then((p) => { if (active) { setPage(p); setError(undefined) } })
      .catch((c: unknown) => { if (active) setError(c instanceof Error ? c.message : "Could not load the audit log") })
    return () => { active = false }
  }, [filters, offset])
  const set = (change: Partial<AuditFilters>) => { setOffset(0); setFilters((f) => ({ ...f, ...change })) }
  const total = page?.total ?? 0
  return (
    <section className="space-y-4" aria-label="Audit log">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-muted-foreground">Action<select value={filters.action ?? ""} onChange={(e) => set({ action: e.target.value || undefined })} className={`${field} ml-1`}>
          <option value="">All actions</option>{page?.actions.map((a) => <option key={a} value={a}>{actionLabel(a)}</option>)}</select></label>
        <label className="text-xs text-muted-foreground">Person<input type="search" placeholder="email" value={filters.user_email ?? ""} onChange={(e) => set({ user_email: e.target.value || undefined })} className={`${field} ml-1 w-52`} /></label>
        <label className="text-xs text-muted-foreground">Workspace<select value={filters.workspace_id ?? ""} onChange={(e) => set({ workspace_id: e.target.value || undefined })} className={`${field} ml-1`}>
          <option value="">All</option>{workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
        <DateRange start={filters.start ?? ""} end={filters.end ?? ""} onChange={(start, end) => set({ start: start || undefined, end: end || undefined })} />
      </div>
      {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
      {!page && !error && <p className="text-sm text-muted-foreground" role="status">Loading…</p>}
      {page && page.items.length === 0 && <p className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">No audit entries match these filters.</p>}
      {page && page.items.length > 0 && <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground"><th className="px-4 py-3">When</th><th className="px-4 py-3">Who</th><th className="px-4 py-3">Action</th><th className="px-4 py-3">Workspace</th><th className="px-4 py-3">Detail</th></tr></thead>
          <tbody>{page.items.map((item) => <tr key={item.id} className="border-b last:border-0">
            <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">{formatWhen(item.at)}</td>
            <td className="px-4 py-2.5">{item.user_email}</td>
            <td className="px-4 py-2.5"><span className={item.action === "auth.login_failed" ? "font-medium text-loss" : ""}>{actionLabel(item.action)}</span></td>
            <td className="px-4 py-2.5">{item.workspace_name ?? (item.workspace_id ? "(removed)" : "")}</td>
            <td className="max-w-xs truncate px-4 py-2.5 text-muted-foreground" title={detailText(item.detail)}>{detailText(item.detail)}</td></tr>)}</tbody>
        </table></div>}
      {total > 0 && <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{offset + 1} to {Math.min(offset + PAGE_SIZE, total)} of {total}</span>
        <span className="flex gap-2">
          <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="rounded-md border px-3 py-1.5 enabled:hover:bg-secondary disabled:opacity-40">Previous</button>
          <button type="button" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)} className="rounded-md border px-3 py-1.5 enabled:hover:bg-secondary disabled:opacity-40">Next</button></span></div>}
    </section>
  )
}

function Tile({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="rounded-xl border bg-card p-4"><p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
    <p className="num mt-1 text-2xl font-semibold">{value}</p>{detail && <p className="text-xs text-muted-foreground">{detail}</p>}</div>
}

function GroupTable({ title, rows, nameOf }: { title: string; rows: UsageGroup[]; nameOf: (row: UsageGroup) => string }) {
  return (
    <section className="space-y-2" aria-label={title}>
      <h2 className="font-display text-lg font-semibold">{title}</h2>
      <div className="overflow-x-auto rounded-xl border bg-card"><table className="w-full text-sm">
        <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground"><th className="px-4 py-3">Name</th><th className="px-4 py-3 text-right">Runs</th><th className="px-4 py-3 text-right">Input tokens</th><th className="px-4 py-3 text-right">Output tokens</th><th className="px-4 py-3 text-right">Cost (USD)</th></tr></thead>
        <tbody>{rows.map((row) => <tr key={String(row.key)} className="border-b last:border-0">
          <td className="px-4 py-2.5">{nameOf(row)}</td><td className="num px-4 py-2.5 text-right">{row.runs}</td>
          <td className="num px-4 py-2.5 text-right">{formatTokens(row.input_tokens)}</td><td className="num px-4 py-2.5 text-right">{formatTokens(row.output_tokens)}</td>
          <td className="num px-4 py-2.5 text-right">{formatUsd(row.cost_usd)}{row.cost_usd !== null && row.unpriced_runs > 0 && <span className="ml-1 text-xs text-muted-foreground">+{row.unpriced_runs} unpriced</span>}</td></tr>)}</tbody>
      </table></div></section>
  )
}

function AiUsagePanel({ workspaces }: { workspaces: WorkspaceMeta[] }) {
  const [workspaceId, setWorkspaceId] = useState("")
  const [range, setRange] = useState<[string, string]>(["", ""])
  const [usage, setUsage] = useState<AiUsage>()
  const [error, setError] = useState<string>()
  useEffect(() => {
    let active = true
    getAiUsage({ workspace_id: workspaceId || undefined, start: range[0] || undefined, end: range[1] || undefined })
      .then((u) => { if (active) { setUsage(u); setError(undefined) } })
      .catch((c: unknown) => { if (active) setError(c instanceof Error ? c.message : "Could not load AI usage") })
    return () => { active = false }
  }, [workspaceId, range])
  const model = usage ? Object.entries(usage.rates.models) : []
  return (
    <section className="space-y-6" aria-label="AI usage and cost">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-muted-foreground">Workspace<select value={workspaceId} onChange={(e) => setWorkspaceId(e.target.value)} className={`${field} ml-1`}>
          <option value="">All workspaces</option>{workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
        <DateRange start={range[0]} end={range[1]} onChange={(start, end) => setRange([start, end])} />
      </div>
      {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
      {!usage && !error && <p className="text-sm text-muted-foreground" role="status">Loading…</p>}
      {usage && <>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Tile label="Agent runs" value={String(usage.totals.runs)} />
          <Tile label="Input tokens" value={formatTokens(usage.totals.input_tokens)} detail={usage.totals.cached_input_tokens ? `${formatTokens(usage.totals.cached_input_tokens)} cached` : undefined} />
          <Tile label="Output tokens" value={formatTokens(usage.totals.output_tokens)} />
          <Tile label="Cost (USD)" value={formatUsd(usage.totals.cost_usd)} detail={usage.totals.unpriced_runs > 0 ? `${usage.totals.unpriced_runs} run(s) on a model with no rate are not included` : undefined} />
        </div>
        {usage.totals.runs === 0 && <p className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">No AI usage recorded for this selection yet. Runs of the AI decision assistant appear here with their tokens and cost.</p>}
        {usage.totals.runs > 0 && <>
          <GroupTable title="By workspace" rows={usage.by_workspace} nameOf={(r) => r.name ?? "No workspace"} />
          <div className="grid gap-6 lg:grid-cols-2">
            <GroupTable title="By person" rows={usage.by_user} nameOf={(r) => String(r.key)} />
            <GroupTable title="By model" rows={usage.by_model} nameOf={(r) => String(r.key).replace(":", " / ")} />
          </div>
          <section className="space-y-2" aria-label="Recent runs"><h2 className="font-display text-lg font-semibold">Recent runs</h2>
            <div className="overflow-x-auto rounded-xl border bg-card"><table className="w-full text-sm">
              <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground"><th className="px-4 py-3">When</th><th className="px-4 py-3">Who</th><th className="px-4 py-3">Workspace</th><th className="px-4 py-3">Model</th><th className="px-4 py-3 text-right">In / out</th><th className="px-4 py-3 text-right">Cost</th></tr></thead>
              <tbody>{usage.recent.map((r, i) => <tr key={(r.trace_id ?? "x") + i} className="border-b last:border-0">
                <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">{formatWhen(r.at)}</td><td className="px-4 py-2.5">{r.user_email}</td><td className="px-4 py-2.5">{r.workspace_name ?? "None"}</td>
                <td className="px-4 py-2.5">{r.trace_id ? <Link to={`/agent-runs/${r.trace_id}`} className="text-primary underline-offset-4 hover:underline">{r.model}</Link> : r.model}</td>
                <td className="num whitespace-nowrap px-4 py-2.5 text-right">{formatTokens(r.input_tokens)} / {formatTokens(r.output_tokens)}</td><td className="num px-4 py-2.5 text-right">{formatUsd(r.cost_usd)}</td></tr>)}</tbody>
            </table></div></section>
        </>}
        <p className="text-xs text-muted-foreground">Cost is tokens times the provider's Standard-tier rate, worked out on the server ({usage.rates.version}, fetched {usage.rates.fetched_on}, {usage.rates.unit}).
          {" "}{model.map(([name, r]) => `${name}: $${r.input.toFixed(2)} input, $${r.cached_input.toFixed(2)} cached, $${r.output.toFixed(2)} output`).join("; ")}. Source: <a href={usage.rates.source} target="_blank" rel="noopener noreferrer" className="text-primary underline-offset-4 hover:underline">provider pricing page</a>. Rates change; check the page before relying on a figure.</p>
      </>}
    </section>
  )
}

export function AuditPage() {
  const [tab, setTab] = useState<Tab>("log")
  const [workspaces, setWorkspaces] = useState<WorkspaceMeta[]>([])
  const load = useCallback(() => { listWorkspaces(true).then(setWorkspaces).catch(() => undefined) }, [])
  useEffect(() => { load() }, [load])
  return (
    <main className="mx-auto w-full max-w-[1200px] flex-1 space-y-6 px-5 py-8 md:px-8">
      <div>
        <h1 className="font-display text-3xl font-semibold">Audit and AI usage</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">Who did what, and what the AI assistant has cost. The log records actions only, never scenario contents or passwords.</p>
      </div>
      <TabBar tab={tab} setTab={setTab} />
      {tab === "log" ? <AuditLog workspaces={workspaces} /> : <AiUsagePanel workspaces={workspaces} />}
    </main>
  )
}
