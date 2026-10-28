import { useState } from "react"
import { ExecutiveDeck } from "@/components/executive-deck"
import { exportWorkspace } from "@/lib/governance"
import { useWorkspace } from "@/workspace/workspace-context"

/** Boardroom view of the case: recommendation, a few options, caveats — no analyst chrome. */
export function ExecutivePage() {
  const { workspace, workspaceId, results, guardrail, loading } = useWorkspace()
  const [exportState, setExportState] = useState<{ busy: boolean; error?: string }>({ busy: false })

  async function download() {
    setExportState({ busy: true })
    try {
      const { blob, filename } = await exportWorkspace(workspaceId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setExportState({ busy: false })
    } catch (cause) {
      setExportState({ busy: false, error: cause instanceof Error ? cause.message : "Export failed" })
    }
  }

  if (loading && results.length === 0) {
    return <p className="p-10 text-sm text-muted-foreground" role="status">Loading executive brief…</p>
  }

  return (
    <ExecutiveDeck
      caseName={workspace?.name ?? "Case"}
      question={workspace?.description}
      results={results}
      guardrail={guardrail}
      basePath={`/w/${workspaceId}`}
      onExport={() => void download()}
      exportBusy={exportState.busy}
      exportError={exportState.error}
    />
  )
}
