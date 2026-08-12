import { Link } from 'react-router-dom'
import {
  useBookings,
  usePayments,
  useProperties,
  useUsers,
  useNotifications,
} from '@/api/queries'
import { useListFilters } from '@/app/useListFilters'
import { PageHeader } from '@/app/Shell'
import { DataTable, FilterBar, SearchInput, Select } from '@/ui/DataTable'
import type { Column } from '@/ui/DataTable'
import { Badge, StatusBadge } from '@/ui/primitives'
import { formatDate, formatDateTime, formatMinor, formatNumber, formatRelative } from '@/core/format'
import type { AdminBooking, AdminPayment, AdminProperty, AdminUser, NotificationRow } from '@/api/types'

/**
 * The five straightforward list screens.
 *
 * Together because they are the same screen with different columns — filters in
 * the URL, offset paging, one table component. Splitting them into five files
 * would duplicate the wiring five times and let them drift apart.
 */

export function BookingsPage() {
  const { filters, update } = useListFilters()
  const query = useBookings(filters)

  const columns: Column<AdminBooking>[] = [
    {
      key: 'reference',
      header: 'Reference',
      render: (row) => (
        <span className="font-mono text-xs">
          {row.reference}
          {/* Flagged inline: a booking with an open ticket is one support is
              already talking to someone about, and acting on it blind is how
              two people give a guest two different answers. */}
          {row.has_open_ticket && (
            <Link to="/tickets" className="ml-2">
              <Badge tone="warn">ticket</Badge>
            </Link>
          )}
        </span>
      ),
    },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    {
      key: 'guest',
      header: 'Guest',
      render: (row) => (
        <div className="min-w-0">
          <p className="truncate">{row.guest_name}</p>
          <p className="truncate text-xs text-ink-500">{row.guest_email}</p>
        </div>
      ),
    },
    {
      key: 'property',
      header: 'Property',
      render: (row) => <span className="block max-w-48 truncate">{row.property_name}</span>,
    },
    {
      key: 'stay',
      header: 'Stay',
      render: (row) => (
        <span className="whitespace-nowrap text-xs">
          {formatDate(row.check_in)} → {formatDate(row.check_out)}
          <span className="ml-1 text-ink-400">
            {row.nights}n
          </span>
        </span>
      ),
    },
    {
      key: 'total',
      header: 'Total',
      numeric: true,
      render: (row) => formatMinor(row.total_minor, row.currency, { compact: true }),
    },
    {
      key: 'created',
      header: 'Booked',
      render: (row) => <span className="text-xs text-ink-500">{formatRelative(row.created_at)}</span>,
    },
  ]

  return (
    <>
      <PageHeader title="Bookings" description="Every booking on the platform" />
      <FilterBar>
        <SearchInput
          value={String(filters.q ?? '')}
          onChange={(q) => update({ q })}
          placeholder="Reference or guest email"
        />
        <Select
          label="Status"
          value={String(filters.status ?? '')}
          onChange={(status) => update({ status })}
          options={[
            { value: '', label: 'All' },
            { value: 'pending_payment', label: 'Payment pending' },
            { value: 'confirmed', label: 'Confirmed' },
            { value: 'in_stay', label: 'In stay' },
            { value: 'completed', label: 'Completed' },
            { value: 'cancelled', label: 'Cancelled' },
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
        emptyMessage="No bookings match those filters"
        page={query.data?.meta.page}
        pages={query.data?.meta.pages}
        total={query.data?.meta.total}
        onPageChange={(page) => update({ page })}
        rowKey={(row) => row.id}
      />
    </>
  )
}

export function PaymentsPage() {
  const { filters, update } = useListFilters()
  const query = usePayments(filters)

  const columns: Column<AdminPayment>[] = [
    {
      key: 'reference',
      header: 'Booking',
      render: (row) => <span className="font-mono text-xs">{row.booking_reference}</span>,
    },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    { key: 'method', header: 'Method', render: (row) => row.method },
    {
      key: 'amount',
      header: 'Charged',
      numeric: true,
      render: (row) => formatMinor(row.amount_minor, row.currency),
    },
    {
      key: 'refunded',
      header: 'Refunded',
      numeric: true,
      render: (row) =>
        row.refunded_minor > 0 ? (
          <span className="text-bad-700">{formatMinor(row.refunded_minor, row.currency)}</span>
        ) : (
          <span className="text-ink-300">—</span>
        ),
    },
    {
      key: 'net',
      header: 'Net held',
      numeric: true,
      // sum(ledger): charge minus fees, refunds and chargebacks. This is the
      // number that must match the settlement report, so it is shown rather
      // than left for someone to work out from the other columns.
      render: (row) => (
        <span className={row.net_minor < 0 ? 'text-bad-700' : undefined}>
          {formatMinor(row.net_minor, row.currency)}
        </span>
      ),
    },
    {
      key: 'captured',
      header: 'Captured',
      render: (row) => <span className="text-xs text-ink-500">{formatDateTime(row.captured_at)}</span>,
    },
  ]

  return (
    <>
      <PageHeader title="Payments" description="Charges, refunds and what the platform holds" />
      <FilterBar>
        <SearchInput
          value={String(filters.q ?? '')}
          onChange={(q) => update({ q })}
          placeholder="Booking reference"
        />
        <Select
          label="Status"
          value={String(filters.status ?? '')}
          onChange={(status) => update({ status })}
          options={[
            { value: '', label: 'All' },
            { value: 'captured', label: 'Captured' },
            { value: 'pending', label: 'Pending' },
            { value: 'authorized', label: 'Authorised' },
            { value: 'failed', label: 'Failed' },
            { value: 'refunded', label: 'Refunded' },
            { value: 'partially_refunded', label: 'Partly refunded' },
            { value: 'disputed', label: 'Disputed' },
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
        emptyMessage="No payments match those filters"
        page={query.data?.meta.page}
        pages={query.data?.meta.pages}
        total={query.data?.meta.total}
        onPageChange={(page) => update({ page })}
        rowKey={(row) => row.id}
      />
    </>
  )
}

export function PropertiesPage() {
  const { filters, update } = useListFilters()
  const query = useProperties(filters)

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
          <Link to={`/vendors?q=${encodeURIComponent(row.vendor_name)}`} className="text-brand-600 hover:underline">
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
  ]

  return (
    <>
      <PageHeader title="Properties" description="Every listing, any status" />
      <FilterBar>
        <SearchInput
          value={String(filters.q ?? '')}
          onChange={(q) => update({ q })}
          placeholder="Name or city"
        />
        <Select
          label="Status"
          value={String(filters.status ?? '')}
          onChange={(status) => update({ status })}
          options={[
            { value: '', label: 'All' },
            { value: 'draft', label: 'Draft' },
            { value: 'pending_review', label: 'Awaiting review' },
            { value: 'published', label: 'Published' },
            { value: 'suspended', label: 'Suspended' },
            { value: 'rejected', label: 'Rejected' },
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
        emptyMessage="No listings match those filters"
        page={query.data?.meta.page}
        pages={query.data?.meta.pages}
        total={query.data?.meta.total}
        onPageChange={(page) => update({ page })}
        rowKey={(row) => row.id}
      />
    </>
  )
}

export function UsersPage() {
  const { filters, update } = useListFilters()
  const query = useUsers(filters)

  const columns: Column<AdminUser>[] = [
    {
      key: 'user',
      header: 'User',
      render: (row) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{row.full_name ?? '—'}</p>
          <p className="truncate text-xs text-ink-500">{row.email}</p>
        </div>
      ),
    },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    {
      key: 'roles',
      header: 'Roles',
      render: (row) => (
        <span className="flex flex-wrap gap-1">
          {row.roles.map((role) => (
            <Badge key={role} tone={role === 'traveler' ? 'neutral' : 'brand'}>
              {role}
            </Badge>
          ))}
        </span>
      ),
    },
    {
      key: 'verified',
      header: 'Email',
      render: (row) =>
        row.email_verified ? (
          <Badge tone="good">verified</Badge>
        ) : (
          <Badge tone="warn">unverified</Badge>
        ),
    },
    { key: 'bookings', header: 'Bookings', numeric: true, render: (row) => formatNumber(row.booking_count) },
    {
      key: 'ltv',
      header: 'Lifetime value',
      numeric: true,
      render: (row) => formatMinor(row.lifetime_value_minor, row.currency, { compact: true }),
    },
    {
      key: 'last_login',
      header: 'Last seen',
      render: (row) => <span className="text-xs text-ink-500">{formatRelative(row.last_login_at)}</span>,
    },
  ]

  return (
    <>
      <PageHeader title="Users" description="Guests and staff" />
      <FilterBar>
        <SearchInput
          value={String(filters.q ?? '')}
          onChange={(q) => update({ q })}
          placeholder="Name or email"
        />
        <Select
          label="Role"
          value={String(filters.role ?? '')}
          onChange={(role) => update({ role })}
          options={[
            { value: '', label: 'Any' },
            { value: 'traveler', label: 'Traveller' },
            { value: 'vendor', label: 'Vendor' },
            { value: 'support', label: 'Support' },
            { value: 'admin', label: 'Admin' },
            { value: 'superadmin', label: 'Superadmin' },
          ]}
        />
        <Select
          label="Status"
          value={String(filters.status ?? '')}
          onChange={(status) => update({ status })}
          options={[
            { value: '', label: 'All' },
            { value: 'active', label: 'Active' },
            { value: 'pending_verification', label: 'Unverified' },
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
        emptyMessage="No users match those filters"
        page={query.data?.meta.page}
        pages={query.data?.meta.pages}
        total={query.data?.meta.total}
        onPageChange={(page) => update({ page })}
        rowKey={(row) => row.id}
      />
    </>
  )
}

export function NotificationsPage() {
  const { filters, update } = useListFilters()
  const query = useNotifications(filters)

  const columns: Column<NotificationRow>[] = [
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    { key: 'template', header: 'Template', render: (row) => <span className="font-mono text-xs">{row.template}</span> },
    { key: 'channel', header: 'Channel', render: (row) => row.channel },
    { key: 'recipient', header: 'Recipient', render: (row) => <span className="text-xs">{row.recipient}</span> },
    {
      key: 'subject',
      header: 'Subject',
      render: (row) => (
        <span className="block max-w-64 truncate text-xs text-ink-600">
          {row.subject ?? row.preview ?? '—'}
        </span>
      ),
    },
    {
      key: 'error',
      header: 'Problem',
      render: (row) =>
        row.error ? (
          <span className="block max-w-48 truncate text-xs text-bad-700" title={row.error}>
            {row.error}
          </span>
        ) : (
          <span className="text-ink-300">—</span>
        ),
    },
    { key: 'attempts', header: 'Tries', numeric: true, render: (row) => row.attempts },
    {
      key: 'sent',
      header: 'Sent',
      render: (row) => <span className="text-xs text-ink-500">{formatDateTime(row.sent_at ?? row.created_at)}</span>,
    },
  ]

  return (
    <>
      <PageHeader
        title="Notifications"
        description="What the platform has sent — and what failed to send"
      />
      <FilterBar>
        <SearchInput
          value={String(filters.recipient ?? '')}
          onChange={(recipient) => update({ recipient })}
          placeholder="Recipient email"
        />
        <Select
          label="Status"
          value={String(filters.status ?? '')}
          onChange={(status) => update({ status })}
          options={[
            { value: '', label: 'All' },
            { value: 'queued', label: 'Queued' },
            { value: 'sent', label: 'Sent' },
            { value: 'failed', label: 'Failed' },
            { value: 'suppressed', label: 'Suppressed' },
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
        emptyMessage="Nothing sent yet"
        page={query.data?.meta.page}
        pages={query.data?.meta.pages}
        total={query.data?.meta.total}
        onPageChange={(page) => update({ page })}
        rowKey={(row) => row.id}
      />
    </>
  )
}
