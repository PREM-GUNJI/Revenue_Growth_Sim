/** A thin bar under a slider: green where the engine has data, red where it will refuse to give numbers. */
export function SupportBar({ min, max, lo, hi }: { min: number; max: number; lo: number; hi: number }) {
  const pos = (v: number) => Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100))
  return <div aria-hidden="true" className="relative mt-1 h-1.5 w-full overflow-hidden rounded bg-loss/30">
    <div className="absolute inset-y-0 rounded bg-gain/70" style={{ left: `${pos(lo)}%`, width: `${pos(hi) - pos(lo)}%` }} />
  </div>
}
