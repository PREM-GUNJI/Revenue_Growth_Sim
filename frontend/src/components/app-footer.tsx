import { useDetailMode } from "@/lib/preferences"

export function AppFooter({ engineMs, computeMs, modelVersion, dataHash }: { engineMs?: number; computeMs?: number; modelVersion?: string; dataHash?: string }) {
  const [detail] = useDetailMode()
  return <footer className="mt-auto border-t px-6 py-3 text-xs text-muted-foreground"><div className="flex flex-wrap items-center justify-between gap-2">
    <span>Synthetic data · every number is calculated by the engine, and the same inputs always give the same numbers</span>
    {detail && <span title="Engine time is measured on the server for the last batch; the round trip adds network and page time.">
      engine compute: {engineMs === undefined ? "—" : engineMs.toFixed(1) + " ms"} · round trip: {computeMs === undefined ? "—" : computeMs.toFixed(0) + " ms"} · engine {modelVersion ?? "—"} · data {dataHash ? dataHash.slice(0, 12) + "…" : "—"}</span>}
  </div></footer>
}
