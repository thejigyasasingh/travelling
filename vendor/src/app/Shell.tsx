import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useDashboard, useMe } from '@/api/queries'
import { useAuth } from './AuthGate'
import { Button, cn } from '@/ui/primitives'
import {
  BuildingIcon,
  CalendarIcon,
  HomeIcon,
  InboxIcon,
  ReportIcon,
  SignOutIcon,
  StarIcon,
  WalletIcon,
} from '@/ui/icons'
import type { VendorDashboard } from '@/api/types'

/**
 * The shell.
 *
 * The sidebar counts are the point, not decoration: a host opens this to find
 * out whether anything needs them, and a portal that requires visiting six
 * screens to learn the answer is no better than the email it replaced.
 *
 * The icons are there for the same reason. A host uses this daily and stops
 * reading the labels within a week — after that, shape is what they navigate
 * by, and a list of seven identical text rows has no shape at all.
 */
const SECTIONS = [
  { to: '/', label: 'Overview', end: true, badge: null, icon: HomeIcon },
  { to: '/properties', label: 'Properties', badge: 'in_review', icon: BuildingIcon },
  { to: '/calendar', label: 'Calendar & pricing', badge: null, icon: CalendarIcon },
  { to: '/bookings', label: 'Bookings', badge: 'awaiting_approval', icon: InboxIcon },
  { to: '/reviews', label: 'Reviews', badge: 'reviews_awaiting', icon: StarIcon },
  { to: '/revenue', label: 'Revenue', badge: null, icon: WalletIcon },
  { to: '/reports', label: 'Reports', badge: null, icon: ReportIcon },
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
  const name = me?.display_name || 'Roaming & Wandering'

  return (
    <div className="flex min-h-dvh bg-ink-100">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-ink-200 bg-white lg:flex">
        {/* The mark. One of two places the gradient is spent — a host should
            recognise this portal from a thumbnail, and a wordmark alone at
            this size does not. */}
        <div className="flex items-center gap-2.5 border-b border-ink-100 px-4 py-4">
          <span className="brand-gradient grid size-9 shrink-0 place-items-center rounded-xl text-sm font-bold text-white shadow-raised">
            {initials(name)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink-900">{name}</p>
            <p className="text-xs text-ink-500">Host portal</p>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 p-2.5" aria-label="Sections">
          {SECTIONS.map((section) => {
            const key: BadgeKey | null = section.badge
            const count = key && dashboard ? dashboard[key] : 0
            const SectionIcon = section.icon
            return (
              <NavLink
                key={section.to}
                to={section.to}
                end={'end' in section ? section.end : false}
                className={({ isActive }) =>
                  cn(
                    'group relative flex items-center gap-2.5 rounded-lg py-2 pr-2 pl-3 text-sm',
                    'transition-colors duration-150',
                    isActive
                      ? 'bg-brand-50 font-medium text-brand-700'
                      : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {/* A rail on the active item. The tint alone is legible
                        for someone who can see it; the bar is what makes the
                        current section obvious at a glance and in greyscale. */}
                    <span
                      className={cn(
                        'absolute top-1.5 bottom-1.5 -left-0.5 w-0.5 rounded-full transition-colors',
                        isActive ? 'bg-brand-600' : 'bg-transparent',
                      )}
                    />
                    <SectionIcon
                      className={cn(
                        'size-[18px] shrink-0 transition-colors',
                        isActive ? 'text-brand-600' : 'text-ink-400 group-hover:text-ink-600',
                      )}
                    />
                    <span className="min-w-0 flex-1 truncate">{section.label}</span>
                    {count > 0 && <NavCount count={count} urgent={!!key && URGENT.has(key)} />}
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>

        <div className="border-t border-ink-100 p-3">
          <div className="mb-2 flex items-center gap-2.5 rounded-lg px-1 py-1">
            <span className="grid size-8 shrink-0 place-items-center rounded-full bg-ink-100 text-xs font-semibold text-ink-600">
              {initials(user?.email ?? '?')}
            </span>
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-ink-800">{user?.email}</p>
              {me && (
                <p className="text-xs text-ink-500">
                  {(me.commission_bps / 100).toFixed(1)}% commission
                </p>
              )}
            </div>
          </div>
          <Button size="sm" className="w-full" onClick={() => void signOut()}>
            <SignOutIcon className="size-4" />
            Sign out
          </Button>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        {/* Mobile: a horizontal rail, not a drawer. A host on a phone is
            checking today's arrivals, not browsing. */}
        <div className="flex gap-1 overflow-x-auto border-b border-ink-200 bg-white px-2 py-2 lg:hidden">
          {SECTIONS.map((section) => {
            const key: BadgeKey | null = section.badge
            const count = key && dashboard ? dashboard[key] : 0
            const SectionIcon = section.icon
            return (
              <NavLink
                key={section.to}
                to={section.to}
                end={'end' in section ? section.end : false}
                className={({ isActive }) =>
                  cn(
                    'flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm whitespace-nowrap',
                    isActive ? 'bg-brand-50 font-medium text-brand-700' : 'text-ink-600',
                  )
                }
              >
                <SectionIcon className="size-4" />
                {section.label}
                {count > 0 && <NavCount count={count} urgent={!!key && URGENT.has(key)} />}
              </NavLink>
            )
          })}
        </div>

        {/* Account-level state, above everything. A host whose payouts have
            stopped should not have to infer it from an empty statement. */}
        {me && me.status !== 'approved' && (
          <div
            role="status"
            className={cn(
              'flex items-start gap-2 border-b px-4 py-2.5 text-sm lg:px-6',
              suspended
                ? 'border-bad-200 bg-bad-50 text-bad-700'
                : 'border-warn-200 bg-warn-50 text-warn-700',
            )}
          >
            <span
              className={cn(
                'mt-1.5 size-1.5 shrink-0 rounded-full',
                suspended ? 'bg-bad-500' : 'bg-warn-500',
              )}
            />
            <span>
              {me.status === 'pending' &&
                'Your application is with our team. Listings can be prepared now and go live once approved.'}
              {me.status === 'under_review' && 'Your application is being reviewed.'}
              {me.status === 'rejected' &&
                `Application not approved${me.rejection_reason ? `: ${me.rejection_reason}` : '.'}`}
              {suspended &&
                `Your account is suspended${me.suspension_reason ? `: ${me.suspension_reason}` : '.'} New bookings and payouts are paused. Guests already booked are still arriving.`}
            </span>
          </div>
        )}

        <div className="mx-auto w-full max-w-7xl flex-1 p-4 lg:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function NavCount({ count, urgent }: { count: number; urgent: boolean }) {
  return (
    <span
      className={cn(
        'grid h-5 min-w-5 shrink-0 place-items-center rounded-full px-1.5 text-xs font-semibold',
        urgent ? 'bg-warn-500 text-white' : 'bg-ink-200 text-ink-600',
      )}
    >
      {count}
    </span>
  )
}

/**
 * Up to two letters for the avatar.
 *
 * Splits a display name on whitespace and an email on its local part, because
 * `SE` for "Sea Breeze Stays" is recognisable and `HO` for
 * `host@example.com` is at least stable.
 */
function initials(value: string): string {
  const source = value.includes('@') ? value.split('@')[0] ?? value : value
  const words = source.split(/[\s._-]+/).filter(Boolean)
  const letters = words.slice(0, 2).map((w) => w[0] ?? '')
  return (letters.join('') || source.slice(0, 2)).toUpperCase()
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[1.375rem] font-semibold tracking-tight text-ink-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-500">{description}</p>}
      </div>
      {action}
    </header>
  )
}
