import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

export type ClaimLabel = "Observed" | "Modeled" | "Assumed" | "Recommended"

const STYLE: Record<ClaimLabel, string> = {
  Observed: "bg-edge/10 text-edge",
  Modeled: "bg-ink/10 text-foreground",
  Assumed: "bg-primary/10 text-primary",
  Recommended: "border border-primary/40 text-primary",
}
const MEANING: Record<ClaimLabel, string> = {
  Observed: "Read straight from the synthetic sales history.",
  Modeled: "Calculated by the deterministic engine from documented assumptions.",
  Assumed: "A documented assumption in the registry, not measured.",
  Recommended: "A suggestion that rests on a modeled result.",
}

/** The four claim labels from the project rules: every figure on screen says where it comes from. */
export function LabelTag({ label }: { label: ClaimLabel }) {
  return <Tooltip>
    <TooltipTrigger render={<span className={`inline-block cursor-help rounded px-1.5 py-0.5 text-[11px] font-medium ${STYLE[label]}`} />}>{label}</TooltipTrigger>
    <TooltipContent>{MEANING[label]}</TooltipContent>
  </Tooltip>
}
