import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useDashboard } from '@/api/queries'
import { formatCompactMoney, formatDate, formatNumber, formatPercent } from '@/core/format'
import { PageHeader } from '@/app/Shell'
import { Card, cn } from '@/ui/primitives'
import type { Kpi } from '@/api/types'

/**
 * The landing screen.
 *
 * Two halves with different jobs. The **action queue** is a to-do list — it is
 * first because it is the only part someone can act on. The charts below are
 * context, and deliberately secondary: an admin panel whose front page is six
 * graphs is one where nobody notices the vendor waiting four days for approval.
 */
const ACTION_LABELS: Record<string, { label: string; to: string; urgent?: boolean }> = {
  vendors_pending: { label: 'Vendors awaiting review', to: '/vendors?status=pending' },
  properties_pending: { label: 'Listings awaiting review', to: '/properties?status=pending_review' },
  tickets_open: { label: 'Open tickets', to: '/tickets' },
  tickets_breaching: { label: 'Tickets past first-response target', to: '/tickets', urgent: true },
  refunds_pending: { label: 'Refunds to settle', to: '/payments' },
  payments_stuck: { label: 'Payments stuck over 30 min', to: '/payments?status=pending', urgent: true },
  notifications_failed: { label: 'Failed notifications', to: '/notifications?status=failed', urgent: true },
}

export function DashboardPage() {
  const { data, isPending, error } = useDashboard(30)

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={
          data ? `Last 30 days · generated ${formatDate(data.generated_at)}` : 'Last 30 days'
        }
      />

      {error ? (
        <Card className="p-6 text-sm text-bad-700">Could not load the dashboard.</Card>
      ) : (
        <div className="space-y-5">
          {/* ── needs a human ─────────────────────────────────────────── */}
          <Card title="Needs attention">
            <ul className="divide-y divide-ink-100">
              {Object.entries(ACTION_LABELS).map(([key, meta]) => {
                const count = data?.action_queue[key] ?? 0
                return (
                  <li key={key}>
                    <Link
                      to={meta.to}
                      className="flex items-center justify-between px-4 py-2.5 hover:bg-ink-50"
                    >
                      <span className="text-sm text-ink-700">{meta.label}</span>
                      <span
                        className={cn(
                          'rounded-full px-2 py-0.5 text-sm font-semibold tabular',
                          count === 0
                            ? 'text-ink-400'
                            : meta.urgent
                              ? 'bg-bad-50 text-bad-700'
                              : 'bg-warn-50 text-warn-700',
                        )}
                      >
                        {isPending ? '—' : formatNumber(count)}
                      </span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          </Card>

          {/* ── the numbers ───────────────────────────────────────────── */}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {(data?.kpis ?? []).map((kpi) => (
              <KpiTile key={kpi.key} kpi={kpi} />
            ))}
            {isPending &&
              Array.from({ length: 5 }, (_, i) => (
                <Card key={i} className="h-24 animate-pulse bg-ink-100" />
              ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Bookings per day">
              <div className="h-56 p-3">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data?.bookings_by_day ?? []}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} tickFormatter={shortDay} />
                    <YAxis tick={{ fontSize: 11 }} allowDecimals={false} width={28} />
                    <Tooltip labelFormatter={(v) => formatDate(dayLabel(v))} />
                    <Bar dataKey="value" fill="#4f46e5" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card title="Revenue per day">
              <div className="h-56 p-3">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data?.revenue_by_day ?? []}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} tickFormatter={shortDay} />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      width={52}
                      tickFormatter={(v) => formatCompactMoney(Number(v))}
                    />
                    <Tooltip
                      labelFormatter={(v) => formatDate(dayLabel(v))}
                      formatter={(v) => formatCompactMoney(Number(v))}
                    />
                    <Area dataKey="value" stroke="#0f766e" fill="#99f6e4" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Booking status mix">
              <ul className="divide-y divide-ink-100">
                {Object.entries(data?.booking_status_mix ?? {}).map(([status, count]) => (
                  <li key={status} className="flex justify-between px-4 py-2 text-sm">
                    <span className="text-ink-600">{status.replace(/_/g, ' ')}</span>
                    <span className="tabular font-medium">{formatNumber(count)}</span>
                  </li>
                ))}
                {!isPending && Object.keys(data?.booking_status_mix ?? {}).length === 0 && (
                  <li className="px-4 py-6 text-center text-sm text-ink-500">
                    No bookings in this window
                  </li>
                )}
              </ul>
            </Card>

            <Card title="Top properties by revenue">
              <ul className="divide-y divide-ink-100">
                {(data?.top_properties ?? []).map((property) => (
                  <li key={property.property_id} className="flex justify-between px-4 py-2 text-sm">
                    <span className="min-w-0 truncate text-ink-700">
                      {property.name}
                      <span className="ml-1 text-ink-400">{property.city}</span>
                    </span>
                    <span className="tabular ml-3 font-medium whitespace-nowrap">
                      {formatCompactMoney(property.revenue_minor, property.currency)}
                    </span>
                  </li>
                ))}
                {!isPending && (data?.top_properties.length ?? 0) === 0 && (
                  <li className="px-4 py-6 text-center text-sm text-ink-500">
                    Nothing booked in this window
                  </li>
                )}
              </ul>
            </Card>
          </div>
        </div>
      )}
    </>
  )
}

function KpiTile({ kpi }: { kpi: Kpi }) {
  const up = (kpi.change_percent ?? 0) > 0
  return (
    <Card className="p-4">
      <p className="text-xs font-medium text-ink-500">{kpi.label}</p>
      <p className="tabular mt-1 text-2xl font-semibold text-ink-900">
        {kpi.unit === 'money' ? formatCompactMoney(kpi.value) : formatNumber(kpi.value)}
      </p>
      {/* `null` is rendered as "no prior data", never as 0% — the two look
          identical on a tile and mean completely different things. */}
      <p
        className={cn(
          'mt-0.5 text-xs',
          kpi.change_percent === null
            ? 'text-ink-400'
            : up
              ? 'text-good-600'
              : 'text-bad-600',
        )}
      >
        {kpi.change_percent === null
          ? 'no prior period'
          : `${formatPercent(kpi.change_percent)} vs previous 30 days`}
      </p>
    </Card>
  )
}

function shortDay(value: unknown): string {
  return dayLabel(value).slice(8) // "2026-08-07" → "07"
}

/** Recharts types axis values loosely. Our day axis is always `yyyy-MM-dd`, so
 *  this narrows rather than stringifying something that could be an object. */
function dayLabel(value: unknown): string {
  return typeof value === 'string' ? value : ''
}
