/**
 * Money, in integer minor units.
 *
 * The API speaks paise and so does this app, end to end. Floating-point rupees
 * are a rounding bug waiting for the first ₹0.005: `0.1 + 0.2 !== 0.3` is
 * funny in a blog post and a mismatched invoice in a booking platform. The only
 * place a decimal appears is the string a human reads.
 */

export interface Money {
  readonly amountMinor: number
  readonly currency: string
}

export function money(amountMinor: number, currency: string): Money {
  return { amountMinor: Math.round(amountMinor), currency }
}

export function zero(currency: string): Money {
  return { amountMinor: 0, currency }
}

export function addMoney(a: Money, b: Money): Money {
  assertSameCurrency(a, b)
  return money(a.amountMinor + b.amountMinor, a.currency)
}

export function subtractMoney(a: Money, b: Money): Money {
  assertSameCurrency(a, b)
  return money(a.amountMinor - b.amountMinor, a.currency)
}

export function multiplyMoney(a: Money, factor: number): Money {
  return money(a.amountMinor * factor, a.currency)
}

function assertSameCurrency(a: Money, b: Money): void {
  if (a.currency !== b.currency) {
    // Loudly, not silently: a currency mix-up that renders is a wrong price
    // shown to a customer, which is the one bug class that costs real money.
    throw new Error(`Cannot combine ${a.currency} with ${b.currency}`)
  }
}

const formatters = new Map<string, Intl.NumberFormat>()

function formatterFor(currency: string, locale: string, fractionDigits: number): Intl.NumberFormat {
  const key = `${locale}:${currency}:${fractionDigits}`
  let existing = formatters.get(key)
  if (!existing) {
    // Intl.NumberFormat construction is genuinely expensive and these are
    // rendered in every price on every search card.
    existing = new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    })
    formatters.set(key, existing)
  }
  return existing
}

/** Minor units per major unit. JPY and KRW have none; INR, USD, EUR have two. */
function exponentFor(currency: string): number {
  return ZERO_DECIMAL.has(currency) ? 0 : 2
}

const ZERO_DECIMAL = new Set(['JPY', 'KRW', 'VND', 'CLP', 'ISK'])

export interface FormatOptions {
  /** Drop `.00` — right for prices in lists, wrong for an invoice total. */
  readonly compact?: boolean
  readonly locale?: string
}

export function formatMoney(value: Money, options: FormatOptions = {}): string {
  const exponent = exponentFor(value.currency)
  const major = value.amountMinor / 10 ** exponent
  const hideDecimals = options.compact === true && value.amountMinor % 10 ** exponent === 0
  return formatterFor(
    value.currency,
    options.locale ?? 'en-IN',
    hideDecimals ? 0 : exponent,
  ).format(major)
}

/** `formatMoney` for a bare number plus currency, which is how the API sends it. */
export function formatMinor(
  amountMinor: number | null | undefined,
  currency: string,
  options: FormatOptions = {},
): string {
  if (amountMinor === null || amountMinor === undefined) return '—'
  return formatMoney(money(amountMinor, currency), options)
}

/** "₹4,500 / night" — the unit is part of the price, and omitting it is a lie. */
export function formatPerNight(amountMinor: number, currency: string, locale?: string): string {
  const opts: FormatOptions = { compact: true, ...(locale === undefined ? {} : { locale }) }
  return `${formatMinor(amountMinor, currency, opts)} / night`
}
