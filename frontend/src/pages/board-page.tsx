import { AnalyticsViews } from "@/components/analytics-views"
import { ComparisonBoard } from "@/components/comparison-board"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useWorkspace } from "@/workspace/workspace-context"

const tab = "flex-none rounded-md px-4 py-2 text-sm data-active:bg-ink data-active:text-white!"

export function BoardPage() {
  const { guardrail, setGuardrail, loading, results, situation, heatmap, heatmapLoading, generateHeatmap, addNearestSupported, openAssumptions } = useWorkspace()
  return (
    <Tabs defaultValue="board">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Step 3 of 4 · Compare</p>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <TabsList className="h-auto w-fit justify-start gap-1 rounded-lg bg-secondary p-1"><TabsTrigger value="board" className={tab}>Comparison board</TabsTrigger><TabsTrigger value="analytics" className={tab}>Analytics</TabsTrigger></TabsList>
        <label className="text-xs text-muted-foreground">Volume guardrail: lose no more than <span className="num text-sm font-semibold text-foreground">{guardrail}%</span> volume
          <input aria-label="Volume guardrail" type="range" min="0" max="20" step="1" value={guardrail} onChange={(e) => setGuardrail(Number(e.target.value))} className="mt-1 block w-48" /></label>
      </div>
      <TabsContent value="board" className={`mt-5 space-y-4 transition-opacity ${loading && results.length ? "opacity-60" : ""}`}>
        {!results.length && loading && <p className="text-sm text-muted-foreground">Evaluating scenarios…</p>}
        {results.length > 0 && <ComparisonBoard scenarios={results} onUseNearest={addNearestSupported} volumeGuardrailPct={guardrail} onShowAssumptions={openAssumptions} />}
      </TabsContent>
      <TabsContent value="analytics" className="mt-5">{results.length > 0 && <AnalyticsViews scenarios={results} heatmap={heatmap} baselineGp={situation?.totals.focal.gp ?? 0} onGenerateHeatmap={() => void generateHeatmap()} heatmapLoading={heatmapLoading} />}</TabsContent>
    </Tabs>
  )
}
