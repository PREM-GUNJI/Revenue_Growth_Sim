import { useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import type { Assumption } from "@/lib/types"

const GROUPS = ["Demand response", "Costs and trade", "Model limits", "Consumer research"] as const
function groupOf(id: string): (typeof GROUPS)[number] {
  const n = parseInt(id.slice(2), 10)
  return n <= 12 ? GROUPS[0] : n <= 17 ? GROUPS[1] : n <= 25 ? GROUPS[2] : GROUPS[3]
}
/** Links in a reference become clickable; everything else stays plain text. */
function Reference({ text }: { text: string }) {
  return <>{text.split(/(https?:\/\/\S+?)(?=[).,;]?(?:\s|$))/g).map((part, i) => /^https?:\/\//.test(part)
    ? <a key={i} href={part} target="_blank" rel="noreferrer noopener" className="break-all text-primary underline-offset-4 hover:underline">{part}</a>
    : <span key={i}>{part}</span>)}</>
}

export function AssumptionsDrawer({ assumptions, open, onOpenChange, focus }: {
  assumptions: Assumption[]; open: boolean; onOpenChange: (open: boolean) => void; focus: string[]
}) {
  const [query, setQuery] = useState("")
  const [onlyFocus, setOnlyFocus] = useState(true)
  const highlighted = useMemo(() => new Set(focus), [focus])
  const filtering = highlighted.size > 0 && onlyFocus
  const needle = query.trim().toLowerCase()
  const visible = assumptions.filter((a) => (!filtering || highlighted.has(a.id))
    && (!needle || [a.id, a.label, a.rationale, a.reference ?? "", a.source].some((v) => v.toLowerCase().includes(needle))))
  return <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetTrigger render={<Button variant="outline" />}>Assumptions &amp; guardrails</SheetTrigger>
    <SheetContent side="right" className="w-full sm:max-w-lg">
      <SheetHeader>
        <SheetTitle>Assumptions registry</SheetTitle>
        <SheetDescription>Every value the engine uses, with its range, why it was chosen and where to check it. Nothing here is fitted to data.</SheetDescription>
      </SheetHeader>
      <div className="space-y-2 px-4">
        <input aria-label="Search assumptions" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by id, name or reason" className="w-full rounded-md border bg-background px-3 py-2 text-sm" />
        {highlighted.size > 0 && <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={onlyFocus} onChange={(e) => setOnlyFocus(e.target.checked)} />Only the {highlighted.size} this result rests on</label>}
      </div>
      <ScrollArea className="h-[calc(100vh-15rem)] px-4"><div className="space-y-6 pb-8">
        {visible.length === 0 && <p className="text-sm text-muted-foreground">No assumption matches.</p>}
        {GROUPS.map((group) => {
          const items = visible.filter((a) => groupOf(a.id) === group)
          if (!items.length) return null
          return <section key={group} aria-label={group} className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{group}</h3>
            {items.map((item) => <div key={item.id} className={`rounded-md p-2 ${highlighted.has(item.id) ? "bg-primary/5 ring-1 ring-primary/30" : ""}`}>
              <div className="flex items-center justify-between gap-2"><span className="font-medium">{item.label}</span><Badge variant="outline" className="font-mono text-xs">{item.id}</Badge></div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground"><span>value: <span className="text-foreground">{item.value}{item.unit ? " " + item.unit : ""}</span></span><Badge variant="secondary" className="text-xs">{item.source}</Badge>{highlighted.has(item.id) && <Badge className="text-xs">used by this result</Badge>}</div>
              <p className="mt-1 text-sm text-muted-foreground">{item.rationale}</p>
              {item.validRange && <p className="text-xs text-muted-foreground">valid range: {item.validRange}</p>}
              {item.reference && <p className="mt-1 text-xs text-muted-foreground"><span className="font-medium text-foreground/80">Source: </span><Reference text={item.reference} /></p>}
            </div>)}
          </section>
        })}
      </div></ScrollArea>
    </SheetContent>
  </Sheet>
}
