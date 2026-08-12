import { useState } from 'react'
import {
  useApproveVendor,
  useBeginVendorReview,
  useRejectVendor,
  useSuspendVendor,
  useVendor,
  useVendors,
} from '@/api/queries'
import { useListFilters } from '@/app/useListFilters'
import { PageHeader } from '@/app/Shell'
import { DataTable, FilterBar, SearchInput, Select } from '@/ui/DataTable'
import type { Column } from '@/ui/DataTable'
import { Badge, Button, StatusBadge } from '@/ui/primitives'
import { formatBps, formatDate, formatMinor, formatNumber } from '@/core/format'
import { ApiError } from '@/core/http'
import type { AdminVendor } from '@/api/types'

/**
 * Vendor management.
 *
 * Approval is a gate on **money**, not on visibility — an approved vendor can
 * publish listings and be paid — so every decision here asks for a reason and
 * records who made it. The reason field on reject and suspend is required by
 * the server, not merely by this form: a rejection the applicant cannot act on
 * is one support cannot defend three months later.
 */
export function VendorsPage() {
  const { filters, update } = useListFilters({ status: 'pending' })
  const query = useVendors(filters)
  const [selected, setSelected] = useState<string | null>(null)

  const columns: Column<AdminVendor>[] = [
    {
      key: 'vendor',
      header: 'Vendor',
      render: (row) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{row.legal_name}</p>
          <p className="truncate text-xs text-ink-500">{row.contact_email}</p>
        </div>
      ),
    },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    {
      key: 'listings',
      header: 'Listings',
      numeric: true,
      render: (row) => (
        <span>
          {formatNumber(row.published_count)}
          <span className="text-ink-400"> / {formatNumber(row.property_count)}</span>
        </span>
      ),
    },
    {
      key: 'gross',
      header: 'Gross bookings',
      numeric: true,
      render: (row) => formatMinor(row.gross_bookings_minor, row.currency, { compact: true }),
    },
    { key: 'commission', header: 'Commission', numeric: true, render: (row) => formatBps(row.commission_bps) },
    {
      key: 'applied',
      header: 'Applied',
      render: (row) => <span className="text-xs text-ink-500">{formatDate(row.created_at)}</span>,
    },
    {
      key: 'action',
      header: '',
      render: (row) => (
        <Button size="sm" onClick={() => setSelected(row.id)}>
          Review
        </Button>
      ),
    },
  ]

  return (
    <>
      <PageHeader title="Vendors" description="Applications, approvals and suspensions" />
      <FilterBar>
        <SearchInput
          value={String(filters.q ?? '')}
          onChange={(q) => update({ q })}
          placeholder="Legal name or email"
        />
        <Select
          label="Status"
          value={String(filters.status ?? '')}
          onChange={(status) => update({ status })}
          options={[
            { value: '', label: 'All' },
            { value: 'pending', label: 'Pending' },
            { value: 'under_review', label: 'Under review' },
            { value: 'approved', label: 'Approved' },
            { value: 'rejected', label: 'Rejected' },
            { value: 'suspended', label: 'Suspended' },
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
        emptyMessage="No vendors match those filters"
        page={query.data?.meta.page}
        pages={query.data?.meta.pages}
        total={query.data?.meta.total}
        onPageChange={(page) => update({ page })}
        rowKey={(row) => row.id}
      />

      {selected && <VendorReviewPanel vendorId={selected} onClose={() => setSelected(null)} />}
    </>
  )
}

function VendorReviewPanel({ vendorId, onClose }: { vendorId: string; onClose: () => void }) {
  const { data: vendor, isPending } = useVendor(vendorId)
  const approve = useApproveVendor()
  const reject = useRejectVendor()
  const suspend = useSuspendVendor()
  const beginReview = useBeginVendorReview()

  const [reason, setReason] = useState('')
  const [commission, setCommission] = useState('')

  const busy =
    approve.isPending || reject.isPending || suspend.isPending || beginReview.isPending
  const error = approve.error ?? reject.error ?? suspend.error ?? beginReview.error

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-900/30" onClick={onClose}>
      <aside
        className="h-full w-full max-w-md overflow-y-auto bg-white p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        {isPending || !vendor ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : (
          <>
            <header className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-ink-900">{vendor.legal_name}</h2>
                <p className="text-sm text-ink-500">{vendor.contact_email}</p>
              </div>
              <StatusBadge status={vendor.status} />
            </header>

            <dl className="mt-5 space-y-2 text-sm">
              <Row label="Trading as" value={vendor.display_name} />
              <Row label="Phone" value={vendor.contact_phone} />
              <Row label="GSTIN" value={vendor.gstin ?? '—'} mono />
              <Row label="PAN" value={vendor.pan ?? '—'} mono />
              <Row
                label="Payout account"
                value={
                  vendor.bank_account_last4
                    ? `···· ${vendor.bank_account_last4} · ${vendor.bank_ifsc ?? ''}`
                    : 'Not provided'
                }
                mono
              />
              <Row label="Commission" value={formatBps(vendor.commission_bps)} />
              <Row label="Listings" value={`${vendor.published_count} live of ${vendor.property_count}`} />
              <Row
                label="Gross bookings"
                value={formatMinor(vendor.gross_bookings_minor, vendor.currency)}
              />
            </dl>

            <div className="mt-4 flex flex-wrap gap-2">
              {vendor.can_publish ? (
                <Badge tone="good">can publish</Badge>
              ) : (
                <Badge tone="warn">cannot publish</Badge>
              )}
              {vendor.can_receive_payouts ? (
                <Badge tone="good">payouts enabled</Badge>
              ) : (
                <Badge tone="warn">payouts blocked</Badge>
              )}
            </div>

            {!vendor.pan && (
              <p className="mt-3 rounded-lg bg-warn-50 p-3 text-xs text-warn-700">
                No PAN on file. Approval is refused without one — it is what TDS
                is filed against, and a payout to a vendor without it is a
                payable finance cannot legally settle.
              </p>
            )}

            {vendor.rejection_reason && (
              <p className="mt-3 rounded-lg bg-bad-50 p-3 text-xs text-bad-700">
                Rejected: {vendor.rejection_reason}
              </p>
            )}
            {vendor.suspension_reason && (
              <p className="mt-3 rounded-lg bg-bad-50 p-3 text-xs text-bad-700">
                Suspended: {vendor.suspension_reason}
              </p>
            )}

            {error && (
              <p role="alert" className="mt-3 rounded-lg bg-bad-50 p-3 text-xs text-bad-700">
                {error instanceof ApiError ? error.message : 'That action failed.'}
              </p>
            )}

            <div className="mt-5 space-y-3 border-t border-ink-100 pt-4">
              {vendor.status === 'pending' && (
                <Button
                  className="w-full"
                  disabled={busy}
                  onClick={() => beginReview.mutate({ id: vendor.id })}
                >
                  Claim for review
                </Button>
              )}

              {(vendor.status === 'pending' ||
                vendor.status === 'under_review' ||
                vendor.status === 'suspended') && (
                <>
                  <label className="block text-sm font-medium text-ink-700">
                    Commission (basis points)
                    <input
                      type="number"
                      min={0}
                      max={3000}
                      value={commission}
                      onChange={(event) => setCommission(event.target.value)}
                      placeholder={String(vendor.commission_bps)}
                      className="mt-1 h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
                    />
                    <span className="mt-1 block text-xs text-ink-500">
                      1500 = 15%. Leave blank to keep the current rate.
                    </span>
                  </label>
                  <Button
                    variant="primary"
                    className="w-full"
                    disabled={busy || !vendor.pan}
                    onClick={() =>
                      approve.mutate(
                        {
                          id: vendor.id,
                          ...(commission ? { commissionBps: Number(commission) } : {}),
                        },
                        { onSuccess: onClose },
                      )
                    }
                  >
                    Approve
                  </Button>
                </>
              )}

              <label className="block text-sm font-medium text-ink-700">
                Reason
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  rows={2}
                  className="mt-1 w-full rounded-lg border border-ink-200 px-2 py-1.5 text-sm"
                  placeholder="Required to reject or suspend"
                />
              </label>

              <div className="flex gap-2">
                {vendor.status !== 'rejected' && (
                  <Button
                    variant="danger"
                    className="flex-1"
                    disabled={busy || reason.trim().length < 3}
                    onClick={() =>
                      reject.mutate({ id: vendor.id, reason }, { onSuccess: onClose })
                    }
                  >
                    Reject
                  </Button>
                )}
                {vendor.status === 'approved' && (
                  <Button
                    variant="danger"
                    className="flex-1"
                    disabled={busy || reason.trim().length < 3}
                    onClick={() =>
                      suspend.mutate({ id: vendor.id, reason }, { onSuccess: onClose })
                    }
                  >
                    Suspend
                  </Button>
                )}
              </div>
              <p className="text-xs text-ink-500">
                Suspending stops new bookings and holds payouts. Existing
                bookings are deliberately left alone — guests with a confirmed
                stay have a contract.
              </p>

              <Button className="w-full" onClick={onClose}>
                Close
              </Button>
            </div>
          </>
        )}
      </aside>
    </div>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-ink-500">{label}</dt>
      <dd className={mono ? 'font-mono text-xs' : undefined}>{value}</dd>
    </div>
  )
}
