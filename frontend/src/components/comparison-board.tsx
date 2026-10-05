import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { ScenarioDelta, ScenarioResult } from "@/lib/types"

function DeltaCell({
  value,
  suffix = "%",
}: {
  value: number | undefined
  suffix?: string
}) {
  if (value === undefined) return <span className="text-muted-foreground">—</span>
  const positive = value > 0
  const negative = value < 0
  return (
    <span
      className={
        negative
          ? "text-destructive font-medium"
          : positive
            ? "font-medium text-emerald-600 dark:text-emerald-400"
            : "text-muted-foreground"
      }
    >
      {positive ? "+" : ""}
      {value.toFixed(1)}
      {suffix}
    </span>
  )
}

function BandTooltip({
  delta,
  p10,
  p90,
  children,
}: {
  delta: ScenarioDelta | undefined
  p10: ScenarioDelta | undefined
  p90: ScenarioDelta | undefined
  children: React.ReactNode
}) {
  if (!delta || !p10 || !p90) return <>{children}</>
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span className="cursor-help underline decoration-dotted underline-offset-4" />
        }
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>
        P10-P90: {p10.marginPct.toFixed(1)}% to {p90.marginPct.toFixed(1)}%
        (sensitivity band, not a confidence interval)
      </TooltipContent>
    </Tooltip>
  )
}

export function ComparisonBoard({ scenarios }: { scenarios: ScenarioResult[] }) {
  const refused = scenarios.filter((s) => s.status === "REFUSED")
  const evaluable = scenarios.filter((s) => s.status !== "REFUSED")

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-56">Scenario</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Δ Volume</TableHead>
              <TableHead className="text-right">Δ Revenue</TableHead>
              <TableHead className="text-right">Δ Margin</TableHead>
              <TableHead className="text-right">Δ Margin (ppt)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {evaluable.map((s) => {
              const isLoser = (s.delta?.marginPct ?? 0) < 0
              return (
                <TableRow
                  key={s.scenarioId}
                  className={isLoser ? "bg-destructive/5" : undefined}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {s.name}
                      {s.isBaseline && <Badge variant="secondary">baseline</Badge>}
                      {s.isAgentProposed && <Badge variant="outline">agent-proposed</Badge>}
                      {isLoser && !s.isBaseline && (
                        <Badge variant="destructive">worse than baseline</Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={s.status === "EDGE" ? "outline" : "secondary"}>
                      {s.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <DeltaCell value={s.delta?.volumePct} />
                  </TableCell>
                  <TableCell className="text-right">
                    <DeltaCell value={s.delta?.revenuePct} />
                  </TableCell>
                  <TableCell className="text-right">
                    <BandTooltip delta={s.delta} p10={s.p10} p90={s.p90}>
                      <DeltaCell value={s.delta?.marginPct} />
                    </BandTooltip>
                  </TableCell>
                  <TableCell className="text-right">
                    <DeltaCell value={s.delta?.marginPpt} suffix="pp" />
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {refused.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {refused.map((s) => (
            <div
              key={s.scenarioId}
              className="rounded-lg border border-dashed bg-muted/40 p-4 text-sm text-muted-foreground"
            >
              <div className="mb-1 flex items-center gap-2">
                <span className="font-medium text-foreground">{s.name}</span>
                <Badge variant="destructive">REFUSED</Badge>
              </div>
              <p>{s.refusalReason}</p>
              <p className="mt-2 text-xs italic">
                No ballpark number is given for a refused scenario, even under pressure.
              </p>
              <button
                type="button"
                className="mt-2 text-xs font-medium text-primary underline underline-offset-4"
              >
                Use nearest supported scenario
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
