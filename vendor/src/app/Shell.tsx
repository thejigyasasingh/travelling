import { NavLink, Outlet } from 'react-router-dom'
import { useDashboard, useMe } from '@/api/queries'
import { useAuth } from './AuthGate'
import { Button, cn } from '@/ui/primitives'
import type { VendorDashboard } from '@/api/types'

/**
 * The shell.
 *
 * The sidebar counts are the point, not decoration: a host opens this to find
 * out whether anything needs them, and a portal that requires visiting six
 * screens to learn the answer is no better than the email it replaced.
 */
const SECTIONS = [
  { to: '/', label: 'Overview', end: true, badge: null },
  { to: '/properties', label: 'Properties', badge: 'in_review' },
  { to: '/calendar', label: 'Calendar & pricing', badge: null },
  { to: '/bookings', label: 'Bookings', badge: 'awaiting_approval' },
  { to: '/reviews', label: 'Reviews', badge: 'reviews_awaiting' },
  { to: '/revenue', label: 'Revenue', badge: null },
  { to: '/reports', label: 'Reports', badge: null },
] as const

type BadgeKey = Extract<keyof VendorDashboard, 'in_review' | 'awaiting_approval' | 'reviews_awaiting'>

/**
 * A pending listing is informational; a booking waiting on the host and an
 * unanswered review are both things a guest is currently waiting for. Only the
 * second kind gets the urgent colour, or every badge becomes background noise.
 */
const URGENT: ReadonlySet<BadgeKey> = new Set<BadgeKey>(['awaiting_approval', 'reviews_awaiting'])

export function Shell() {
  const { user, signOut } = useAuth()
  const { data: dashboard } = useDashboard()
  const { data: me } = useMe()

  const suspended = me?.status === 'suspended'

  return (
    <div className="flex min-h-dvh">
      <aside className="hidden w-56 shrink-0 border-r border-ink-200 bg-white lg:flex lg:flex-col">
        <div className="border-b border-ink-100 px-4 py-4">
          <p className="truncate text-sm font-semibold text-ink-900">
            {me?.display_name || 'Roaming & Wandering'}
          </p>
          <p className="text-xs text-ink-500">Host portal</p>
        </div>

        <nav className="flex-1 space-y-0.5 p-2" aria-label="Sections">
          {SECTIONS.map((section) => {
            const key: BadgeKey | null = section.badge
            const count = key && dashboard ? dashboard[key] : 0
            return (
              <NavLink
                key={section.to}
                to={section.to}
                end={'end' in section ? section.end : false}
                className={({ isActive }) =>
                  cn(
                    'flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-brand-50 font-medium text-brand-700'
                      : 'text-ink-600 hover:bg-ink-100',
                  )
                }
              >
                <span className="truncate">{section.label}</span>
                {count > 0 && (
                  <span
                    className={cn(
                      'rounded-full px-1.5 text-xs font-semibold',
                      key && URGENT.has(key)
                        ? 'bg-warn-50 text-warn-700'
                        : 'bg-ink-100 text-ink-600',
                    )}
                  >
                    {count}
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>

        <div className="border-t border-ink-100 p-3">
          <p className="truncate text-xs font-medium text-ink-700">{user?.email}</p>
          {me && (
            <p className="mt-0.5 text-xs text-ink-500">
              {(me.commission_bps / 100).toFixed(1)}% commission
            </p>
          )}
          <Button size="sm" className="mt-2 w-full" onClick={() => void signOut()}>
            Sign out
          </Button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        {/* Mobile: a horizontal rail, not a drawer. A host on a phone is
            checking today's arrivals, not browsing. */}
        <div className="flex gap-1 overflow-x-auto border-b border-ink-200 bg-white px-2 py-2 lg:hidden">
          {SECTIONS.map((section) => (
            <NavLink
              key={section.to}
              to={section.to}
              end={'end' in section ? section.end : false}
              className={({ isActive }) =>
                cn(
                  'shrink-0 rounded-lg px-3 py-1.5 text-sm whitespace-nowrap',
                  isActive ? 'bg-brand-50 font-medium text-brand-700' : 'text-ink-600',
                )
              }
            >
              {section.label}
            </NavLink>
          ))}
        </div>

        {/* Account-level state, above everything. A host whose payouts have
            stopped should not have to infer it from an empty statement. */}
        {me && me.status !== 'approved' && (
          <div
            role="status"
            className={cn(
              'border-b px-4 py-2 text-sm lg:px-6',
              suspended ? 'border-bad-200 bg-bad-50 text-bad-700' : 'border-warn-200 bg-warn-50 text-warn-700',
            )}
          >
            {me.status === 'pending' && 'Your application is with our team. Listings can be prepared now and go live once approved.'}
            {me.status === 'under_review' && 'Your application is being reviewed.'}
            {me.status === 'rejected' &&
              `Application not approved${me.rejection_reason ? `: ${me.rejection_reason}` : '.'}`}
            {suspended &&
              `Your account is suspended${me.suspension_reason ? `: ${me.suspension_reason}` : '.'} New bookings and payouts are paused. Guests already booked are still arriving.`}
          </div>
        )}

        <div className="p-4 lg:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: React.ReactNode
}) {
  return (
    <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">{title}</h1>
        {description && <p className="mt-0.5 text-sm text-ink-500">{description}</p>}
      </div>
      {action}
    </header>
  )
}
