export function AppFooter({ engineMs, computeMs, modelVersion, dataHash }: { engineMs?: number; computeMs?: number; modelVersion?: string; dataHash?: string }) {
  return <footer className="mt-auto border-t px-6 py-3 text-xs text-muted-foreground"><div className="flex flex-wrap items-center justify-between gap-2">
    <span title="Engine time is measured on the server for the last batch; the round trip adds network and page time.">
      engine compute: {engineMs === undefined ? "—" : engineMs.toFixed(1) + " ms"} · round trip: {computeMs === undefined ? "—" : computeMs.toFixed(0) + " ms"}</span>
    <span>engine {modelVersion ?? "—"} · data {dataHash ? dataHash.slice(0, 12) + "…" : "—"} · same inputs always give the same numbers</span>
  </div></footer>
}
