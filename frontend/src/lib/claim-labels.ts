export type ClaimLabel = "Observed" | "Modeled" | "Assumed" | "Recommended"

export const MEANING: Record<ClaimLabel, string> = {
  Observed: "Read straight from the synthetic sales history.",
  Modeled: "Calculated by the deterministic engine from documented assumptions.",
  Assumed: "A documented assumption in the registry, not measured.",
  Recommended: "A suggestion that rests on a modeled result.",
}
