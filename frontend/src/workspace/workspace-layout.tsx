import { useState } from "react"
import { Link, Outlet, useLocation, useNavigate, useParams } from "react-router-dom"
import { AppFooter } from "@/components/app-footer"
import { AssumptionsDrawer } from "@/components/assumptions-drawer"
import { exportWorkspace } from "@/lib/governance"
import { ScenarioBuilder } from "./scenario-builder"
import { useWorkspace } from "./workspace-context"
import type { SaveState } from "./workspace-context"
import { WorkspaceProvider } from "./workspace-provider"

const SAVE_LABEL: Record<SaveState, string> = { saved: "All changes saved", saving: "Saving…", error: "Could not save, retrying on next edit", conflict: "Not saved: changed by someone else" }

function WorkspaceName() {
  const { workspace, renameWorkspace } = useWorkspace()
  const [draft, setDraft] = useState<string>()
  if (!workspace) return null
  if (draft === undefined) {
    return <p className="flex items-center gap-2 text-sm font-medium text-muted-foreground">Workspace
      <span className="text-foreground">{workspace.name}</span>
      <button type="button" onClick={() => setDraft(workspace.name)} className="rounded px-1.5 py-0.5 text-xs hover:bg-secondary">Rename</button></p>
  }
  const commit = () => {
    const name = draft.trim()
    setDraft(undefined)
    if (name && name !== workspace.name) void renameWorkspace(name)
  }
  return <input aria-label="Workspace name" autoFocus value={draft} maxLength={120} onChange={(e) => setDraft(e.target.value)} onBlur={commit}
    onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setDraft(undefined) }}
    className="w-72 rounded-md border bg-card px-2 py-1 text-sm font-medium" />
}

function ExportButton({ workspaceId, disabled }: { workspaceId: string; disabled: boolean }) {
  const [state, setState] = useState<{ busy: boolean; error?: string }>({ busy: false })
  async function download() {
    setState({ busy: true })
    try {
      const { blob, filename } = await exportWorkspace(workspaceId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url; link.download = filename
      document.body.appendChild(link); link.click(); link.remove()
      URL.revokeObjectURL(url)
      setState({ busy: false })
    } catch (cause) {
      setState({ busy: false, error: cause instanceof Error ? cause.message : "Export failed" })
    }
  }
  return <span className="flex items-center gap-2">
    <button type="button" onClick={() => void download()} disabled={disabled || state.busy} className="rounded-md border bg-card px-3 py-1.5 text-sm font-medium hover:bg-secondary disabled:opacity-50">{state.busy ? "Preparing…" : "Export deck"}</button>
    {state.error && <span role="alert" className="max-w-56 truncate text-xs text-loss" title={state.error}>{state.error}</span>}</span>
}

function WorkspaceFrame() {
  const { workspaceId, status, assumptions, error, modelInfo, computeMs, notice, setNotice, saveState } = useWorkspace()
  const location = useLocation()
  const navigate = useNavigate()
  const showBuilder = /\/(simulator|board)$/.test(location.pathname)

  if (status === "loading") return <main className="grid flex-1 place-items-center p-10 text-sm text-muted-foreground" role="status">Loading workspace…</main>
  if (status === "notfound" || status === "failed") {
    return <main className="mx-auto grid w-full max-w-xl flex-1 place-content-center gap-3 px-5 py-24 text-center">
      <h1 className="font-display text-3xl font-semibold">{status === "notfound" ? "Workspace not found" : "Couldn't open this workspace"}</h1>
      <p className="text-muted-foreground">{status === "notfound" ? "It may have been archived or the link is wrong." : error}</p>
      <Link to="/" className="font-medium text-primary underline-offset-4 hover:underline">Back to the homepage</Link>
    </main>
  }

  return (
    <>
      <header className="sticky top-0 z-20 border-b bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1480px] flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3 md:px-8">
          <WorkspaceName />
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span role="status" className={`text-xs ${saveState === "conflict" || saveState === "error" ? "text-loss" : "text-muted-foreground"}`}>{SAVE_LABEL[saveState]}</span>
            <span className="hidden items-center gap-1.5 text-xs text-muted-foreground xl:flex"><span className={`size-2 rounded-full ${error ? "bg-loss" : "bg-gain"}`} />{error ? "Engine unreachable" : "Synthetic data, engine " + (modelInfo?.engine_version ?? "…")}</span>
            <ExportButton workspaceId={workspaceId} disabled={saveState !== "saved"} />
            <AssumptionsDrawer assumptions={assumptions} />
          </div>
        </div>
      </header>

      {notice && <div role="status" className="fixed bottom-14 left-1/2 z-30 flex -translate-x-1/2 items-center gap-4 rounded-lg bg-ink px-4 py-3 text-sm text-white shadow-lg">
        <span>{notice}</span><button type="button" onClick={() => { navigate(`/w/${workspaceId}/board`); setNotice(undefined) }} className="rounded border border-white/40 px-2 py-1 text-xs font-medium hover:bg-white/10">Open comparison board</button></div>}

      <main className={`mx-auto grid w-full max-w-[1480px] flex-1 items-start gap-8 px-5 py-8 md:px-8 ${showBuilder ? "lg:grid-cols-[22rem_minmax(0,1fr)]" : ""}`}>
        {showBuilder && <ScenarioBuilder />}
        <div className="min-w-0 space-y-8">
          {error && <div role="alert" className="rounded-md border border-loss/40 bg-loss/5 p-3 text-sm text-loss">{error}</div>}
          <Outlet />
        </div>
      </main>
      <AppFooter computeMs={computeMs} modelVersion={modelInfo?.engine_version} dataHash={modelInfo?.data_hash} />
    </>
  )
}

/** Route element for /w/:workspaceId: owns that workspace's state for all of its pages. */
export function WorkspaceLayout() {
  const { workspaceId = "" } = useParams()
  return <WorkspaceProvider key={workspaceId} workspaceId={workspaceId}><WorkspaceFrame /></WorkspaceProvider>
}
