import { useState } from 'react'
import { useEarnings, useMe } from '@/api/queries'
import { PageHeader } from '@/app/Shell'
import { formatDate, formatMinor, formatNumber } from '@/core/format'
import { Card, Spinner } from '@/ui/primitives'

/**
 * What the host is owed, and how it was arrived at.
 *
 * Shown as a subtraction rather than a set of tiles. A host reconciling this
 * against their bank statement needs to see gross minus commission minus
 * refunds minus tax reach the number that was transferred — five separate
 * figures they have to combine themselves is how a support ticket starts.
 *
 * Tax is *collected*, not earned: it is remitted to the government. It appears
 * in the subtraction so the arithmetic closes, and is labelled so nobody counts
 * it as income.
 */
export function RevenuePage() {
  const [range, setRange] = useState(() => lastDays(30))
  const { data, isPending } = useEarnings(range.from, range.to)
  const { data: me } = useMe()

  return (
    <>
      <PageHeader
        title="Revenue"
        description="What you have earned, and what will be transferred."
        action={
          <div className="flex flex-wrap gap-2">
            {[
              { label: '30 days', days: 30 },
              { label: '90 days', days: 90 },
              { label: '12 months', days: 365 },
            ].map((option) => (
              <button
                key={option.days}
                type="button"
                onClick={() => setRange(lastDays(option.days))}
                className={
                  range.days === option.days
                    ? 'rounded-lg bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700'
                    : 'rounded-lg px-3 py-1.5 text-sm text-ink-600 hover:bg-ink-100'
                }
              >
                {option.label}
              </button>
            ))}
          </div>
        }
      />

      {isPending || !data ? (
        <div className="grid place-items-center py-20">
          <Spinner />
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <Card title={`${formatDate(data.from_date)} — ${formatDate(data.to_date)}`}>
            <dl className="divide-y divide-ink-100">
              <Line
                label="Booked"
                hint={`${formatNumber(data.bookings)} booking${data.bookings === 1 ? '' : 's'}, ${formatNumber(data.nights_sold)} nights`}
                value={formatMinor(data.gross_minor, data.currency)}
              />
              <Line
                label="Platform commission"
                hint={me ? `${(me.commission_bps / 100).toFixed(1)}% of accommodation` : undefined}
                value={`− ${formatMinor(data.commission_minor, data.currency)}`}
                negative
              />
              <Line
                label="Refunds issued"
                hint="Counted in the period the refund went out, not when the booking was made"
                value={`− ${formatMinor(data.refunded_minor, data.currency)}`}
                negative
              />
              <Line
                label="Tax collected"
                hint="Remitted to the government — collected on your behalf, not earned"
                value={`− ${formatMinor(data.tax_collected_minor, data.currency)}`}
                negative
              />
              <Line
                label="Yours"
                value={formatMinor(data.net_payable_minor, data.currency)}
                emphasis
              />
            </dl>
          </Card>

          <div className="space-y-4">
            <Card title="Averages">
              <dl className="space-y-3 px-4 py-3">
                <Small
                  label="Per booking"
                  value={formatMinor(data.average_booking_minor, data.currency)}
                />
                <Small
                  label="Per night"
                  value={formatMinor(data.average_nightly_minor, data.currency)}
                />
              </dl>
            </Card>

            <Card title="Payouts">
              <div className="px-4 py-3 text-sm">
                {me?.bank_account_last4 ? (
                  <>
                    <p className="text-ink-700">
                      Account ending{' '}
                      <span className="font-medium tabular-nums">{me.bank_account_last4}</span>
                    </p>
                    {me.bank_ifsc && <p className="mt-0.5 text-xs text-ink-500">{me.bank_ifsc}</p>}
                  </>
                ) : (
                  <p className="text-warn-700">
                    No bank account on file. Add one before your first payout.
                  </p>
                )}
                {me && !me.can_receive_payouts && (
                  <p className="mt-2 rounded-lg bg-warn-50 px-3 py-2 text-xs text-warn-700">
                    Payouts are paused on this account.
                  </p>
                )}
              </div>
            </Card>

            <p className="px-1 text-xs text-ink-500">
              These are figures for bookings <em>made</em> in the period. A stay in December booked
              today is counted today — which is how the statement and the transfer are calculated.
            </p>
          </div>
        </div>
      )}
    </>
  )
}

function Line({
  label,
  hint,
  value,
  negative = false,
  emphasis = false,
}: {
  label: string
  hint?: string | undefined
  value: string
  negative?: boolean
  emphasis?: boolean
}) {
  return (
    <div className="flex items-start justify-between gap-4 px-4 py-3">
      <div>
        <dt className={emphasis ? 'font-semibold text-ink-900' : 'text-ink-700'}>{label}</dt>
        {hint && <p className="mt-0.5 text-xs text-ink-500">{hint}</p>}
      </div>
      <dd
        className={
          emphasis
            ? 'text-xl font-semibold tabular-nums whitespace-nowrap text-ink-900'
            : negative
              ? 'tabular-nums whitespace-nowrap text-ink-500'
              : 'tabular-nums whitespace-nowrap text-ink-900'
        }
      >
        {value}
      </dd>
    </div>
  )
}

function Small({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-sm text-ink-600">{label}</dt>
      <dd className="font-medium tabular-nums text-ink-900">{value}</dd>
    </div>
  )
}

function lastDays(days: number): { from: string; to: string; days: number } {
  const now = Date.now()
  return {
    from: new Date(now - (days - 1) * 86_400_000).toISOString().slice(0, 10),
    to: new Date(now).toISOString().slice(0, 10),
    days,
  }
}
