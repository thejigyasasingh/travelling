import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useArrivals, useDashboard, useMe } from '@/api/queries'
import { PageHeader } from '@/app/Shell'
import { formatCompactMoney, formatDate, formatMinor } from '@/core/format'
import { Card, EmptyRow, Skeleton, StatusBadge, cn } from '@/ui/primitives'
import {
  ArrowRightIcon,
  BellIcon,
  BuildingIcon,
  KeyIcon,
  PlaneIcon,
  StarIcon,
  TrendUpIcon,
} from '@/ui/icons'

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
    // Skeletons in the shape of the real thing. A centred spinner throws the
    // layout away and rebuilds it a moment later, which reads as a jump on the
    // one screen a host opens twenty times a day.
    return (
      <>
        <PageHeader title="Overview" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[104px]" />
          ))}
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <Skeleton className="h-40 lg:col-span-2" />
          <Skeleton className="h-40" />
        </div>
        <Skeleton className="mt-4 h-64" />
      </>
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
          icon={<BellIcon className="size-[18px]" />}
          to="/bookings?status=pending_approval"
          hint="Guests waiting for an answer"
        />
        <Tile
          label="Reviews to answer"
          value={data.reviews_awaiting}
          tone={data.reviews_awaiting > 0 ? 'warn' : 'quiet'}
          icon={<StarIcon className="size-[18px]" />}
          to="/reviews?awaiting_reply=true"
          hint="A reply is public and permanent"
        />
        <Tile
          label="Arriving this week"
          value={data.arrivals_this_week}
          tone="quiet"
          icon={<PlaneIcon className="size-[18px]" />}
          to="/bookings"
          hint="Confirmed check-ins"
        />
        <Tile
          label="Guests in stay"
          value={data.in_stay}
          tone="quiet"
          icon={<KeyIcon className="size-[18px]" />}
          to="/bookings?status=in_stay"
          hint="On the property now"
        />
      </div>

      {/* The money. Net first — it is the number that reaches the bank. */}
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <Card
          title="Last 30 days"
          description="Booked value, not money received — a stay in December is counted the day it is booked."
          icon={<TrendUpIcon className="size-4" />}
          className="lg:col-span-2"
          action={
            <Link
              to="/revenue"
              className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:text-brand-800"
            >
              Payout statement
              <ArrowRightIcon className="size-3.5" />
            </Link>
          }
        >
          <div className="grid gap-3 p-4 sm:grid-cols-3">
            {/* The one figure that reaches the bank, and the second place the
                gradient is spent. Everything else on this card is context for
                it. */}
            <div className="brand-gradient rounded-lg p-3.5 text-white shadow-raised">
              <p className="text-xs font-medium text-white/75">Yours</p>
              <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
                {formatCompactMoney(data.net_30d_minor)}
              </p>
              <p className="mt-0.5 text-xs text-white/70">After commission</p>
            </div>
            <Figure label="Booked" value={formatCompactMoney(data.gross_30d_minor)} />
            <Figure
              label="Commission"
              value={formatCompactMoney(data.commission_30d_minor)}
              hint={me ? `${(me.commission_bps / 100).toFixed(1)}% of accommodation` : undefined}
            />
          </div>
        </Card>

        <Card title="Listings" icon={<BuildingIcon className="size-4" />}>
          <div className="p-4">
            <dl className="space-y-2.5 text-sm">
              <Row label="Live" value={data.live_listings} tone="good" />
              <Row label="In review" value={data.in_review} tone={data.in_review ? 'warn' : 'quiet'} />
            </dl>
            <Link
              to="/properties"
              className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800"
            >
              Manage listings
              <ArrowRightIcon className="size-3.5" />
            </Link>
          </div>
        </Card>
      </div>

      {/* The operational list */}
      <Card
        title="Arriving in the next 7 days"
        icon={<PlaneIcon className="size-4" />}
        className="mt-4"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead>
              <tr className="border-b border-ink-100 bg-ink-50/60 text-left text-xs text-ink-500">
                <th className="px-4 py-2.5 font-medium">Guest</th>
                <th className="px-4 py-2.5 font-medium">Property</th>
                <th className="px-4 py-2.5 font-medium">Check-in</th>
                <th className="px-4 py-2.5 text-right font-medium">Nights</th>
                <th className="px-4 py-2.5 text-right font-medium">Value</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {arrivals?.length === 0 && (
                <EmptyRow
                  colSpan={6}
                  message="Nobody arriving this week"
                  hint="Check-ins appear here seven days ahead."
                />
              )}
              {arrivals?.map((arrival) => (
                <tr
                  key={arrival.booking_id}
                  className="border-b border-ink-100 transition-colors last:border-0 hover:bg-ink-50/70"
                >
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-ink-900">{arrival.guest_name}</p>
                    <p className="font-mono text-xs text-ink-400">{arrival.reference}</p>
                  </td>
                  <td className="px-4 py-2.5 text-ink-600">
                    <p>{arrival.property_name}</p>
                    <p className="text-xs text-ink-400">{arrival.room_type_name}</p>
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap text-ink-600">
                    {formatDate(arrival.check_in)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-ink-600">
                    {nights(arrival.check_in, arrival.check_out)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-medium tabular-nums text-ink-900">
                    {formatMinor(arrival.total_minor, arrival.currency)}
                  </td>
                  <td className="px-4 py-2.5">
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
  icon,
}: {
  label: string
  value: number
  tone: 'warn' | 'quiet'
  to: string
  hint?: string | undefined
  icon?: ReactNode
}) {
  const warn = tone === 'warn'
  return (
    <Link
      to={to}
      className={cn(
        'group relative overflow-hidden rounded-xl p-4 ring-1 shadow-raised',
        'transition-all duration-150 hover:-translate-y-0.5 hover:shadow-floating',
        warn ? 'bg-warn-50 ring-warn-200' : 'bg-white ring-ink-200/70 hover:ring-ink-300',
      )}
    >
      {/* A bar along the top edge of anything that needs attention. Colour
          alone fails for a host with a colour vision deficiency; a bar that is
          present or absent does not. */}
      {warn && <span className="absolute inset-x-0 top-0 h-0.5 bg-warn-500" />}

      <div className="flex items-start justify-between gap-2">
        <p className={cn('text-xs font-medium', warn ? 'text-warn-700' : 'text-ink-500')}>
          {label}
        </p>
        {icon && (
          <span className={warn ? 'text-warn-500' : 'text-ink-300 transition-colors group-hover:text-ink-400'}>
            {icon}
          </span>
        )}
      </div>

      <p
        className={cn(
          'mt-2 text-3xl leading-none font-semibold tracking-tight tabular-nums',
          warn ? 'text-warn-700' : 'text-ink-900',
        )}
      >
        {value}
      </p>

      <div className="mt-2 flex items-center gap-1">
        {hint && (
          <p className={cn('text-xs', warn ? 'text-warn-700/80' : 'text-ink-500')}>{hint}</p>
        )}
        <ArrowRightIcon
          className={cn(
            'size-3.5 shrink-0 opacity-0 transition-all duration-150',
            'group-hover:translate-x-0.5 group-hover:opacity-100',
            warn ? 'text-warn-600' : 'text-ink-400',
          )}
        />
      </div>
    </Link>
  )
}

function Figure({
  label,
  value,
  hint,
}: {
  label: string
  value: string
  hint?: string | undefined
}) {
  return (
    <div className="rounded-lg bg-ink-50 p-3.5 ring-1 ring-ink-100">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-ink-800">
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-ink-500">{hint}</p>}
    </div>
  )
}

function Row({
  label,
  value,
  tone = 'quiet',
}: {
  label: string
  value: number
  tone?: 'good' | 'warn' | 'quiet'
}) {
  return (
    <div className="flex items-center justify-between">
      <dt className="flex items-center gap-2 text-ink-600">
        {/* A dot rather than a coloured number: the count is the data and
            should stay readable, while the state is the decoration. */}
        <span
          className={cn(
            'size-1.5 rounded-full',
            tone === 'good' ? 'bg-good-500' : tone === 'warn' ? 'bg-warn-500' : 'bg-ink-300',
          )}
        />
        {label}
      </dt>
      <dd className="font-semibold tabular-nums text-ink-900">{value}</dd>
    </div>
  )
}
