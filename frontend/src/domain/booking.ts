/** Bookings and the status machine, as the guest experiences it. */

import type { IsoDate } from '@/core/dates'

export const BOOKING_STATUSES = [
  'pending_payment',
  'pending_approval',
  'confirmed',
  'in_stay',
  'completed',
  'cancelled',
  'expired',
  'rejected',
  'no_show',
] as const

export type BookingStatus = (typeof BOOKING_STATUSES)[number]

export interface NightlyRate {
  readonly date: IsoDate
  readonly amountMinor: number
}

export interface RefundState {
  readonly status: string
  readonly amountMinor: number
  readonly currency: string
  readonly reason: string | null
  readonly requestedAt: string | null
  readonly completedAt: string | null
}

export interface Booking {
  readonly id: string
  readonly reference: string
  readonly status: BookingStatus
  readonly propertyId: string
  readonly propertyName: string
  readonly propertyAddress: string | null
  readonly roomTypeId: string
  readonly roomTypeName: string
  readonly checkIn: IsoDate
  readonly checkOut: IsoDate
  readonly nights: number
  readonly adults: number
  readonly children: number
  readonly infants: number
  readonly rooms: number
  readonly guestName: string
  readonly guestEmail: string
  readonly guestPhone: string
  readonly specialRequests: string | null
  readonly accommodationMinor: number
  readonly extraGuestMinor: number
  readonly cleaningFeeMinor: number
  readonly taxMinor: number
  readonly platformFeeMinor: number
  readonly totalMinor: number
  readonly currency: string
  readonly cancellationPolicy: string
  readonly createdAt: string | null
  readonly confirmedAt: string | null
  readonly cancelledAt: string | null
  readonly cancelledBy: string | null
  readonly cancellationReason: string | null
  readonly invoiceNumber: string | null
  /**
   * Seconds until the hold lapses and the rooms go back on sale. Present only
   * while `pending_payment`. The countdown is not decoration — a guest who
   * misses it loses the room.
   */
  readonly holdExpiresIn: number | null
  readonly nightlyRates: readonly NightlyRate[]
  readonly refund: RefundState | null
}

export interface RefundPreview {
  readonly policy: string
  readonly hoursBeforeCheckIn: number
  readonly appliedPercent: string
  readonly accommodationMinor: number
  readonly extraGuestMinor: number
  readonly cleaningFeeMinor: number
  readonly taxMinor: number
  readonly platformFeeMinor: number
  readonly totalMinor: number
  readonly vendorRetainsMinor: number
  readonly reason: string
  readonly currency: string
  readonly cancellable: boolean
}

export interface InvoiceLine {
  readonly description: string
  readonly hsnSac: string | null
  readonly quantity: number
  readonly unitPriceMinor: number
  readonly amountMinor: number
  readonly taxRate: string
}

export interface Invoice {
  readonly number: string
  readonly issuedAt: string
  readonly financialYear: string
  readonly bookingReference: string
  readonly supplierName: string
  readonly supplierAddress: string
  readonly supplierGstin: string | null
  readonly guestName: string
  readonly guestEmail: string
  readonly propertyName: string
  readonly checkIn: IsoDate
  readonly checkOut: IsoDate
  readonly nights: number
  readonly rooms: number
  readonly lines: readonly InvoiceLine[]
  readonly subtotalMinor: number
  readonly cgstMinor: number
  readonly sgstMinor: number
  readonly igstMinor: number
  readonly taxTotalMinor: number
  readonly totalMinor: number
  readonly totalInWords: string
  readonly placeOfSupply: string
  readonly currency: string
}

// ── status, as the UI reads it ────────────────────────────────────────────

export interface StatusPresentation {
  readonly label: string
  readonly tone: 'pending' | 'success' | 'active' | 'neutral' | 'danger'
  readonly hint: string
}

const PRESENTATION: Record<BookingStatus, StatusPresentation> = {
  pending_payment: {
    label: 'Payment pending',
    tone: 'pending',
    hint: 'Your rooms are held. Pay to confirm before the hold lapses.',
  },
  pending_approval: {
    label: 'Awaiting host',
    tone: 'pending',
    hint: 'The host has your request. You will not be charged until they accept.',
  },
  confirmed: { label: 'Confirmed', tone: 'success', hint: 'Your stay is booked.' },
  in_stay: { label: 'In stay', tone: 'active', hint: 'Enjoy your stay.' },
  completed: { label: 'Completed', tone: 'neutral', hint: 'This stay has ended.' },
  cancelled: { label: 'Cancelled', tone: 'danger', hint: 'This booking was cancelled.' },
  expired: {
    label: 'Expired',
    tone: 'danger',
    hint: 'The payment window closed and the rooms were released.',
  },
  rejected: { label: 'Declined', tone: 'danger', hint: 'The host could not take this booking.' },
  no_show: { label: 'No show', tone: 'danger', hint: 'Recorded as a no-show by the property.' },
}

export function statusPresentation(status: BookingStatus): StatusPresentation {
  return PRESENTATION[status] ?? { label: status, tone: 'neutral', hint: '' }
}

/** Money is owed and the rooms are held: the checkout page is reachable. */
export function isPayable(booking: Booking): boolean {
  return booking.status === 'pending_payment'
}

export function isUpcoming(booking: Booking): boolean {
  return booking.status === 'confirmed' || booking.status === 'pending_approval'
}

export function isActive(booking: Booking): boolean {
  return isUpcoming(booking) || booking.status === 'in_stay' || booking.status === 'pending_payment'
}

/**
 * Whether to *offer* cancellation. The authoritative answer — and the refund
 * amount — comes from the server's refund preview; this only decides whether
 * showing the button makes sense at all.
 */
export function canRequestCancellation(booking: Booking): boolean {
  return (
    booking.status === 'confirmed' ||
    booking.status === 'pending_approval' ||
    booking.status === 'pending_payment'
  )
}

/** A stay you have actually been on is the only one worth reviewing. */
export function canReview(booking: Booking): boolean {
  return booking.status === 'completed'
}

export function guestSummary(booking: {
  adults: number
  children: number
  infants: number
  rooms: number
}): string {
  const parts = [plural(booking.adults, 'adult')]
  if (booking.children > 0) parts.push(plural(booking.children, 'child', 'children'))
  if (booking.infants > 0) parts.push(plural(booking.infants, 'infant'))
  if (booking.rooms > 1) parts.push(plural(booking.rooms, 'room'))
  return parts.join(' · ')
}

function plural(n: number, singular: string, pluralForm?: string): string {
  return `${n} ${n === 1 ? singular : (pluralForm ?? `${singular}s`)}`
}
