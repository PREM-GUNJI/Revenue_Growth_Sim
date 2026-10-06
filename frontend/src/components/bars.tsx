import { signed, tone } from "@/lib/catalog"

/** Bar growing from a zero axis; optional P10-P90 whisker. */
export function DivBar({ value, max, band, strong }: { value: number; max: number; band?: [number, number]; strong?: boolean }) {
  const pos = (v: number) => 50 + (Math.max(-max, Math.min(max, v)) / max) * 50
  const left = Math.min(50, pos(value)), width = Math.abs(pos(value) - 50)
  return <div className={`relative w-full ${strong ? "h-3" : "h-2"}`} aria-hidden="true">
    <div className="absolute inset-y-0 left-1/2 w-px bg-foreground/25" />
    <div className="bar absolute inset-y-0 rounded-[2px]" style={{ left: `${left}%`, width: `${width}%`, background: value < 0 ? "var(--loss)" : "var(--gain)", ["--origin" as string]: value < 0 ? "right" : "left" }} />
    {band && <div className="absolute top-1/2 h-px bg-foreground/70" style={{ left: `${pos(band[0])}%`, width: `${pos(band[1]) - pos(band[0])}%` }}>
      <span className="absolute -left-px -top-[3px] h-[7px] w-px bg-foreground/70" /><span className="absolute -right-px -top-[3px] h-[7px] w-px bg-foreground/70" />
    </div>}
  </div>
}

export function Metric({ label, value, max, band, strong, extra }: { label: string; value: number; max: number; band?: [number, number]; strong?: boolean; extra?: string }) {
  return <div className="min-w-0">
    <div className="mb-1.5 flex items-baseline justify-between gap-2 text-xs text-muted-foreground"><span>{label}</span>{extra && <span>{extra}</span>}</div>
    <div className={`num ${strong ? "text-xl" : "text-base"} font-semibold ${tone(value)}`}>{signed(value)}</div>
    <div className="mt-1.5"><DivBar value={value} max={max} band={band} strong={strong} /></div>
  </div>
}

export interface Series { key: string; label: string; color: string }
export interface ChartPoint { x: number; refused?: boolean; values: Record<string, number | null | undefined> }

/** Small line chart over a sweep. Refused x positions are hatched and carry no values. */
export function LineChart({ points, series, markers = [], xLabel, xFormat, ariaLabel }: {
  points: ChartPoint[]; series: Series[]; markers?: { x: number; label: string; tone?: string }[]
  xLabel: string; xFormat: (x: number) => string; ariaLabel: string
}) {
  const W = 640, H = 300, L = 44, R = 16, T = 34, B = 66
  const xs = points.map((p) => p.x).concat(markers.map((m) => m.x))
  const xMin = Math.min(...xs), xMax = Math.max(...xs)
  const ys = points.flatMap((p) => series.map((s) => p.values[s.key]).filter((v): v is number => v !== null && v !== undefined)).concat(0)
  const yMin = Math.min(...ys), yMax = Math.max(...ys), pad = (yMax - yMin) * 0.12 || 1
  const x = (v: number) => L + ((v - xMin) / (xMax - xMin || 1)) * (W - L - R)
  const y = (v: number) => T + (1 - (v - (yMin - pad)) / (yMax - yMin + 2 * pad)) * (H - T - B)
  const half = points.length > 1 ? (x(points[1].x) - x(points[0].x)) / 2 : 8
  const ticks = [yMin, 0, yMax].filter((v, i, a) => a.indexOf(v) === i)
  return <svg role="img" aria-label={ariaLabel} viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[480px]">
    <defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="var(--loss)" strokeOpacity=".3" strokeWidth="1.5" /></pattern></defs>
    {points.filter((p) => p.refused).map((p) => <rect key={p.x} x={x(p.x) - half} y={T} width={half * 2} height={H - T - B} fill="url(#hatch)"><title>REFUSED: outside the supported data, so there are no numbers here</title></rect>)}
    {ticks.map((t) => <g key={t}><line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="currentColor" opacity={t === 0 ? 0.35 : 0.1} /><text x={L - 6} y={y(t) + 3} textAnchor="end" fontSize="10" fill="currentColor" opacity=".7">{signed(t, 0)}</text></g>)}
    {markers.map((m, i) => <g key={m.label}><line x1={x(m.x)} x2={x(m.x)} y1={T} y2={H - B} stroke={m.tone ?? "var(--edge)"} strokeDasharray="3 3" /><text x={x(m.x)} y={T - 6 - (i % 2) * 12} textAnchor="middle" fontSize="10" fill={m.tone ?? "var(--edge)"}>{m.label}</text></g>)}
    {series.map((s) => {
      const runs: ChartPoint[][] = [[]]
      points.forEach((p) => { if (p.refused || p.values[s.key] == null) runs.push([]); else runs[runs.length - 1].push(p) })
      return <g key={s.key}>{runs.filter((r) => r.length).map((r, i) => <g key={i}>
        <polyline fill="none" stroke={s.color} strokeWidth="2.25" points={r.map((p) => `${x(p.x)},${y(p.values[s.key] as number)}`).join(" ")} />
        {r.map((p) => <circle key={p.x} cx={x(p.x)} cy={y(p.values[s.key] as number)} r="3" fill={s.color} />)}
      </g>)}</g>
    })}
    {points.filter((_, i) => i % Math.ceil(points.length / 6) === 0).map((p) => <text key={p.x} x={x(p.x)} y={H - B + 16} textAnchor="middle" fontSize="10" fill="currentColor" opacity=".7">{xFormat(p.x)}</text>)}
    <text x={(L + W - R) / 2} y={H - B + 34} textAnchor="middle" fontSize="11" fill="currentColor">{xLabel}</text>
    {series.map((s, i) => <g key={s.key} transform={`translate(${L + i * 150},${H - B + 46})`}><rect width="10" height="3" y="4" fill={s.color} /><text x="15" y="9" fontSize="10" fill="currentColor">{s.label}</text></g>)}
  </svg>
}
