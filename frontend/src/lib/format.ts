export const formatTokens = (value: number) => value.toLocaleString("en-US")

/** Dollars from the server's computed cost. A missing cost means the model has no rate, which is not the same as $0. */
export function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "rate not set"
  return "$" + value.toLocaleString("en-US", { minimumFractionDigits: value < 1 ? 4 : 2, maximumFractionDigits: value < 1 ? 4 : 2 })
}

export function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
}
