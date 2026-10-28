/** Display helpers for a case's locked market currency (synthetic markets, not live FX). */

export interface Currency {
  code: string
  symbol: string
  locale: string
}

export const INR: Currency = { code: "INR", symbol: "₹", locale: "en-IN" }

export function asCurrency(value: unknown): Currency {
  if (value && typeof value === "object" && "code" in value && "symbol" in value && "locale" in value) {
    const c = value as Currency
    return { code: String(c.code), symbol: String(c.symbol), locale: String(c.locale) }
  }
  if (value === "INR" || value === "USD" || value === "EUR") {
    const map: Record<string, Currency> = {
      INR,
      USD: { code: "USD", symbol: "$", locale: "en-US" },
      EUR: { code: "EUR", symbol: "€", locale: "de-DE" },
    }
    return map[value]
  }
  return INR
}

/** Shelf / unit price with decimals, e.g. ₹40.00 or $1.49. */
export function money(value: number, currency: Currency = INR, digits = 2): string {
  const sign = value < 0 ? "−" : ""
  return sign + currency.symbol + Math.abs(value).toFixed(digits)
}

/** Whole currency units with locale grouping, e.g. ₹2,35,586 or $18,435. */
export function moneyWhole(value: number, currency: Currency = INR): string {
  const format = new Intl.NumberFormat(currency.locale, { maximumFractionDigits: 0 })
  const sign = value < 0 ? "−" : ""
  return sign + currency.symbol + format.format(Math.abs(Math.round(value)))
}

/** Signed whole currency change, e.g. +₹10,440 or −$1,548. */
export function signedMoney(value: number, currency: Currency = INR): string {
  const format = new Intl.NumberFormat(currency.locale, { maximumFractionDigits: 0 })
  if (Math.round(value) === 0) return currency.symbol + "0"
  return (value > 0 ? "+" : "−") + currency.symbol + format.format(Math.abs(Math.round(value)))
}

export function currencyLabel(currency: Currency): string {
  return currency.code
}
