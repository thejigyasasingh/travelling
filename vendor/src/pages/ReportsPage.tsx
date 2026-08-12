import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useReports } from '@/api/queries'
import { PageHeader } from '@/app/Shell'
import { formatCompactMoney, formatDate, formatMinor, formatNumber } from '@/core/format'
import { Button, Card, EmptyRow, Spinner } from '@/ui/primitives'

/**
 * Everything, for a period.
 *
 * Assembled by the server in one request rather than by five parallel ones: the
 * figures have to agree with each other, and five queries issued at slightly
 * different moments do not. A host who sees a per-property table that does not
 * sum to the total above it stops trusting both.
 */
export function ReportsPage() {
  const [range, setRange] = useState(() => lastDays(90))
  const { data, isPending } = useReports(range.from, range.to)

  return (
    <>
      <PageHeader
        title="Reports"
        description="How each property did, month by month."
        action={
          <div className="flex flex-wrap items-center gap-2">
            {[30, 90, 365].map((days) => (
              <button
                key={days}
                type="button"
                onClick={() => setRange(lastDays(days))}
                className={
                  range.days === days
                    ? 'rounded-lg bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700'
                    : 'rounded-lg px-3 py-1.5 text-sm text-ink-600 hover:bg-ink-100'
                }
              >
                {days === 365 ? '12 months' : `${days} days`}
              </button>
            ))}
            {/* A plain link, not fetch-and-blob: the browser handles the
                download, and the Authorization header is not needed because
                the refresh cookie authenticates the navigation. */}
            <a href="/api/v1/vendor/reports/statement.csv" download>
              <Button size="sm">Download CSV</Button>
            </a>
          </div>
        }
      />

      {isPending || !data ? (
        <div className="grid place-items-center py-20">
          <Spinner />
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Tile label="Yours" value={formatCompactMoney(data.earnings.net_payable_minor)} emphasis />
            <Tile label="Booked" value={formatCompactMoney(data.earnings.gross_minor)} />
            <Tile label="Nights sold" value={formatNumber(data.earnings.nights_sold)} />
            <Tile
              label="Occupancy"
              value={`${data.occupancy.occupancy_percent.toFixed(1)}%`}
              hint="of nights you manage"
            />
          </div>

          <Card title="Bookings by day">
            {data.revenue_by_day.length === 0 ? (
              <p className="px-4 py-12 text-center text-sm text-ink-500">Nothing in this period.</p>
            ) : (
              <div className="h-64 px-2 py-3">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.revenue_by_day}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis
                      dataKey="day"
                      tickFormatter={(value: string) => value.slice(5)}
                      tick={{ fontSize: 11 }}
                      minTickGap={24}
                    />
                    <YAxis
                      tickFormatter={(value: number) => formatCompactMoney(value)}
                      tick={{ fontSize: 11 }}
                      width={64}
                    />
                    <Tooltip
                      formatter={(value) => formatMinor(Number(value))}
                      labelFormatter={(label) =>
                        typeof label === 'string' ? formatDate(label) : ''
                      }
                    />
                    <Bar dataKey="revenue_minor" fill="#0d9488" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          <Card title="By property">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] text-sm">
                <thead>
                  <tr className="border-b border-ink-100 text-left text-xs text-ink-500">
                    <th className="px-4 py-2 font-medium">Property</th>
                    <th className="px-4 py-2 font-medium">City</th>
                    <th className="px-4 py-2 text-right font-medium">Bookings</th>
                    <th className="px-4 py-2 text-right font-medium">Nights</th>
                    <th className="px-4 py-2 text-right font-medium">Booked</th>
                    <th className="px-4 py-2 text-right font-medium">Rating</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_property.length === 0 && (
                    <EmptyRow colSpan={6} message="No properties in this period." />
                  )}
                  {data.by_property.map((row) => (
                    <tr key={row.property_id} className="border-b border-ink-50 last:border-0">
                      <td className="px-4 py-2 font-medium text-ink-900">{row.name}</td>
                      <td className="px-4 py-2 text-ink-600">{row.city}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-ink-600">
                        {formatNumber(row.bookings)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-ink-600">
                        {formatNumber(row.nights_sold)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-ink-900">
                        {formatMinor(row.gross_minor)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-ink-600">
                        {row.review_count === 0
                          ? '—'
                          : `${row.review_average.toFixed(1)} (${row.review_count})`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Month by month">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[36rem] text-sm">
                <thead>
                  <tr className="border-b border-ink-100 text-left text-xs text-ink-500">
                    <th className="px-4 py-2 font-medium">Month</th>
                    <th className="px-4 py-2 text-right font-medium">Bookings</th>
                    <th className="px-4 py-2 text-right font-medium">Booked</th>
                    <th className="px-4 py-2 text-right font-medium">Commission</th>
                    <th className="px-4 py-2 text-right font-medium">Tax</th>
                    <th className="px-4 py-2 text-right font-medium">Yours</th>
                  </tr>
                </thead>
                <tbody>
                  {data.monthly.length === 0 && <EmptyRow colSpan={6} message="No months yet." />}
                  {data.monthly.map((row) => (
                    <tr key={row.month} className="border-b border-ink-50 last:border-0">
                      <td className="px-4 py-2 whitespace-nowrap text-ink-700">
                        {monthLabel(row.month)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-ink-600">
                        {formatNumber(row.bookings)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-ink-600">
                        {formatMinor(row.gross_minor)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-ink-500">
                        {formatMinor(row.commission_minor)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-ink-500">
                        {formatMinor(row.tax_minor)}
                      </td>
                      <td className="px-4 py-2 text-right font-medium tabular-nums text-ink-900">
                        {formatMinor(row.net_minor)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="border-t border-ink-100 px-4 py-2 text-xs text-ink-500">
              The CSV writes amounts in rupees with two decimals, so it reconciles against a bank
              statement without conversion.
            </p>
          </Card>
        </div>
      )}
    </>
  )
}

function Tile({
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
    <div className="rounded-xl border border-ink-200 bg-white p-4">
      <p className="text-xs text-ink-500">{label}</p>
      <p
        className={
          emphasis
            ? 'mt-1 text-2xl font-semibold text-ink-900'
            : 'mt-1 text-xl font-medium text-ink-800'
        }
      >
        {value}
      </p>
      {hint && <p className="text-xs text-ink-500">{hint}</p>}
    </div>
  )
}

function monthLabel(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-IN', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

function lastDays(days: number): { from: string; to: string; days: number } {
  const now = Date.now()
  return {
    from: new Date(now - (days - 1) * 86_400_000).toISOString().slice(0, 10),
    to: new Date(now).toISOString().slice(0, 10),
    days,
  }
}
