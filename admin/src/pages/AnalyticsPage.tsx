import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAnalytics } from '@/api/queries'
import { PageHeader } from '@/app/Shell'
import { Card } from '@/ui/primitives'
import { formatCompactMoney, formatDate, formatMinor, formatNumber } from '@/core/format'

const SLICE_COLOURS = ['#4f46e5', '#0f766e', '#b45309', '#be123c', '#7c3aed']

/** Indexing a fixed palette is `string | undefined` under
 *  `noUncheckedIndexedAccess`; the modulo makes it total, so the fallback never
 *  runs and exists only to say so to the compiler. */
function sliceColour(index: number): string {
  return SLICE_COLOURS[index % SLICE_COLOURS.length] ?? '#4f46e5'
}

/**
 * Analytics.
 *
 * The revenue waterfall is the important part, and it is deliberately shown as
 * a **breakdown rather than a single number**. "Revenue: ₹50L" is the number
 * everyone quotes and nobody can act on; gross, minus refunds, minus the
 * gateway's cut, minus commission, leaving what vendors are owed — that is the
 * shape someone can reconcile against a bank statement.
 *
 * Fees and commission come from the payment ledger rather than being
 * recomputed from percentages, so this page and the settlement report cannot
 * disagree.
 */
export function AnalyticsPage() {
  const [range, setRange] = useState<{ from?: string; to?: string }>({})
  const { data, isPending, error } = useAnalytics(range.from, range.to)

  const waterfall = data
    ? [
        { name: 'Gross', value: data.revenue.gross_minor },
        { name: 'Refunds', value: -data.revenue.refunded_minor },
        { name: 'Gateway fees', value: -data.revenue.gateway_fees_minor },
        { name: 'Commission', value: -data.revenue.platform_commission_minor },
        { name: 'Vendor payable', value: data.revenue.vendor_payable_minor },
      ]
    : []

  const typeSlices = Object.entries(data?.by_property_type ?? {}).map(([name, value]) => ({
    name,
    value,
  }))

  return (
    <>
      <PageHeader
        title="Analytics"
        description={
          data
            ? `${formatDate(data.revenue.from_date)} – ${formatDate(data.revenue.to_date)}`
            : 'Revenue and demand'
        }
        action={
          <div className="flex items-center gap-2 text-xs text-ink-500">
            <label className="flex items-center gap-1">
              From
              <input
                type="date"
                value={range.from ?? ''}
                onChange={(event) => setRange((r) => ({ ...r, from: event.target.value }))}
                className="h-9 rounded-lg border border-ink-200 px-2 text-sm"
              />
            </label>
            <label className="flex items-center gap-1">
              To
              <input
                type="date"
                value={range.to ?? ''}
                onChange={(event) => setRange((r) => ({ ...r, to: event.target.value }))}
                className="h-9 rounded-lg border border-ink-200 px-2 text-sm"
              />
            </label>
          </div>
        }
      />

      {error ? (
        <Card className="p-6 text-sm text-bad-700">
          Could not load analytics. Revenue reporting needs payment access.
        </Card>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Stat label="Gross bookings" value={data ? formatCompactMoney(data.revenue.gross_minor) : '—'} loading={isPending} />
            <Stat label="Net of refunds" value={data ? formatCompactMoney(data.revenue.net_minor) : '—'} loading={isPending} />
            <Stat
              label="Owed to vendors"
              value={data ? formatCompactMoney(data.revenue.vendor_payable_minor) : '—'}
              loading={isPending}
            />
            <Stat
              label="Discounts given"
              value={data ? formatCompactMoney(data.coupon_cost_minor) : '—'}
              loading={isPending}
            />
            <Stat
              label="Average booking"
              value={data ? formatMinor(data.average_booking_value_minor, 'INR', { compact: true }) : '—'}
              loading={isPending}
            />
            <Stat
              label="Cancellation rate"
              value={data ? `${data.cancellation_rate.toFixed(1)}%` : '—'}
              loading={isPending}
            />
            <Stat
              label="Booking lead time"
              value={data ? `${data.average_lead_time_days.toFixed(0)} days` : '—'}
              loading={isPending}
            />
            <Stat
              label="Occupancy"
              value={data ? `${data.occupancy_percent.toFixed(1)}%` : '—'}
              hint="Across managed inventory only"
              loading={isPending}
            />
          </div>

          <Card title="Where the money goes">
            <div className="h-64 p-3">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={waterfall}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    width={60}
                    tickFormatter={(v) => formatCompactMoney(Number(v))}
                  />
                  <Tooltip formatter={(v) => formatMinor(Number(v))} />
                  <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                    {waterfall.map((entry) => (
                      <Cell
                        key={entry.name}
                        // Outflows in red, so the shape is readable without
                        // reading the axis.
                        fill={entry.value < 0 ? '#be123c' : '#0f766e'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Revenue trend">
              <div className="h-56 p-3">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data?.revenue_by_day ?? []}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} tickFormatter={(v) => dayLabel(v).slice(8)} />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      width={56}
                      tickFormatter={(v) => formatCompactMoney(Number(v))}
                    />
                    <Tooltip
                      labelFormatter={(v) => formatDate(dayLabel(v))}
                      formatter={(v) => formatMinor(Number(v))}
                    />
                    <Line dataKey="value" stroke="#4f46e5" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card title="Bookings by property type">
              <div className="h-56 p-3">
                {typeSlices.length === 0 ? (
                  <p className="grid h-full place-items-center text-sm text-ink-500">
                    Nothing booked in this window
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={typeSlices} dataKey="value" nameKey="name" outerRadius={70} label>
                        {typeSlices.map((slice, index) => (
                          <Cell key={slice.name} fill={sliceColour(index)} />
                        ))}
                      </Pie>
                      <Legend />
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Top cities">
              <ul className="divide-y divide-ink-100">
                {(data?.by_city ?? []).map((city) => (
                  <li key={city.city} className="flex justify-between px-4 py-2 text-sm">
                    <span className="text-ink-700">
                      {city.city}
                      <span className="ml-1.5 text-xs text-ink-400">
                        {formatNumber(city.bookings)} bookings
                      </span>
                    </span>
                    <span className="tabular font-medium">
                      {formatCompactMoney(city.revenue_minor)}
                    </span>
                  </li>
                ))}
                {!isPending && (data?.by_city.length ?? 0) === 0 && (
                  <li className="px-4 py-6 text-center text-sm text-ink-500">No data</li>
                )}
              </ul>
            </Card>

            <Card title="Top properties">
              <ul className="divide-y divide-ink-100">
                {(data?.top_properties ?? []).map((property) => (
                  <li key={property.property_id} className="flex justify-between px-4 py-2 text-sm">
                    <span className="min-w-0 truncate text-ink-700">
                      {property.name}
                      <span className="ml-1.5 text-xs text-ink-400">{property.city}</span>
                    </span>
                    <span className="tabular ml-2 font-medium whitespace-nowrap">
                      {formatCompactMoney(property.revenue_minor)}
                    </span>
                  </li>
                ))}
                {!isPending && (data?.top_properties.length ?? 0) === 0 && (
                  <li className="px-4 py-6 text-center text-sm text-ink-500">No data</li>
                )}
              </ul>
            </Card>
          </div>

          <p className="text-xs text-ink-500">
            Gateway fees and commission come from the payment ledger, not from
            recomputed percentages — so these figures reconcile against the
            settlement report rather than approximating it. Tax collected in
            this period: {data ? formatMinor(data.revenue.tax_collected_minor) : '—'}.
          </p>
        </div>
      )}
    </>
  )
}

function Stat({
  label,
  value,
  hint,
  loading,
}: {
  label: string
  value: string
  hint?: string
  loading?: boolean
}) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className="tabular mt-1 text-xl font-semibold text-ink-900">
        {loading ? <span className="inline-block h-6 w-20 animate-pulse rounded bg-ink-100" /> : value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-ink-400">{hint}</p>}
    </Card>
  )
}

/** Recharts types axis values loosely. Our day axis is always `yyyy-MM-dd`, so
 *  this narrows rather than stringifying something that could be an object. */
function dayLabel(value: unknown): string {
  return typeof value === 'string' ? value : ''
}
