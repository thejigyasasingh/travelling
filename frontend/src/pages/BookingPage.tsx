import { useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useProperty, useQuote } from '@/application/hooks/useCatalog'
import { useCreateBooking } from '@/application/hooks/useBookings'
import { useAuth } from '@/app/AuthProvider'
import { criteriaFromParams } from '@/application/hooks/useSearchParamsState'
import { cancellationPolicy, REFUND_FOOTNOTE } from '@/domain/policies'
import { formatMinor } from '@/core/money'
import { formatStay, nightsBetween, type IsoDate } from '@/core/dates'
import { hasErrorCode, ErrorCode, messageFor } from '@/core/errors'
import { Button } from '@/ui/Button'
import { Input, Textarea } from '@/ui/Field'
import { ErrorState, LoadingBlock } from '@/ui/feedback'

/**
 * Review and reserve.
 *
 * Two things make this page correct rather than merely working.
 *
 * **The idempotency key is minted once, when the page mounts** — not per click.
 * A guest who double-taps "Reserve", or whose phone retries on a flaky
 * connection, sends the same key twice and gets the same booking back. A key
 * generated inside the click handler would defeat the entire mechanism.
 *
 * **The quote total is sent with the booking.** The server re-prices and returns
 * 409 if it disagrees, which is handled here explicitly. Silently charging the
 * new price would be the wrong answer, and so would silently charging the old.
 */
