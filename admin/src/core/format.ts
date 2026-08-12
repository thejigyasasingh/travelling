/**
 * Formatting.
 *
 * Money is integer minor units everywhere, as in every other client. An admin
 * screen showing a revenue figure that disagrees with the customer's invoice by
 * a rounding error is a support ticket the platform cannot answer.
 */

const money = new Map<string, Intl.NumberFormat>()

function formatter(currency: string, decimals: number): Intl.NumberFormat {
  const key = `${currency}:${decimals}`
  let existing = money.get(key)
  if (!existing) {
    existing = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency,
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
    money.set(key, existing)
  }
  return existing
}

export function formatMinor(
  amountMinor: number | null | undefined,
  currency = 'INR',
  { compact = false } = {},
): string {
  // An em dash for "we do not know". Never ₹0 — a zero an admin can act on is
  // worse than an obvious gap.
  if (amountMinor === null || amountMinor === undefined) return '—'
  const hideDecimals = compact && amountMinor % 100 === 0
  return formatter(currency, hideDecimals ? 0 : 2).format(amountMinor / 100)
}

/** ₹12,34,567 → "₹12.3L". For dashboard tiles, where the shape matters more
 *  than the paisa. */
export function formatCompactMoney(amountMinor: number, currency = 'INR'): string {
  const rupees = amountMinor / 100
  if (rupees >= 10_000_000) return `${formatMinor(0, currency).slice(0, 1)}${(rupees / 10_000_000).toFixed(2)}Cr`
  if (rupees >= 100_000) return `${formatMinor(0, currency).slice(0, 1)}${(rupees / 100_000).toFixed(2)}L`
  return formatMinor(amountMinor, currency, { compact: true })
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-IN').format(value)
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime())
    ? '—'
    : new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(parsed)
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime())
    ? '—'
    : new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(parsed)
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—'
  const target = new Date(iso).getTime()
  if (Number.isNaN(target)) return '—'
  const delta = Math.round((target - Date.now()) / 1000)
  const rtf = new Intl.RelativeTimeFormat('en-IN', { numeric: 'auto' })
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  for (const [unit, seconds] of units) {
    if (Math.abs(delta) >= seconds) return rtf.format(Math.round(delta / seconds), unit)
  }
  return rtf.format(delta, 'second')
}

/** 1500 basis points → "15%". Commission is stored in bps because a float
 *  percentage rounds differently on two machines. */
export function formatBps(bps: number): string {
  return `${(bps / 100).toFixed(bps % 100 === 0 ? 0 : 2)}%`
}
