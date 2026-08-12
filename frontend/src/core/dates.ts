/**
 * Stay dates.
 *
 * A stay is a **half-open** range: `[check_in, check_out)`. The guest sleeps on
 * check-in night and leaves on check-out morning, so a 12th→14th stay is two
 * nights and the 14th is free for the next guest. Getting this wrong is either
 * an off-by-one on the price or an overbooking, and it is the single most
 * common bug in booking software.
 *
 * Dates here are calendar dates, not instants. A stay starting "12 September"
 * starts on the 12th in Goa regardless of where the guest's phone thinks it is,
 * so these are `YYYY-MM-DD` strings — the same thing the API speaks — and never
 * `Date` objects silently shifted by a timezone.
 */

/** A calendar date as `YYYY-MM-DD`. */
export type IsoDate = string

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const MS_PER_DAY = 86_400_000

export function isIsoDate(value: string): value is IsoDate {
  return ISO_DATE.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`))
}

/** Today in the *user's* timezone, as a calendar date. */
export function today(): IsoDate {
  return toIsoDate(new Date())
}

export function toIsoDate(date: Date): IsoDate {
  // Local getters, not toISOString(): at 01:00 IST the UTC date is still
  // yesterday, and "yesterday" is not a bookable check-in.
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/** Parsed as UTC midnight, purely as a stable arithmetic anchor. */
function asUtc(date: IsoDate): number {
  return Date.parse(`${date}T00:00:00Z`)
}

export function addDays(date: IsoDate, days: number): IsoDate {
  const shifted = new Date(asUtc(date) + days * MS_PER_DAY)
  return shifted.toISOString().slice(0, 10)
}

/** Nights between two dates. Half-open, so `12th → 14th` is 2. */
export function nightsBetween(checkIn: IsoDate, checkOut: IsoDate): number {
  return Math.round((asUtc(checkOut) - asUtc(checkIn)) / MS_PER_DAY)
}

export function isBefore(a: IsoDate, b: IsoDate): boolean {
  return asUtc(a) < asUtc(b)
}

export function isPast(date: IsoDate): boolean {
  return isBefore(date, today())
}

/** Every night actually slept in — check-out excluded, by definition. */
export function nightsIn(checkIn: IsoDate, checkOut: IsoDate): IsoDate[] {
  const out: IsoDate[] = []
  for (let d = checkIn; isBefore(d, checkOut); d = addDays(d, 1)) out.push(d)
  return out
}

export interface StayRange {
  readonly checkIn: IsoDate
  readonly checkOut: IsoDate
}

export function isValidStay(range: Partial<StayRange>): range is StayRange {
  const { checkIn, checkOut } = range
  return (
    checkIn !== undefined &&
    checkOut !== undefined &&
    isIsoDate(checkIn) &&
    isIsoDate(checkOut) &&
    isBefore(checkIn, checkOut)
  )
}

// ── display ───────────────────────────────────────────────────────────────

const dateFormats = new Map<string, Intl.DateTimeFormat>()

function dateFormatter(locale: string, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = locale + JSON.stringify(options)
  let f = dateFormats.get(key)
  if (!f) {
    f = new Intl.DateTimeFormat(locale, { ...options, timeZone: 'UTC' })
    dateFormats.set(key, f)
  }
  return f
}

export function formatDate(date: IsoDate, locale = 'en-IN'): string {
  return dateFormatter(locale, { day: 'numeric', month: 'short', year: 'numeric' }).format(
    new Date(asUtc(date)),
  )
}

export function formatDateShort(date: IsoDate, locale = 'en-IN'): string {
  return dateFormatter(locale, { day: 'numeric', month: 'short' }).format(new Date(asUtc(date)))
}

/** "12 – 14 Sep 2026", collapsing the repeated month and year. */
export function formatStay(checkIn: IsoDate, checkOut: IsoDate, locale = 'en-IN'): string {
  const sameMonth = checkIn.slice(0, 7) === checkOut.slice(0, 7)
  const left = sameMonth ? new Date(asUtc(checkIn)).getUTCDate().toString() : formatDateShort(checkIn, locale)
  return `${left} – ${formatDate(checkOut, locale)}`
}

/** An instant, for "booked on" and "last used". */
export function formatDateTime(iso: string | null | undefined, locale = 'en-IN'): string {
  if (!iso) return '—'
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return '—'
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(parsed)
}

/** "in 3 days" / "2 hours ago", for holds and trip countdowns. */
export function formatRelative(iso: string | null | undefined, locale = 'en-IN'): string {
  if (!iso) return '—'
  const target = new Date(iso).getTime()
  if (Number.isNaN(target)) return '—'
  const deltaSeconds = Math.round((target - Date.now()) / 1000)
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['year', 31_536_000],
    ['month', 2_592_000],
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  for (const [unit, seconds] of units) {
    if (Math.abs(deltaSeconds) >= seconds) return rtf.format(Math.round(deltaSeconds / seconds), unit)
  }
  return rtf.format(deltaSeconds, 'second')
}

/** `mm:ss`, for the checkout hold countdown. */
export function formatCountdown(secondsLeft: number): string {
  const safe = Math.max(0, Math.floor(secondsLeft))
  const m = Math.floor(safe / 60)
  const s = safe % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
