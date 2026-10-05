import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import type { Assumption } from "@/lib/types"

export function AssumptionsDrawer({ assumptions }: { assumptions: Assumption[] }) {
  return (
    <Sheet>
      <SheetTrigger render={<Button variant="outline" />}>
        Assumptions &amp; guardrails
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Assumptions registry</SheetTitle>
          <SheetDescription>
            Every number above is traceable to one of these. Each has a value, a
            source and a rationale — read from{" "}
            <code className="font-mono text-xs">GET /assumptions</code> once the
            backend is wired up.
          </SheetDescription>
        </SheetHeader>
        <ScrollArea className="h-[calc(100vh-10rem)] px-4">
          <div className="space-y-4 pb-8">
            {assumptions.map((a) => (
              <div key={a.id}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{a.label}</span>
                  <Badge variant="outline" className="font-mono text-xs">
                    {a.id}
                  </Badge>
                </div>
                <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                  <span>
                    value: <span className="text-foreground">{a.value}</span>
                  </span>
                  <Badge variant="secondary" className="text-xs">
                    {a.source}
                  </Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{a.rationale}</p>
                {a.validRange && (
                  <p className="text-xs text-muted-foreground">
                    valid range: {a.validRange}
                  </p>
                )}
                <Separator className="mt-4" />
              </div>
            ))}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
