export function AppFooter({ computeMs, modelVersion, dataHash }: { computeMs?: number; modelVersion?: string; dataHash?: string }) {
  return <footer className="mt-auto border-t px-6 py-3 text-xs text-muted-foreground"><div className="flex flex-wrap items-center justify-between gap-2">
    <span>request round trip: {computeMs === undefined ? "—" : computeMs.toFixed(0) + " ms"}</span>
    <span>model: {modelVersion ?? "—"} · data: {dataHash ? dataHash.slice(0, 12) + "…" : "—"}</span>
  </div></footer>
}
