import { NavLink, Outlet } from 'react-router-dom'
import { useDashboard } from '@/api/queries'
import { useAuth } from './AuthGate'
import { Button, cn } from '@/ui/primitives'

/**
 * The shell.
 *
 * The sidebar counts are the reason this is not just a nav: an admin's job is a
 * queue, and a panel that makes you open five screens to discover there is
 * nothing to do wastes the one thing the tool is meant to save.
 */
const SECTIONS = [
  { to: '/', label: 'Dashboard', end: true, badge: null },
  { to: '/bookings', label: 'Bookings', badge: null },
  { to: '/payments', label: 'Payments', badge: null },
  { to: '/properties', label: 'Properties', badge: 'properties_pending' },
  { to: '/vendors', label: 'Vendors', badge: 'vendors_pending' },
  { to: '/users', label: 'Users', badge: null },
  { to: '/coupons', label: 'Coupons', badge: null },
  { to: '/tickets', label: 'Support', badge: 'tickets_open' },
  { to: '/notifications', label: 'Notifications', badge: 'notifications_failed' },
  { to: '/analytics', label: 'Analytics', badge: null },
] as const

export function Shell() {
  const { user, signOut } = useAuth()
  const { data: dashboard } = useDashboard()
  const queue = dashboard?.action_queue ?? {}

  return (
    <div className="flex min-h-dvh">
      <aside className="hidden w-56 shrink-0 border-r border-ink-200 bg-white lg:flex lg:flex-col">
        <div className="border-b border-ink-100 px-4 py-4">
          <p className="text-sm font-semibold text-ink-900">Roaming &amp; Wandering</p>
          <p className="text-xs text-ink-500">Admin</p>
        </div>

        <nav className="flex-1 space-y-0.5 p-2" aria-label="Sections">
          {SECTIONS.map((section) => {
            const count = section.badge ? (queue[section.badge] ?? 0) : 0
            return (
              <NavLink
                key={section.to}
                to={section.to}
                end={'end' in section ? section.end : false}
                className={({ isActive }) =>
                  cn(
                    'flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-brand-50 font-medium text-brand-700'
                      : 'text-ink-600 hover:bg-ink-100',
                  )
                }
              >
                {section.label}
                {count > 0 && (
                  <span
                    className={cn(
                      'rounded-full px-1.5 text-xs font-semibold',
                      section.badge === 'notifications_failed'
                        ? 'bg-bad-50 text-bad-700'
                        : 'bg-warn-50 text-warn-700',
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
          <p className="mt-0.5 truncate text-xs text-ink-500">{user?.roles.join(', ')}</p>
          <Button size="sm" className="mt-2 w-full" onClick={() => void signOut()}>
            Sign out
          </Button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        {/* Mobile nav: a horizontal rail rather than a drawer. An admin on a
            phone is checking one thing, not browsing. */}
        <div className="flex gap-1 overflow-x-auto border-b border-ink-200 bg-white px-2 py-2 lg:hidden">
          {SECTIONS.map((section) => (
            <NavLink
              key={section.to}
              to={section.to}
              end={'end' in section ? section.end : false}
              className={({ isActive }) =>
                cn(
                  'shrink-0 rounded-lg px-3 py-1.5 text-sm',
                  isActive ? 'bg-brand-50 font-medium text-brand-700' : 'text-ink-600',
                )
              }
            >
              {section.label}
            </NavLink>
          ))}
        </div>
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
