import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { MEANING, type ClaimLabel } from "@/lib/claim-labels"

export type { ClaimLabel }

const STYLE: Record<ClaimLabel, string> = {
  Observed: "bg-edge/10 text-edge",
  Modeled: "bg-ink/10 text-foreground",
  Assumed: "bg-primary/10 text-primary",
  Recommended: "border border-primary/40 text-primary",
}

/** The four claim labels from the project rules: every figure on screen says where it comes from. */
export function LabelTag({ label }: { label: ClaimLabel }) {
  return <Tooltip>
    <TooltipTrigger render={<span className={`inline-block cursor-help rounded px-1.5 py-0.5 text-[11px] font-medium ${STYLE[label]}`} />}>{label}</TooltipTrigger>
    <TooltipContent>{MEANING[label]}</TooltipContent>
  </Tooltip>
}
