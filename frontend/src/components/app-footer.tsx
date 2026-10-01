export function AppFooter() {
  return (
    <footer className="mt-auto border-t px-6 py-3 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span>compute: — ms (placeholder — Phase 7 benchmarks)</span>
        <span>model: — · data: —</span>
        <button
          type="button"
          className="font-mono underline underline-offset-4"
          title="Copies a token that reproduces this exact board (Phase 6-8)"
        >
          reproduce this
        </button>
      </div>
    </footer>
  )
}
