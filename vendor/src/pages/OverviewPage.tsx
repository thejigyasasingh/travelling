import { Link } from 'react-router-dom'
import { useArrivals, useDashboard, useMe } from '@/api/queries'
import { PageHeader } from '@/app/Shell'
import { formatCompactMoney, formatDate, formatMinor } from '@/core/format'
import { Card, EmptyRow, Spinner, StatusBadge } from '@/ui/primitives'

/**
 * What needs doing, and how the month is going.
 *
 * Ordered by urgency rather than by category: the things a guest is waiting on
 * come first, then the money, then the operational list. A host opens this
 * between other work and should be able to close it again in ten seconds if the
 * answer is "nothing".
 */
export function OverviewPage() {
  const { data, isPending } = useDashboard()
  const { data: me } = useMe()
  const { data: arrivals } = useArrivals(7)

  if (isPending || !data) {
    return (
      <div className="grid place-items-center py-20">
        <Spinner />
      </div>
    )
  }

  const needsYou = data.awaiting_approval + data.reviews_awaiting

  return (
    <>
      <PageHeader
        title={me?.display_name ? `Hello, ${me.display_name}` : 'Overview'}
        description={
          needsYou === 0
            ? 'Nothing is waiting on you.'
            : `${needsYou} thing${needsYou === 1 ? '' : 's'} waiting on you.`
        }
      />

      {/* Waiting on the host */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile
          label="Booking requests"
          value={data.awaiting_approval}
          tone={data.awaiting_approval > 0 ? 'warn' : 'quiet'}
          to="/bookings?status=pending_approval"
          hint="Guests waiting for an answer"
        />
        <Tile
          label="Reviews to answer"
          value={data.reviews_awaiting}
          tone={data.reviews_awaiting > 0 ? 'warn' : 'quiet'}
          to="/reviews?awaiting_reply=true"
          hint="A reply is public and permanent"
        />
        <Tile
          label="Arriving this week"
          value={data.arrivals_this_week}
          tone="quiet"
          to="/bookings"
        />
        <Tile label="Guests in stay" value={data.in_stay} tone="quiet" to="/bookings?status=in_stay" />
      </div>

      {/* The money. Net first — it is the number that reaches the bank. */}
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <Card title="Last 30 days" className="lg:col-span-2">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Figure
              label="Yours"
              value={formatCompactMoney(data.net_30d_minor)}
              emphasis
              hint="After commission"
            />
            <Figure label="Booked" value={formatCompactMoney(data.gross_30d_minor)} />
            <Figure
              label="Commission"
              value={formatCompactMoney(data.commission_30d_minor)}
              hint={me ? `${(me.commission_bps / 100).toFixed(1)}% of accommodation` : undefined}
            />
          </dl>
          <p className="mt-3 text-xs text-ink-500">
            Booked value, not money received — a stay in December is counted the day it is booked.{' '}
            <Link to="/revenue" className="text-brand-700 underline">
              Payout statement
            </Link>
          </p>
        </Card>

        <Card title="Listings">
          <dl className="space-y-2 text-sm">
            <Row label="Live" value={data.live_listings} />
            <Row label="In review" value={data.in_review} />
          </dl>
          <Link to="/properties" className="mt-3 inline-block text-sm text-brand-700 underline">
            Manage listings
          </Link>
        </Card>
      </div>

      {/* The operational list */}
      <Card title="Arriving in the next 7 days" className="mt-4">
        <div className="-mx-4 overflow-x-auto sm:mx-0">
          <table className="w-full min-w-[36rem] text-sm">
            <thead>
              <tr className="border-b border-ink-100 text-left text-xs text-ink-500">
                <th className="px-4 py-2 font-medium sm:px-0">Guest</th>
                <th className="px-4 py-2 font-medium">Property</th>
                <th className="px-4 py-2 font-medium">Check-in</th>
                <th className="px-4 py-2 font-medium">Nights</th>
                <th className="px-4 py-2 text-right font-medium">Value</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {arrivals?.length === 0 && <EmptyRow colSpan={6} message="Nobody arriving this week." />}
              {arrivals?.map((arrival) => (
                <tr key={arrival.booking_id} className="border-b border-ink-50 last:border-0">
                  <td className="px-4 py-2 sm:px-0">
                    <p className="font-medium text-ink-900">{arrival.guest_name}</p>
                    <p className="text-xs text-ink-500">{arrival.reference}</p>
                  </td>
                  <td className="px-4 py-2 text-ink-600">
                    <p>{arrival.property_name}</p>
                    <p className="text-xs text-ink-500">{arrival.room_type_name}</p>
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap text-ink-600">
                    {formatDate(arrival.check_in)}
                  </td>
                  <td className="px-4 py-2 text-ink-600">{nights(arrival.check_in, arrival.check_out)}</td>
                  <td className="px-4 py-2 text-right tabular-nums text-ink-900">
                    {formatMinor(arrival.total_minor, arrival.currency)}
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={arrival.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

/** Both dates are plain `YYYY-MM-DD`, and the range is half-open, so this is
 *  whole days without a timezone anywhere near it. */
function nights(checkIn: string, checkOut: string): number {
  const ms = Date.parse(`${checkOut}T00:00:00Z`) - Date.parse(`${checkIn}T00:00:00Z`)
  return Math.max(0, Math.round(ms / 86_400_000))
}

function Tile({
  label,
  value,
  tone,
  to,
  hint,
}: {
  label: string
  value: number
  tone: 'warn' | 'quiet'
  to: string
  hint?: string | undefined
}) {
  return (
    <Link
      to={to}
      className={
        tone === 'warn'
          ? 'rounded-xl border border-warn-200 bg-warn-50 p-4 transition-colors hover:bg-warn-100'
          : 'rounded-xl border border-ink-200 bg-white p-4 transition-colors hover:bg-ink-50'
      }
    >
      <p className={tone === 'warn' ? 'text-xs text-warn-700' : 'text-xs text-ink-500'}>{label}</p>
      <p
        className={
          tone === 'warn'
            ? 'mt-1 text-2xl font-semibold text-warn-700'
            : 'mt-1 text-2xl font-semibold text-ink-900'
        }
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-ink-500">{hint}</p>}
    </Link>
  )
}

function Figure({
  label,
  value,
  hint,
  emphasis = false,
}: {
  label: string
  value: string
  hint?: string | undefined
  emphasis?: boolean
}) {
  return (
    <div>
      <dt className="text-xs text-ink-500">{label}</dt>
      <dd
        className={
          emphasis
            ? 'mt-1 text-2xl font-semibold text-ink-900'
            : 'mt-1 text-xl font-medium text-ink-700'
        }
      >
        {value}
      </dd>
      {hint && <p className="text-xs text-ink-500">{hint}</p>}
    </div>
  )
}

function Row({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-ink-600">{label}</dt>
      <dd className="font-medium tabular-nums text-ink-900">{value}</dd>
    </div>
  )
}
