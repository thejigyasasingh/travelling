import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  useChecklist,
  useCreateRoomType,
  useProperties,
  useProperty,
  useSetVisibility,
  useSubmitProperty,
  useUpdateProperty,
  useUpdateRoomType,
} from '@/api/queries'
import { PageHeader } from '@/app/Shell'
import { formatDate, formatMinor } from '@/core/format'
import { ApiError } from '@/core/http'
import { DataTable, type Column } from '@/ui/DataTable'
import { Button, Card, StatusBadge } from '@/ui/primitives'
import type { RoomType, VendorProperty } from '@/api/types'

/**
 * The listings a host owns.
 *
 * A list and a detail screen rather than an inline editor: a listing has thirty
 * editable fields and the ones that matter — rooms, rates, inventory — are each
 * a screen's worth of decisions on their own.
 */
export function PropertiesPage() {
  const [status, setStatus] = useState<string>('')
  const [page, setPage] = useState(1)
  const navigate = useNavigate()
  const { data, isPending, isFetching, error, refetch } = useProperties({
    ...(status ? { status } : {}),
    page,
    size: 20,
  })

  const columns: Column<VendorProperty>[] = [
    {
      key: 'name',
      header: 'Listing',
      render: (row) => (
        <div>
          <p className="font-medium text-ink-900">{row.name}</p>
          <p className="text-xs text-ink-500">
            {row.city}, {row.state}
          </p>
        </div>
      ),
    },
    { key: 'type', header: 'Type', render: (row) => <span className="capitalize">{row.property_type}</span> },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    { key: 'rooms', header: 'Rooms', numeric: true, render: (row) => row.room_types.length },
    {
      key: 'rating',
      header: 'Rating',
      numeric: true,
      // An unrated listing shows an em dash, never 0.0 — nought out of five is
      // the worst score on the platform and a new listing has not earned it.
      render: (row) =>
        row.review_count === 0 ? '—' : `${row.review_average.toFixed(1)} (${row.review_count})`,
    },
    {
      key: 'published',
      header: 'Live since',
      render: (row) => (row.published_at ? formatDate(row.published_at) : '—'),
    },
  ]

  return (
    <>
      <PageHeader
        title="Properties"
        description="Everything you list. Rooms, rates and inventory live inside each one."
      />

      <div className="mb-3 flex flex-wrap gap-2">
        {['', 'draft', 'pending_review', 'published', 'unpublished'].map((value) => (
          <button
            key={value || 'all'}
            type="button"
            onClick={() => {
              setStatus(value)
              setPage(1)
            }}
            className={
              status === value
                ? 'rounded-lg bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700'
                : 'rounded-lg px-3 py-1.5 text-sm text-ink-600 hover:bg-ink-100'
            }
          >
            {value ? value.replace('_', ' ') : 'All'}
          </button>
        ))}
      </div>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        isLoading={isPending}
        isFetching={isFetching}
        error={error}
        onRetry={() => void refetch()}
        emptyMessage="No listings yet."
        page={data?.page}
        pages={data ? Math.max(1, Math.ceil(data.total / data.size)) : 1}
        total={data?.total}
        onPageChange={setPage}
        rowKey={(row) => row.id}
        onRowClick={(row) => void navigate(`/properties/${row.id}`)}
      />
    </>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// One listing
// ══════════════════════════════════════════════════════════════════════════

export function PropertyDetailPage() {
  const { propertyId = '' } = useParams()
  const { data: property, isPending } = useProperty(propertyId)
  const { data: checklist } = useChecklist(propertyId)
  const submit = useSubmitProperty(propertyId)
  const visibility = useSetVisibility(propertyId)

  if (isPending || !property) return <p className="py-20 text-center text-sm text-ink-500">Loading…</p>

  const live = property.status === 'published'

  return (
    <>
      <PageHeader
        title={property.name}
        description={`${property.city}, ${property.state} · ${property.property_type}`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={property.status} />
            {property.status === 'draft' && (
              <Button
                variant="primary"
                disabled={submit.isPending || checklist?.ready === false}
                onClick={() => submit.mutate()}
              >
                {submit.isPending ? 'Submitting…' : 'Submit for review'}
              </Button>
            )}
            {(live || property.status === 'unpublished') && (
              <Button
                disabled={visibility.isPending}
                onClick={() => visibility.mutate(!live)}
                title={
                  live
                    ? 'Stops new bookings. Guests already booked are still arriving.'
                    : 'Puts the listing back on sale.'
                }
              >
                {live ? 'Take off sale' : 'Put back on sale'}
              </Button>
            )}
          </div>
        }
      />

      {/* Publishing and submitting both fail for a reason the host can act on
          — a missing map pin, a description too short. Showing it here, next
          to the button that was just pressed, is the difference between a
          fixable problem and a button that "does nothing". */}
      {(submit.error ?? visibility.error) instanceof ApiError && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-bad-200 bg-bad-50 px-4 py-3 text-sm text-bad-700"
        >
          <p>{((submit.error ?? visibility.error) as ApiError).message}</p>
          {missingFrom(submit.error ?? visibility.error).length > 0 && (
            <ul className="mt-1 list-inside list-disc">
              {missingFrom(submit.error ?? visibility.error).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {property.rejection_reason && (
        <div className="mb-4 rounded-xl border border-bad-200 bg-bad-50 px-4 py-3 text-sm text-bad-700">
          <strong className="font-medium">Not approved:</strong> {property.rejection_reason}
        </div>
      )}

      {live && (
        <p className="mb-4 text-sm text-ink-500">
          Taking a listing off sale stops <em>new</em> bookings. Guests who have already booked are
          still arriving and still appear in{' '}
          <Link to="/bookings" className="text-brand-700 underline">
            bookings
          </Link>
          .
        </p>
      )}

      {/* What the server will refuse to publish without — rendered verbatim
          rather than re-derived, so it cannot drift from the real check. */}
      {checklist && !checklist.ready && (
        <Card title="Before this can go live" className="mb-4">
          <ul className="space-y-1.5 px-4 py-3 text-sm">
            {checklist.missing.map((item) => (
              <li key={item} className="flex items-start gap-2 text-ink-700">
                <span aria-hidden="true" className="mt-1.5 size-1.5 shrink-0 rounded-full bg-warn-500" />
                {item}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <BasicsCard property={property} />
        <RoomsCard property={property} />
      </div>
    </>
  )
}

/** The server names what is missing in `details.missing`. Reading it here
 *  rather than only showing the sentence means the host is told *which* thing
 *  to fix, which is the whole content of the refusal. */
function missingFrom(error: unknown): string[] {
  if (!(error instanceof ApiError)) return []
  const missing = error.details['missing']
  return Array.isArray(missing) ? missing.map(String) : []
}

function BasicsCard({ property }: { property: VendorProperty }) {
  const update = useUpdateProperty(property.id)
  const [description, setDescription] = useState(property.description ?? '')
  const [houseRules, setHouseRules] = useState(property.house_rules ?? '')

  const dirty = description !== (property.description ?? '') || houseRules !== (property.house_rules ?? '')

  return (
    <Card title="Details" className="lg:col-span-1">
      <div className="space-y-3 px-4 py-3">
        <label className="block text-sm">
          <span className="font-medium text-ink-700">Description</span>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={6}
            className="mt-1 w-full rounded-lg border border-ink-200 p-2 text-sm"
          />
          <span className="text-xs text-ink-500">{description.trim().length} characters</span>
        </label>

        <label className="block text-sm">
          <span className="font-medium text-ink-700">House rules</span>
          <textarea
            value={houseRules}
            onChange={(event) => setHouseRules(event.target.value)}
            rows={3}
            className="mt-1 w-full rounded-lg border border-ink-200 p-2 text-sm"
          />
        </label>

        {update.error instanceof ApiError && (
          <p role="alert" className="rounded-lg bg-bad-50 px-3 py-2 text-sm text-bad-700">
            {update.error.message}
          </p>
        )}

        <Button
          variant="primary"
          disabled={!dirty || update.isPending}
          onClick={() => update.mutate({ description, house_rules: houseRules })}
        >
          {update.isPending ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </Card>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// Rooms
// ══════════════════════════════════════════════════════════════════════════

function RoomsCard({ property }: { property: VendorProperty }) {
  const [adding, setAdding] = useState(false)

  return (
    <Card
      title="Rooms"
      className="lg:col-span-2"
      action={
        <Button size="sm" onClick={() => setAdding((open) => !open)}>
          {adding ? 'Cancel' : 'Add a room'}
        </Button>
      }
    >
      {adding && <RoomForm propertyId={property.id} onDone={() => setAdding(false)} />}

      {property.room_types.length === 0 && !adding && (
        <p className="px-4 py-8 text-center text-sm text-ink-500">
          No rooms yet. A listing needs at least one before it can go live.
        </p>
      )}

      <ul className="divide-y divide-ink-100">
        {property.room_types.map((room) => (
          <RoomRow key={room.id} propertyId={property.id} room={room} currency={property.currency} />
        ))}
      </ul>
    </Card>
  )
}

function RoomRow({
  propertyId,
  room,
  currency,
}: {
  propertyId: string
  room: RoomType
  currency: string
}) {
  const [editing, setEditing] = useState(false)

  if (editing) {
    return (
      <li>
        <RoomForm propertyId={propertyId} room={room} onDone={() => setEditing(false)} />
      </li>
    )
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <p className="font-medium text-ink-900">{room.name}</p>
        <p className="text-xs text-ink-500">
          Sleeps {room.max_adults + room.max_children} · {room.total_units} unit
          {room.total_units === 1 ? '' : 's'}
          {room.bed_type ? ` · ${room.bed_type}` : ''}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <p className="font-medium tabular-nums text-ink-900">
            {formatMinor(room.base_rate_minor, currency)}
          </p>
          <p className="text-xs text-ink-500">default nightly</p>
        </div>
        <Button size="sm" onClick={() => setEditing(true)}>
          Edit
        </Button>
        <Link
          to={`/calendar?property=${propertyId}&room=${room.id}`}
          className="text-sm text-brand-700 underline"
        >
          Calendar
        </Link>
      </div>
    </li>
  )
}

/**
 * Add or edit a room.
 *
 * The base rate here is the *default* — the price for any night nobody has set
 * explicitly. Changing it does not overwrite dates already priced on the
 * calendar, and the form says so, because that is the assumption a host makes
 * and the one that costs them a season if it is wrong.
 */
function RoomForm({
  propertyId,
  room,
  onDone,
}: {
  propertyId: string
  room?: RoomType
  onDone: () => void
}) {
  const create = useCreateRoomType(propertyId)
  const update = useUpdateRoomType(propertyId)
  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error

  const [name, setName] = useState(room?.name ?? '')
  const [maxAdults, setMaxAdults] = useState(room?.max_adults ?? 2)
  const [maxChildren, setMaxChildren] = useState(room?.max_children ?? 0)
  const [units, setUnits] = useState(room?.total_units ?? 1)
  const [rateRupees, setRateRupees] = useState(
    room ? String(room.base_rate_minor / 100) : '',
  )

  function save() {
    // Rupees in the form, paise on the wire. The conversion happens once, here,
    // and `Math.round` rather than truncation so ₹1,234.55 is not ₹1,234.54.
    const body = {
      name: name.trim(),
      max_adults: maxAdults,
      max_children: maxChildren,
      total_units: units,
      base_rate_minor: Math.round(Number(rateRupees) * 100),
    }
    const options = { onSuccess: onDone }
    if (room) update.mutate({ roomTypeId: room.id, body }, options)
    else create.mutate(body, options)
  }

  return (
    <div className="border-b border-ink-100 bg-ink-50 px-4 py-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Name">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Garden-side double"
            className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
          />
        </Field>
        <Field label="Default nightly rate (₹)">
          <input
            type="number"
            min={0}
            step="0.01"
            value={rateRupees}
            onChange={(event) => setRateRupees(event.target.value)}
            className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
          />
        </Field>
        <Field label="Units">
          <input
            type="number"
            min={1}
            max={500}
            value={units}
            onChange={(event) => setUnits(Number(event.target.value))}
            className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
          />
        </Field>
        <Field label="Max adults">
          <input
            type="number"
            min={1}
            value={maxAdults}
            onChange={(event) => setMaxAdults(Number(event.target.value))}
            className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
          />
        </Field>
        <Field label="Max children">
          <input
            type="number"
            min={0}
            value={maxChildren}
            onChange={(event) => setMaxChildren(Number(event.target.value))}
            className="h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
          />
        </Field>
      </div>

      <p className="mt-2 text-xs text-ink-500">
        The default rate applies to any night you have not priced on the calendar. Changing it does
        not overwrite dates you have already set.
      </p>

      {error instanceof ApiError && (
        <p role="alert" className="mt-2 rounded-lg bg-bad-50 px-3 py-2 text-sm text-bad-700">
          {error.message}
        </p>
      )}

      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={pending || !name.trim()} onClick={save}>
          {pending ? 'Saving…' : room ? 'Save room' : 'Add room'}
        </Button>
        <Button onClick={onDone}>Cancel</Button>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="text-xs font-medium text-ink-600">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  )
}