export default function BookingPage() {
  const { propertyId } = useParams<{ propertyId: string }>()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { user } = useAuth()

  const criteria = criteriaFromParams(params)
  const roomTypeId = params.get('room_type') ?? ''
  const checkIn = criteria.checkIn
  const checkOut = criteria.checkOut
  const adults = criteria.adults ?? 2
  const children = criteria.children ?? 0
  const infants = criteria.infants ?? 0
  const rooms = criteria.rooms ?? 1

  const { data: property, isPending, isError, error } = useProperty(propertyId)
  const quoteQuery = useQuote(propertyId, {
    roomTypeId,
    ...(checkIn ? { checkIn } : {}),
    ...(checkOut ? { checkOut } : {}),
    adults,
    children,
    infants,
    rooms,
  })
  const createBooking = useCreateBooking()

  // One key for the lifetime of this page. See the note above.
  const [idempotencyKey] = useState(() => crypto.randomUUID())

  const [guestName, setGuestName] = useState(user?.fullName ?? '')
  const [guestEmail, setGuestEmail] = useState(user?.email ?? '')
  const [guestPhone, setGuestPhone] = useState(user?.phone ?? '')
  const [specialRequests, setSpecialRequests] = useState('')

  if (isPending) return <LoadingBlock label="Loading your booking" />
  if (isError || !property) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState error={error} />
      </div>
    )
  }

  if (!checkIn || !checkOut || !roomTypeId) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <h1 className="text-xl font-semibold text-ink-900">Choose your dates first</h1>
        <p className="mt-2 text-sm text-ink-500">
          We need a check-in date, a check-out date and a room to price your stay.
        </p>
        <Button className="mt-6" onClick={() => navigate(`/stays/${property.slug}`)}>
          Back to the stay
        </Button>
      </div>
    )
  }

  const room = property.roomTypes.find((r) => r.id === roomTypeId)
  const quote = quoteQuery.data
  const nights = nightsBetween(checkIn, checkOut)
  const policy = cancellationPolicy(property.cancellationPolicy)

  const priceChanged = hasErrorCode(createBooking.error, ErrorCode.PRICE_CHANGED)
  const soldOut = hasErrorCode(createBooking.error, ErrorCode.BOOKING_DATES_UNAVAILABLE)

  function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!quote || !property) return

    createBooking.mutate(
      {
        idempotencyKey,
        input: {
          propertyId: property.id,
          roomTypeId,
          checkIn: checkIn as IsoDate,
          checkOut: checkOut as IsoDate,
          adults,
          children,
          infants,
          rooms,
          guestName,
          guestEmail,
          guestPhone,
          ...(specialRequests ? { specialRequests } : {}),
          quotedTotalMinor: quote.totalMinor,
        },
      },
      {
        // The booking now holds real inventory on a timer, so the guest goes
        // straight to payment rather than to a page they might wander off from.
        onSuccess: (booking) => void navigate(`/checkout/${booking.id}`),
      },
    )
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold tracking-tight text-ink-900">Review and reserve</h1>

      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_360px]">
        <form onSubmit={submit} className="space-y-6">
          <section className="rounded-2xl border border-ink-100 p-5">
            <h2 className="font-semibold text-ink-900">Your stay</h2>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-500">Dates</dt>
                <dd className="font-medium text-ink-800">
                  {formatStay(checkIn, checkOut)} · {nights} night
                  {nights === 1 ? '' : 's'}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-500">Room</dt>
                <dd className="font-medium text-ink-800">{room?.name ?? '—'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-500">Guests</dt>
                <dd className="font-medium text-ink-800">
                  {adults} adult{adults === 1 ? '' : 's'}
                  {children > 0 && `, ${children} child${children === 1 ? '' : 'ren'}`}
                  {infants > 0 && `, ${infants} infant${infants === 1 ? '' : 's'}`} · {rooms} room
                  {rooms === 1 ? '' : 's'}
                </dd>
              </div>
            </dl>
          </section>

          <section className="rounded-2xl border border-ink-100 p-5">
            <h2 className="font-semibold text-ink-900">Guest details</h2>
            <p className="mt-1 text-sm text-ink-500">
              These go to the property. The name should match the ID the guest checks in with.
            </p>
            <div className="mt-4 space-y-4">
              <Input
                label="Full name"
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                autoComplete="name"
                required
              />
              <Input
                label="Email"
                type="email"
                value={guestEmail}
                onChange={(e) => setGuestEmail(e.target.value)}
                autoComplete="email"
                hint="Your confirmation and invoice go here."
                required
              />
              <Input
                label="Phone"
                type="tel"
                value={guestPhone}
                onChange={(e) => setGuestPhone(e.target.value)}
                autoComplete="tel"
                placeholder="+91 98765 43210"
                hint="The property may call about your arrival."
                required
              />
              <Textarea
                label="Anything the host should know?"
                value={specialRequests}
                onChange={(e) => setSpecialRequests(e.target.value)}
                rows={3}
                maxLength={500}
                placeholder="Late arrival, dietary needs, accessibility…"
                hint="Requests are passed on, not guaranteed."
              />
            </div>
          </section>

          {createBooking.isError && (
            <div role="alert" className="rounded-xl bg-danger-50 p-4">
              <p className="font-medium text-danger-700">
                {priceChanged
                  ? 'The price changed while you were booking'
                  : soldOut
                    ? 'Those dates just went'
                    : 'We could not hold that booking'}
              </p>
              <p className="mt-1 text-sm text-ink-600">
                {priceChanged
                  ? 'Rates for these dates were updated. Refresh to see the new total — you have not been charged.'
                  : soldOut
                    ? 'Someone else booked the last room for these dates. Try different dates or another room.'
                    : messageFor(createBooking.error)}
              </p>
              <div className="mt-3 flex gap-2">
                {(priceChanged || soldOut) && (
                  <Button variant="secondary" size="sm" onClick={() => void quoteQuery.refetch()}>
                    Refresh price
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => navigate(`/stays/${property.slug}`)}>
                  Back to the stay
                </Button>
              </div>
            </div>
          )}

          <Button
            type="submit"
            size="lg"
            fullWidth
            loading={createBooking.isPending}
            disabled={!quote?.isAvailable}
          >
            Reserve and pay
          </Button>
          <p className="text-center text-xs text-ink-500">
            Reserving holds your rooms for a short window while you pay.
          </p>
        </form>

        <aside>
          <div className="sticky top-24 rounded-2xl border border-ink-200 p-5 shadow-card">
            <h2 className="font-semibold text-ink-900">{property.name}</h2>
            <p className="mt-0.5 text-sm text-ink-500">{property.city}</p>

            {quoteQuery.isPending ? (
              <div className="mt-4 space-y-2">
                <div className="shimmer h-4 rounded" />
                <div className="shimmer h-4 rounded" />
                <div className="shimmer h-6 rounded" />
              </div>
            ) : quote ? (
              <dl className="mt-4 space-y-1.5 border-t border-ink-100 pt-4 text-sm">
                <Row
                  label={`${formatMinor(quote.averageNightlyMinor, quote.currency, { compact: true })} × ${nights} night${nights === 1 ? '' : 's'}`}
                  value={formatMinor(quote.accommodationMinor, quote.currency)}
                />
                {quote.extraGuestMinor > 0 && (
                  <Row label="Extra guests" value={formatMinor(quote.extraGuestMinor, quote.currency)} />
                )}
                {quote.cleaningFeeMinor > 0 && (
                  <Row label="Cleaning fee" value={formatMinor(quote.cleaningFeeMinor, quote.currency)} />
                )}
                <Row label="Taxes" value={formatMinor(quote.taxMinor, quote.currency)} />
                <div className="flex justify-between border-t border-ink-100 pt-2 text-base font-semibold text-ink-900">
                  <dt>Total</dt>
                  <dd className="tabular-nums">{formatMinor(quote.totalMinor, quote.currency)}</dd>
                </div>
              </dl>
            ) : null}

            <div className="mt-4 rounded-xl bg-ink-50 p-3">
              <p className="text-sm font-medium text-ink-800">{policy.label} cancellation</p>
              <p className="mt-1 text-xs text-ink-600">{policy.detail}</p>
              <p className="mt-1.5 text-xs text-ink-500">{REFUND_FOOTNOTE}</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-ink-600">
      <dt>{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  )
}
