import { useState } from "react"
import { findSimilarRuns, type ApiScenario, type SimilarRunRow } from "@/lib/api"
import { LabelTag } from "@/components/label-tag"
import { useWorkspace } from "@/workspace/workspace-context"

/** Thin historical similarity panel. Does not replace nearest-supported. */
export function SimilarRunsPanel({ scenario }: { scenario: ApiScenario | null }) {
  const { workspaceId } = useWorkspace()
  const [query, setQuery] = useState("")
  const [rows, setRows] = useState<SimilarRunRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function search() {
    if (!scenario && !query.trim()) {
      setError("Choose an option or enter a short text query.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const result = await findSimilarRuns({
        scenario: scenario ?? undefined,
        query_text: query.trim() || undefined,
        limit: 8,
        workspace_id: workspaceId,
      })
      setRows(result)
    } catch (err) {
      setRows(null)
      setError(err instanceof Error ? err.message : "Similarity search unavailable")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mt-8 border-t border-border/60 pt-6" aria-label="Similar past runs">
      <h2 className="font-display text-lg font-semibold">Similar past runs</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
        Search saved evaluations by lever similarity or a short note. Results are{" "}
        <LabelTag label="Observed" /> history only — not a substitute for engine evaluation or nearest-supported.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="grid min-w-[16rem] flex-1 gap-1 text-sm">
          <span className="text-muted-foreground">Optional text query</span>
          <input
            className="rounded-md border border-border bg-background px-3 py-2"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. PET price up, refusal, promo"
          />
        </label>
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          onClick={() => void search()}
          disabled={busy}
        >
          {busy ? "Searching…" : "Find similar"}
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
      {rows && rows.length === 0 && (
        <p className="mt-3 text-sm text-muted-foreground">No persisted runs matched yet. Save a scenario run first.</p>
      )}
      {rows && rows.length > 0 && (
        <ul className="mt-3 divide-y divide-border/50 rounded-md border border-border/60">
          {rows.map((row) => (
            <li key={row.run_id} className="grid gap-1 px-3 py-2.5 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{row.status}</span>
                <span className="text-muted-foreground">distance {row.distance.toFixed(4)}</span>
                <LabelTag label="Observed" />
              </div>
              <p className="text-muted-foreground">{row.summary_text}</p>
              <p className="font-mono text-xs text-muted-foreground">{row.scenario_id.slice(0, 16)}…</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
