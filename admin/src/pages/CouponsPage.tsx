import { useState } from 'react'
import { useCoupons, useCouponUsage, useCreateCoupon, useSetCouponStatus } from '@/api/queries'
import { useListFilters } from '@/app/useListFilters'
import { PageHeader } from '@/app/Shell'
import { DataTable, FilterBar, SearchInput, Select } from '@/ui/DataTable'
import type { Column } from '@/ui/DataTable'
import { Badge, Button, Card, StatusBadge } from '@/ui/primitives'
import { formatDate, formatMinor, formatNumber } from '@/core/format'
import { ApiError } from '@/core/http'
import type { Coupon } from '@/api/types'

/**
 * Coupons.
 *
 * The form enforces the same rule the server does — a percentage discount must
 * carry a cap — and says why. 25% off a ₹4,00,000 villa week is ₹1,00,000, and
 * nobody typing "25" is picturing that number. The server refuses it either
 * way; the form explains it before the refusal.
 */
export function CouponsPage() {
  const { filters, update } = useListFilters()
  const query = useCoupons(filters)
  const [creating, setCreating] = useState(false)
  const [inspecting, setInspecting] = useState<Coupon | null>(null)
  const setStatus = useSetCouponStatus()

  const columns: Column<Coupon>[] = [
    {
      key: 'code',
      header: 'Code',
      render: (row) => (
        <div className="min-w-0">
          <p className="font-mono text-sm font-semibold">{row.code}</p>
          <p className="truncate text-xs text-ink-500">{row.description}</p>
        </div>
      ),
    },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    {
      key: 'discount',
      header: 'Discount',
      render: (row) =>
        row.discount_type === 'percent' ? (
          <span>
            {(row.value / 100).toFixed(row.value % 100 === 0 ? 0 : 1)}%
            <span className="text-ink-400">
              {' '}
              max {formatMinor(row.max_discount_minor, 'INR', { compact: true })}
            </span>
          </span>
        ) : (
          formatMinor(row.value, 'INR', { compact: true })
        ),
    },
    {
      key: 'used',
      header: 'Used',
      numeric: true,
      // "12 / ∞" rather than "12 / 0": null means unlimited, and rendering that
      // as zero would read as an exhausted campaign.
      render: (row) => (
        <span>
          {formatNumber(row.redeemed_count)}
          <span className="text-ink-400"> / {row.total_limit === null ? '∞' : formatNumber(row.total_limit)}</span>
        </span>
      ),
    },
    {
      key: 'window',
      header: 'Runs',
      render: (row) => (
        <span className="text-xs whitespace-nowrap text-ink-500">
          {formatDate(row.starts_at)} → {formatDate(row.ends_at)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row) => (
        <span className="flex justify-end gap-1">
          <Button size="sm" onClick={() => setInspecting(row)}>
            Usage
          </Button>
          <Button
            size="sm"
            disabled={setStatus.isPending}
            onClick={() => setStatus.mutate({ id: row.id, active: row.status !== 'active' })}
          >
            {row.status === 'active' ? 'Pause' : 'Resume'}
          </Button>
        </span>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title="Coupons"
        description="Campaigns, their limits and what they have cost"
        action={
          <Button variant="primary" onClick={() => setCreating(true)}>
            New coupon
          </Button>
        }
      />
      <FilterBar>
        <SearchInput
          value={String(filters.q ?? '')}
          onChange={(q) => update({ q })}
          placeholder="Code"
        />
        <Select
          label="Status"
          value={String(filters.status ?? '')}
          onChange={(status) => update({ status })}
          options={[
            { value: '', label: 'All' },
            { value: 'active', label: 'Active' },
            { value: 'inactive', label: 'Paused' },
            { value: 'expired', label: 'Expired' },
          ]}
        />
      </FilterBar>

      <DataTable
        columns={columns}
        rows={query.data?.items ?? []}
        isLoading={query.isPending}
        isFetching={query.isFetching}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyMessage="No campaigns yet"
        page={query.data?.page}
        pages={query.data ? Math.max(1, Math.ceil(query.data.total / query.data.size)) : 1}
        total={query.data?.total}
        onPageChange={(page) => update({ page })}
        rowKey={(row) => row.id}
      />

      {creating && <CreateCouponForm onClose={() => setCreating(false)} />}
      {inspecting && <UsagePanel coupon={inspecting} onClose={() => setInspecting(null)} />}
    </>
  )
}

function CreateCouponForm({ onClose }: { onClose: () => void }) {
  const create = useCreateCoupon()
  const [type, setType] = useState<'percent' | 'flat'>('percent')
  const [form, setForm] = useState({
    code: '',
    description: '',
    value: '',
    max_discount: '',
    min_booking: '',
    total_limit: '',
    per_user_limit: '1',
    starts_at: new Date().toISOString().slice(0, 10),
    ends_at: '',
    first_booking_only: false,
  })

  const set = (key: keyof typeof form, value: string | boolean) =>
    setForm((current) => ({ ...current, [key]: value }))

  function submit(event: React.FormEvent) {
    event.preventDefault()
    create.mutate(
      {
        code: form.code,
        description: form.description,
        discount_type: type,
        // Percentages are basis points on the wire; the form takes a percentage
        // because that is what a human types.
        value: type === 'percent' ? Math.round(Number(form.value) * 100) : Math.round(Number(form.value) * 100),
        starts_at: new Date(form.starts_at).toISOString(),
        ends_at: new Date(form.ends_at).toISOString(),
        max_discount_minor: form.max_discount ? Math.round(Number(form.max_discount) * 100) : null,
        min_booking_minor: form.min_booking ? Math.round(Number(form.min_booking) * 100) : 0,
        total_limit: form.total_limit ? Number(form.total_limit) : null,
        per_user_limit: Number(form.per_user_limit || 1),
        first_booking_only: form.first_booking_only,
      },
      { onSuccess: onClose },
    )
  }

  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-ink-900/30 p-4" onClick={onClose}>
      <form
        onSubmit={submit}
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-lg space-y-3 rounded-xl bg-white p-5"
      >
        <h2 className="text-lg font-semibold text-ink-900">New coupon</h2>

        {create.error && (
          <p role="alert" className="rounded-lg bg-bad-50 p-3 text-sm text-bad-700">
            {create.error instanceof ApiError ? create.error.message : 'Could not create that coupon.'}
          </p>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Code" hint="Letters and digits. 0 and 1 are refused — they are misread as O and I.">
            <input
              value={form.code}
              onChange={(event) => set('code', event.target.value.toUpperCase())}
              required
              minLength={3}
              maxLength={24}
              className="h-9 w-full rounded-lg border border-ink-200 px-2 font-mono text-sm"
            />
          </Field>
          <Field label="Type">
            <select
              value={type}
              onChange={(event) => setType(event.target.value as 'percent' | 'flat')}
              className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
            >
              <option value="percent">Percentage</option>
              <option value="flat">Flat amount</option>
            </select>
          </Field>
          <Field label="Description" className="sm:col-span-2">
            <input
              value={form.description}
              onChange={(event) => set('description', event.target.value)}
              maxLength={200}
              className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
            />
          </Field>
          <Field label={type === 'percent' ? 'Percentage off' : 'Amount off (₹)'}>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={form.value}
              onChange={(event) => set('value', event.target.value)}
              required
              className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
            />
          </Field>
          <Field
            label="Maximum discount (₹)"
            hint={
              type === 'percent'
                ? 'Required. 25% of a ₹4,00,000 week is ₹1,00,000.'
                : 'Optional for a flat discount.'
            }
          >
            <input
              type="number"
              step="1"
              min="1"
              value={form.max_discount}
              onChange={(event) => set('max_discount', event.target.value)}
              required={type === 'percent'}
              className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
            />
          </Field>
          <Field label="Minimum booking (₹)">
            <input
              type="number"
              min="0"
              value={form.min_booking}
              onChange={(event) => set('min_booking', event.target.value)}
              className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
            />
          </Field>
          <Field label="Total redemptions" hint="Blank for unlimited.">
            <input
              type="number"
              min="1"
              value={form.total_limit}
              onChange={(event) => set('total_limit', event.target.value)}
              className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
            />
          </Field>
          <Field label="Per guest">
            <input
              type="number"
              min="1"
              value={form.per_user_limit}
              onChange={(event) => set('per_user_limit', event.target.value)}
              className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
            />
          </Field>
          <Field label="Starts">
            <input
              type="date"
              value={form.starts_at}
              onChange={(event) => set('starts_at', event.target.value)}
              required
              className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
            />
          </Field>
          <Field label="Ends">
            <input
              type="date"
              value={form.ends_at}
              onChange={(event) => set('ends_at', event.target.value)}
              required
              className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
            />
          </Field>
        </div>

        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={form.first_booking_only}
            onChange={(event) => set('first_booking_only', event.target.checked)}
          />
          First booking only
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={create.isPending}>
            {create.isPending ? 'Creating…' : 'Create'}
          </Button>
        </div>
      </form>
    </div>
  )
}

function UsagePanel({ coupon, onClose }: { coupon: Coupon; onClose: () => void }) {
  const { data, isPending } = useCouponUsage(coupon.id)

  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-ink-900/30 p-4" onClick={onClose}>
      <Card className="w-full max-w-sm p-5" >
        <div onClick={(event) => event.stopPropagation()}>
          <h2 className="font-mono text-lg font-semibold text-ink-900">{coupon.code}</h2>
          <p className="text-sm text-ink-500">{coupon.description}</p>

          {isPending ? (
            <p className="mt-4 text-sm text-ink-500">Loading…</p>
          ) : (
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-500">Redemptions</dt>
                <dd className="tabular font-medium">{formatNumber(data?.redemptions ?? 0)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-500">Released</dt>
                {/* Reported separately, never netted: a campaign report that
                    silently subtracts cancellations is one nobody can
                    reconcile against the ledger. */}
                <dd className="tabular font-medium">{formatNumber(data?.released ?? 0)}</dd>
              </div>
              <div className="flex justify-between border-t border-ink-100 pt-2">
                <dt className="text-ink-500">Discount given</dt>
                <dd className="tabular font-semibold">
                  {formatMinor(data?.discount_minor ?? 0)}
                </dd>
              </div>
            </dl>
          )}

          <div className="mt-4 flex flex-wrap gap-1.5">
            {coupon.first_booking_only && <Badge tone="brand">first booking only</Badge>}
            {coupon.min_booking_minor > 0 && (
              <Badge>min {formatMinor(coupon.min_booking_minor, 'INR', { compact: true })}</Badge>
            )}
            <Badge>{coupon.per_user_limit} per guest</Badge>
          </div>

          <Button className="mt-5 w-full" onClick={onClose}>
            Close
          </Button>
        </div>
      </Card>
    </div>
  )
}

function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string
  hint?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <label className={`block text-sm font-medium text-ink-700 ${className ?? ''}`}>
      {label}
      {children}
      {hint && <span className="mt-0.5 block text-xs font-normal text-ink-500">{hint}</span>}
    </label>
  )
}
