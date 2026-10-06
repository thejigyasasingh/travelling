import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useProperties, useReviewProperty, useSuspendProperty } from '@/api/queries'
import type { ListFilters } from '@/api/queries'
import { useAuth } from '@/app/AuthGate'
import { useListFilters } from '@/app/useListFilters'
import { PageHeader } from '@/app/Shell'
import { DataTable, FilterBar, SearchInput, Select } from '@/ui/DataTable'
import type { Column } from '@/ui/DataTable'
import { Button, StatusBadge } from '@/ui/primitives'
import { formatDate } from '@/core/format'
import { ApiError } from '@/core/http'
import type { AdminProperty } from '@/api/types'

/**
 * Listings, and the review queue.
 *
 * Moved out of `lists.tsx` once it stopped being a list: approving a listing
 * puts inventory in front of travellers and rejecting one takes it away for as
 * long as the vendor takes to notice, so this screen acts rather than reports.
 *
 * Review is a gate on **trust**, not on tidiness. A marketplace that publishes
 * whatever is submitted gets stolen photos and properties that do not exist,
 * and the first traveller to arrive at one costs more than every review that
 * prevented it. So a rejection carries a reason the vendor can act on — the
 * server refuses one without, and so does this form.
 */

/** The server gate on every action here (`CanPublish` on the admin routes). */
export const PROPERTY_MODERATION_PERMISSION = 'property:publish:any'

/**
 * Five, because the suspend endpoint's schema enforces five and a rejection of
 * "no" is one the vendor cannot act on. Held to the same bar in both places:
 * two different minimums on one form is a rule nobody can predict.
 */
const MIN_REASON = 5
const MAX_REASON = 500

/** Defaults to the queue. The sidebar badges `properties_pending`, and a count
 *  that opens onto every listing ever created is a count nobody follows. */
const DEFAULT_FILTERS = { status: 'pending_review' }

/**
 * "All" is a value in the URL, not the absence of one.
 *
 * `useListFilters` drops an empty filter from the query string, and an absent
 * `status` here means the default — the queue. So the usual `value: ''` for
 * "All" would delete the parameter, fall back to `pending_review`, and snap the
 * dropdown back to "Awaiting review" the moment someone chose "All".
 */
const ANY_STATUS = 'any'

const STATUS_OPTIONS = [
  { value: ANY_STATUS, label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'pending_review', label: 'Awaiting review' },
  { value: 'published', label: 'Published' },
  { value: 'unpublished', label: 'Unpublished' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'rejected', label: 'Rejected' },
]

/** `any` is this screen's word, not the API's — the server would treat it as a
 *  status nothing matches and return an empty queue. */
export function toListQuery(filters: ListFilters): ListFilters {
  if (filters.status !== ANY_STATUS) return filters
  const next = { ...filters }
  delete next.status
  return next
}

export interface ModerationActions {
  approve: boolean
  reject: boolean
  suspend: boolean
}

/**
 * What the server will actually accept for a listing in this status.
 *
 * A mirror of the domain's transition table, kept as a pure function so the
 * panel never offers a button that can only 409. Offering an action the server
 * refuses is worse than hiding it: the admin presses it, reads a transition
 * error, and learns to distrust every other button on the screen.
 */
export function moderationActions(status: string): ModerationActions {
  return {
    // pending_review → published | rejected
    approve: status === 'pending_review',
    reject: status === 'pending_review',
    // published | unpublished → suspended. Not from draft, rejected, or an
    // existing suspension, none of which the transition table allows.
    suspend: status === 'published' || status === 'unpublished',
  }
}

