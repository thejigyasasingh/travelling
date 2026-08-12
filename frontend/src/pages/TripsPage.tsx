import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useBookings } from '@/application/hooks/useBookings'
import { formatMinor } from '@/core/money'
import { formatStay, isPast } from '@/core/dates'
import { isActive, statusPresentation, type Booking } from '@/domain/booking'
import { Badge, EmptyState, ErrorState, Skeleton } from '@/ui/feedback'
import { ButtonLink } from '@/ui/Button'
import { cn } from '@/ui/cn'

type Tab = 'upcoming' | 'past' | 'all'

/**
 * Trips.
 *
 * Split into upcoming and past because the two are used for entirely different
 * things: upcoming is "where am I going and can I still change it", past is
 * "find me that invoice". A single reverse-chronological list serves neither.
 */
export default function TripsPage() {
  const [tab, setTab] = useState<Tab>('upcoming')
  const { data, isPending, isError, error, refetch } = useBookings()

  const all = data?.items ?? []
  const upcoming = all.filter((b) => isActive(b) && !isPast(b.checkOut))
  const past = all.filter((b) => !isActive(b) || isPast(b.checkOut))
  const shown = tab === 'upcoming' ? upcoming : tab === 'past' ? past : all

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold tracking-tight text-ink-900">My trips</h1>

      <div role="tablist" aria-label="Trip filter" className="mt-5 flex gap-1 border-b border-ink-100">
        {(
          [
            ['upcoming', `Upcoming${upcoming.length ? ` (${upcoming.length})` : ''}`],
            ['past', `Past${past.length ? ` (${past.length})` : ''}`],
            ['all', 'All'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn(
              '-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
              tab === value
                ? 'border-brand-600 text-brand-700'
                : 'border-transparent text-ink-500 hover:text-ink-800',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {isError ? (
          <ErrorState error={error} onRetry={() => void refetch()} />
        ) : isPending ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        ) : shown.length === 0 ? (
          <EmptyState
            title={tab === 'past' ? 'No past trips yet' : 'No trips booked yet'}
            description={
              tab === 'past'
                ? 'Completed stays and their invoices will show up here.'
                : 'When you book a stay it will appear here, with your confirmation and invoice.'
            }
            action={<ButtonLink to="/search">Find a stay</ButtonLink>}
          />
        ) : (
          <ul className="space-y-4">
            {shown.map((booking) => (
              <li key={booking.id}>
                <TripCard booking={booking} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function TripCard({ booking }: { booking: Booking }) {
  const status = statusPresentation(booking.status)
  const needsPayment = booking.status === 'pending_payment'

  return (
    <article className="relative rounded-2xl border border-ink-100 p-5 transition-shadow hover:shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate font-semibold text-ink-900">
            <Link to={`/trips/${booking.id}`} className="before:absolute before:inset-0">
              {booking.propertyName}
            </Link>
          </h2>
          <p className="mt-0.5 text-sm text-ink-500">
            {formatStay(booking.checkIn, booking.checkOut)} · {booking.nights} night
            {booking.nights === 1 ? '' : 's'} · {booking.roomTypeName}
          </p>
          <p className="mt-1 font-mono text-xs text-ink-400">{booking.reference}</p>
        </div>

        <div className="text-right">
          <Badge tone={status.tone}>{status.label}</Badge>
          <p className="mt-2 font-semibold text-ink-900">
            {formatMinor(booking.totalMinor, booking.currency, { compact: true })}
          </p>
        </div>
      </div>

      {needsPayment && (
        <div className="relative z-10 mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-warning-50 p-3">
          <p className="flex-1 text-sm text-warning-700">
            Payment pending — your rooms are held, but not for long.
          </p>
          <ButtonLink to={`/checkout/${booking.id}`} size="sm">
            Pay now
          </ButtonLink>
        </div>
      )}

      {booking.refund && (
        <p className="mt-3 text-sm text-ink-600">
          Refund of {formatMinor(booking.refund.amountMinor, booking.refund.currency)}{' '}
          {booking.refund.status === 'completed' ? 'has been issued' : 'is being processed'}.
        </p>
      )}
    </article>
  )
}
