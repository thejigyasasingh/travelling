import { Link, useParams } from 'react-router-dom'
import { useBooking } from '@/application/hooks/useBookings'
import { formatMinor } from '@/core/money'
import { formatStay } from '@/core/dates'
import { statusPresentation } from '@/domain/booking'
import { Badge, ErrorState, LoadingBlock } from '@/ui/feedback'
import { Button, ButtonLink } from '@/ui/Button'

/**
 * The page after paying.
 *
 * It has to be honest about a genuine ambiguity: the webhook is what confirms a
 * booking, and it usually lands within a second or two of the payment — but not
 * always. So a booking still in `pending_payment` here is shown as *confirming*,
 * with a poll running (see `useBooking`), rather than as either confirmed (a
 * lie) or failed (also a lie, and one that invites a second payment).
 */
export default function BookingConfirmationPage() {
  const { bookingId } = useParams<{ bookingId: string }>()
  const { data: booking, isPending, isError, error, refetch } = useBooking(bookingId)

  if (isPending) return <LoadingBlock label="Loading your booking" />
  if (isError || !booking) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    )
  }

  const status = statusPresentation(booking.status)
  const settling = booking.status === 'pending_payment'
  const confirmed = booking.status === 'confirmed' || booking.status === 'pending_approval'

  return (
    <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
      <div className="text-center">
        {confirmed ? (
          <div className="mx-auto grid size-14 place-items-center rounded-full bg-success-50 text-success-700">
            <CheckIcon />
          </div>
        ) : (
          <div className="mx-auto size-14 animate-spin rounded-full border-4 border-ink-200 border-t-brand-600" />
        )}

        <h1 className="mt-5 text-2xl font-bold tracking-tight text-ink-900">
          {confirmed
            ? booking.status === 'pending_approval'
              ? 'Payment received — awaiting the host'
              : 'Your stay is confirmed'
            : 'Confirming your payment'}
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-ink-600">
          {settling
            ? 'Your payment went through and we are waiting on the final confirmation from the gateway. This page updates itself — there is nothing more to do, and you will not be charged twice.'
            : status.hint}
        </p>
      </div>

      <div className="mt-8 rounded-2xl border border-ink-100 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold text-ink-900">{booking.propertyName}</h2>
            <p className="mt-0.5 text-sm text-ink-500">{booking.roomTypeName}</p>
          </div>
          <Badge tone={status.tone}>{status.label}</Badge>
        </div>

        <dl className="mt-5 grid gap-4 sm:grid-cols-2">
          <Detail label="Booking reference" value={booking.reference} mono />
          <Detail label="Dates" value={formatStay(booking.checkIn, booking.checkOut)} />
          <Detail
            label="Guests"
            value={`${booking.adults + booking.children} in ${booking.rooms} room${booking.rooms === 1 ? '' : 's'}`}
          />
          <Detail label="Total paid" value={formatMinor(booking.totalMinor, booking.currency)} />
          {booking.invoiceNumber && <Detail label="Invoice" value={booking.invoiceNumber} mono />}
          {booking.propertyAddress && (
            <div className="sm:col-span-2">
              <Detail label="Address" value={booking.propertyAddress} />
            </div>
          )}
        </dl>

        <p className="mt-5 text-sm text-ink-500">
          A confirmation has been emailed to {booking.guestEmail}.
        </p>
      </div>

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <ButtonLink to={`/trips/${booking.id}`}>View this trip</ButtonLink>
        <ButtonLink to="/trips" variant="secondary">
          All my trips
        </ButtonLink>
        {settling && (
          <Button variant="ghost" onClick={() => void refetch()}>
            Refresh
          </Button>
        )}
      </div>

      <p className="mt-8 text-center text-xs text-ink-500">
        Need to change something?{' '}
        <Link to={`/trips/${booking.id}`} className="text-brand-600 hover:underline">
          Manage this booking
        </Link>
      </p>
    </div>
  )
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-500">{label}</dt>
      <dd className={`mt-0.5 text-sm text-ink-900 ${mono ? 'font-mono' : ''}`}>{value}</dd>
    </div>
  )
}

function CheckIcon() {
  return (
    <svg className="size-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
      <path d="m5 13 4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