export function PropertiesPage() {
  const { filters, update } = useListFilters(DEFAULT_FILTERS)
  const query = useProperties(toListQuery(filters))
  const { can } = useAuth()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const canModerate = can(PROPERTY_MODERATION_PERMISSION)
  const rows = query.data?.items ?? []
  const selected = rows.find((row) => row.id === selectedId) ?? null

  const columns: Column<AdminProperty>[] = [
    {
      key: 'name',
      header: 'Property',
      render: (row) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{row.name}</p>
          <p className="truncate text-xs text-ink-500">
            {row.city} · {row.property_type}
          </p>
        </div>
      ),
    },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    {
      key: 'vendor',
      header: 'Vendor',
      render: (row) =>
        row.vendor_name ? (
          <Link
            to={`/vendors?q=${encodeURIComponent(row.vendor_name)}`}
            // The row itself opens the panel, so a link inside it has to say
            // so — otherwise following the vendor also opens the review drawer.
            onClick={(event) => event.stopPropagation()}
            className="text-brand-600 hover:underline"
          >
            {row.vendor_name}
          </Link>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    { key: 'rooms', header: 'Rooms', numeric: true, render: (row) => row.room_types },
    {
      key: 'rating',
      header: 'Rating',
      numeric: true,
      // "New" rather than 0.0 — an unrated listing is not a badly-rated one.
      render: (row) =>
        row.review_count === 0 ? (
          <span className="text-ink-400">New</span>
        ) : (
          `${row.review_average.toFixed(1)} (${row.review_count})`
        ),
    },
    {
      key: 'published',
      header: 'Published',
      render: (row) => <span className="text-xs text-ink-500">{formatDate(row.published_at)}</span>,
    },
    {
      key: 'action',
      header: '',
      render: (row) => (
        <Button size="sm" onClick={() => setSelectedId(row.id)}>
          {/* "Open" rather than "Review" when there is nothing to decide, so
              the word in the button matches what pressing it can do. */}
          {canModerate && hasAnyAction(row.status) ? 'Review' : 'Open'}
        </Button>
      ),
    },
  ]

  return (
    <>
      <PageHeader title="Properties" description="The review queue, and every listing behind it" />
      <FilterBar>
        <SearchInput
          value={String(filters.q ?? '')}
          onChange={(q) => update({ q })}
          placeholder="Name or city"
        />
        <Select
          label="Status"
          value={String(filters.status ?? ANY_STATUS)}
          onChange={(status) => update({ status })}
          options={STATUS_OPTIONS}
        />
      </FilterBar>
      <DataTable
        columns={columns}
        rows={rows}
        isLoading={query.isPending}
        isFetching={query.isFetching}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyMessage="No listings match those filters"
        page={query.data?.meta.page}
        pages={query.data?.meta.pages}
        total={query.data?.meta.total}
        onPageChange={(page) => update({ page })}
        rowKey={(row) => row.id}
        onRowClick={(row) => setSelectedId(row.id)}
      />

      {selected && (
        <PropertyReviewPanel
          property={selected}
          canModerate={canModerate}
          onClose={() => setSelectedId(null)}
        />
      )}
    </>
  )
}

function hasAnyAction(status: string): boolean {
  const actions = moderationActions(status)
  return actions.approve || actions.reject || actions.suspend
}

/**
 * The decision panel.
 *
 * Built from the row rather than a detail fetch, because there is no
 * `GET /admin/properties/{id}` — the list already carries everything a
 * reviewer decides on, and inventing a detail endpoint to populate a drawer
 * would be a round trip for data that is already on screen.
 */
function PropertyReviewPanel({
  property,
  canModerate,
  onClose,
}: {
  property: AdminProperty
  canModerate: boolean
  onClose: () => void
}) {
  const review = useReviewProperty()
  const suspend = useSuspendProperty()
  const [reason, setReason] = useState('')

  const actions = moderationActions(property.status)
  const busy = review.isPending || suspend.isPending
  const error = review.error ?? suspend.error
  const reasonGiven = reason.trim().length >= MIN_REASON

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-900/30" onClick={onClose}>
      <aside
        className="h-full w-full max-w-md overflow-y-auto bg-white p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-ink-900">{property.name}</h2>
            <p className="truncate text-sm text-ink-500">
              {property.city} · {property.property_type}
            </p>
          </div>
          <StatusBadge status={property.status} />
        </header>

        <dl className="mt-5 space-y-2 text-sm">
          <Row label="Vendor" value={property.vendor_name ?? '—'} />
          <Row label="Slug" value={property.slug} mono />
          <Row label="Room types" value={String(property.room_types)} />
          <Row
            label="Rating"
            // Never 0.0 for an unrated listing: a reviewer glancing at this
            // would read it as the worst listing on the platform.
            value={
              property.review_count === 0
                ? 'No reviews yet'
                : `${property.review_average.toFixed(1)} from ${property.review_count}`
            }
          />
          <Row label="Created" value={formatDate(property.created_at)} />
          <Row label="Published" value={formatDate(property.published_at)} />
        </dl>

        {property.room_types === 0 && actions.approve && (
          <p className="mt-3 rounded-lg bg-warn-50 p-3 text-xs text-warn-700">
            No room types. The server re-checks completeness on approval and
            will refuse this one — the listing is editable while it waits, so
            what passed at submission may no longer hold.
          </p>
        )}

        {error && (
          <p role="alert" className="mt-3 rounded-lg bg-bad-50 p-3 text-xs text-bad-700">
            {error instanceof ApiError ? error.message : 'That action failed.'}
          </p>
        )}

        <div className="mt-5 space-y-3 border-t border-ink-100 pt-4">
          {!canModerate ? (
            <p className="rounded-lg bg-ink-50 p-3 text-xs text-ink-600">
              You can see this listing but not decide on it. Moderation needs{' '}
              <span className="font-mono">{PROPERTY_MODERATION_PERMISSION}</span>.
            </p>
          ) : !hasAnyAction(property.status) ? (
            <p className="rounded-lg bg-ink-50 p-3 text-xs text-ink-600">
              Nothing to decide on a listing in this state. A rejected or
              suspended listing moves next when the vendor acts, not here.
            </p>
          ) : (
            <>
              {actions.approve && (
                <Button
                  variant="primary"
                  className="w-full"
                  disabled={busy}
                  onClick={() =>
                    review.mutate({ id: property.id, approve: true }, { onSuccess: onClose })
                  }
                >
                  Approve and publish
                </Button>
              )}

              <label className="block text-sm font-medium text-ink-700">
                Reason
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  rows={2}
                  maxLength={MAX_REASON}
                  className="mt-1 w-full rounded-lg border border-ink-200 px-2 py-1.5 text-sm"
                  placeholder="Required to reject or suspend"
                />
                <span className="mt-1 block text-xs text-ink-500">
                  The vendor reads this. "Photos do not match the address" is
                  actionable; "rejected" is not.
                </span>
              </label>

              <div className="flex gap-2">
                {actions.reject && (
                  <Button
                    variant="danger"
                    className="flex-1"
                    disabled={busy || !reasonGiven}
                    onClick={() =>
                      review.mutate(
                        { id: property.id, approve: false, reason: reason.trim() },
                        { onSuccess: onClose },
                      )
                    }
                  >
                    Reject
                  </Button>
                )}
                {actions.suspend && (
                  <Button
                    variant="danger"
                    className="flex-1"
                    disabled={busy || !reasonGiven}
                    onClick={() =>
                      suspend.mutate(
                        { id: property.id, reason: reason.trim() },
                        { onSuccess: onClose },
                      )
                    }
                  >
                    Suspend
                  </Button>
                )}
              </div>

              {actions.suspend && (
                <p className="text-xs text-ink-500">
                  Suspending takes the listing off sale and the vendor cannot
                  reverse it — only an admin can, and only back to unpublished.
                  Confirmed bookings are deliberately left alone: a guest with a
                  stay has a contract.
                </p>
              )}
            </>
          )}

          <Button className="w-full" onClick={onClose}>
            Close
          </Button>
        </div>
      </aside>
    </div>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-ink-500">{label}</dt>
      <dd className={mono ? 'truncate font-mono text-xs' : 'truncate'}>{value}</dd>
    </div>
  )
}
