import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useBookingDecision, useBookings, useProperties } from '@/api/queries'
import { PageHeader } from '@/app/Shell'
import { formatDate, formatMinor } from '@/core/format'
import { ApiError } from '@/core/http'
import { Button, Card, EmptyRow, Spinner, StatusBadge } from '@/ui/primitives'
import type { VendorBooking } from '@/api/types'

const STATUSES = [
  { value: '', label: 'All' },
  { value: 'pending_approval', label: 'Awaiting you' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'in_stay', label: 'In stay' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'rejected', label: 'Declined' },
] as const

/**
 * Every booking, and the three decisions a host can make about one.
 *
 * The list is a card list rather than a table on purpose: the useful unit is a
 * guest, and a guest is a name, dates, a phone number and a request — six
 * fields that a row squeezes and a card does not.
 */
export function BookingsPage() {
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? ''
  const propertyId = params.get('property') ?? ''
  const [page, setPage] = useState(1)

  const { data: properties } = useProperties({ size: 100 })
  const { data, isPending, error } = useBookings({
    ...(status ? { status } : {}),
    ...(propertyId ? { property_id: propertyId } : {}),
    page,
    size: 20,
  })

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
    setPage(1)
  }

  return (
    <>
      <PageHeader title="Bookings" description="Requests, arrivals and everything already stayed." />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {STATUSES.map((option) => (
          <button
            key={option.value || 'all'}
            type="button"
            onClick={() => setFilter('status', option.value)}
            className={
              status === option.value
                ? 'rounded-lg bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700'
                : 'rounded-lg px-3 py-1.5 text-sm text-ink-600 hover:bg-ink-100'
            }
          >
            {option.label}
          </button>
        ))}

        <select
          value={propertyId}
          onChange={(event) => setFilter('property', event.target.value)}
          className="ml-auto h-9 rounded-lg border border-ink-200 bg-white px-2 text-sm"
        >
          <option value="">Every property</option>
          {properties?.items.map((property) => (
            <option key={property.id} value={property.id}>
              {property.name}
            </option>
          ))}
        </select>
      </div>

      {isPending && (
        <div className="grid place-items-center py-20">
          <Spinner />
        </div>
      )}

      {error instanceof ApiError && (
        <Card>
          <p role="alert" className="px-4 py-8 text-center text-sm text-bad-700">
            {error.message}
          </p>
        </Card>
      )}

      <div className="space-y-3">
        {data?.items.length === 0 && (
          <Card>
            <table className="w-full">
              <tbody>
                <EmptyRow colSpan={1} message="No bookings match this filter." />
              </tbody>
            </table>
          </Card>
        )}
        {data?.items.map((booking) => <BookingCard key={booking.id} booking={booking} />)}
      </div>

      {data && data.total > 20 && (
        <div className="mt-4 flex items-center justify-between text-sm text-ink-600">
          <span>
            Page {page} of {Math.max(1, Math.ceil(data.total / 20))} · {data.total} bookings
          </span>
          <div className="flex gap-2">
            <Button size="sm" disabled={page === 1} onClick={() => setPage((n) => n - 1)}>
              Previous
            </Button>
            <Button
              size="sm"
              disabled={page >= Math.ceil(data.total / 20)}
              onClick={() => setPage((n) => n + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  )
}

function BookingCard({ booking }: { booking: VendorBooking }) {
  const decide = useBookingDecision()
  const [confirming, setConfirming] = useState<'reject' | 'cancel' | null>(null)
  const [reason, setReason] = useState('')

  const awaiting = booking.status === 'pending_approval'
  const cancellable = booking.status === 'confirmed' || booking.status === 'pending_approval'

  return (
    <Card className={awaiting ? 'border-warn-300' : undefined}>
      <div className="flex flex-wrap items-start justify-between gap-4 px-4 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium text-ink-900">{booking.guest_name}</p>
            <StatusBadge status={booking.status} />
            <span className="text-xs text-ink-500">{booking.reference}</span>
          </div>
          <p className="mt-1 text-sm text-ink-600">
            {booking.property_name} · {booking.room_type_name}
          </p>
          <p className="mt-0.5 text-sm text-ink-600">
            {formatDate(booking.check_in)} → {formatDate(booking.check_out)} · {booking.nights} night
            {booking.nights === 1 ? '' : 's'} · {booking.adults + booking.children} guest
            {booking.adults + booking.children === 1 ? '' : 's'}
            {booking.rooms > 1 ? ` · ${booking.rooms} rooms` : ''}
          </p>
          {/* Contact details appear only once the stay is confirmed — before
              that the platform does not hand them over. */}
          {booking.guest_phone && (
            <p className="mt-0.5 text-sm text-ink-600">
              <a href={`tel:${booking.guest_phone}`} className="text-brand-700 underline">
                {booking.guest_phone}
              </a>
            </p>
          )}
          {booking.special_requests && (
            <p className="mt-2 rounded-lg bg-ink-50 px-3 py-2 text-sm text-ink-700">
              “{booking.special_requests}”
            </p>
          )}
          {booking.cancellation_reason && (
            <p className="mt-2 text-sm text-ink-500">
              {booking.status === 'rejected' ? 'Declined' : 'Cancelled'}:{' '}
              {booking.cancellation_reason}
            </p>
          )}
        </div>

        <div className="text-right">
          <p className="text-lg font-semibold tabular-nums text-ink-900">
            {formatMinor(booking.total_minor - booking.platform_fee_minor, booking.currency)}
          </p>
          <p className="text-xs text-ink-500">
            yours · {formatMinor(booking.total_minor, booking.currency)} total
          </p>
        </div>
      </div>

      {(awaiting || cancellable) && (
        <div className="border-t border-ink-100 px-4 py-3">
          {confirming ? (
            <div className="space-y-2">
              <label className="block text-sm">
                <span className="text-xs font-medium text-ink-600">
                  {confirming === 'reject'
                    ? 'Why are you declining? The guest sees this.'
                    : 'Why are you cancelling? The guest sees this, and their refund is issued automatically.'}
                </span>
                <input
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  className="mt-1 h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
                  autoFocus
                />
              </label>
              <div className="flex gap-2">
                <Button
                  variant="danger"
                  disabled={decide.isPending || reason.trim().length < 3}
                  onClick={() =>
                    decide.mutate(
                      { bookingId: booking.id, action: confirming, reason: reason.trim() },
                      { onSuccess: () => setConfirming(null) },
                    )
                  }
                >
                  {decide.isPending
                    ? 'Working…'
                    : confirming === 'reject'
                      ? 'Decline booking'
                      : 'Cancel and refund'}
                </Button>
                <Button onClick={() => setConfirming(null)}>Back</Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {awaiting && (
                <Button
                  variant="primary"
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ bookingId: booking.id, action: 'approve' })}
                >
                  Accept
                </Button>
              )}
              {/* Accepting does not confirm the stay — the guest still has to
                  pay, and the booking sits in "pending payment" until they do.
                  Saying so stops a host treating an accepted request as a
                  guaranteed arrival. */}
              {awaiting && (
                <span className="text-xs text-ink-500">
                  Accepting asks the guest to pay. The stay is confirmed once they have.
                </span>
              )}
              {awaiting && <Button onClick={() => setConfirming('reject')}>Decline</Button>}
              {booking.status === 'confirmed' && (
                <Button onClick={() => setConfirming('cancel')}>Cancel booking</Button>
              )}
            </div>
          )}

          {decide.error instanceof ApiError && (
            <p role="alert" className="mt-2 rounded-lg bg-bad-50 px-3 py-2 text-sm text-bad-700">
              {decide.error.message}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}
