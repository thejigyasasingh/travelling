import { Suspense } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import { useWishlist } from '@/application/hooks/useWishlist'
import { displayName, initials } from '@/domain/user'
import { Button, ButtonLink } from '@/ui/Button'
import { LoadingBlock } from '@/ui/feedback'
import { cn } from '@/ui/cn'

export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col">
      {/* First tab stop on every page: keyboard users skip the nav in one key. */}
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <Header />
      <main id="main" className="flex-1">
        <Suspense fallback={<LoadingBlock />}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
      <MobileTabBar />
    </div>
  )
}

function Header() {
  const { isAuthenticated, user, signOut } = useAuth()
  const { data: wishlist } = useWishlist()
  const location = useLocation()
  const savedCount = wishlist?.length ?? 0

  return (
    <header className="sticky top-0 z-40 border-b border-ink-100 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex shrink-0 items-center gap-2" aria-label="Roaming & Wandering, home">
          <LogoMark />
          <span className="hidden text-lg font-semibold tracking-tight text-ink-900 sm:block">
            Roaming <span className="text-brand-600">&amp;</span> Wandering
          </span>
        </Link>

        <nav className="ml-auto hidden items-center gap-1 md:flex" aria-label="Main">
          <HeaderLink to="/search">Search</HeaderLink>
          <HeaderLink to="/wishlist">
            Wishlist
            {savedCount > 0 && (
              <span className="ml-1.5 rounded-full bg-brand-100 px-1.5 text-xs font-semibold text-brand-700">
                {savedCount}
              </span>
            )}
          </HeaderLink>
          {isAuthenticated && <HeaderLink to="/trips">Trips</HeaderLink>}
        </nav>

        <div className="ml-auto flex items-center gap-2 md:ml-0">
          {isAuthenticated && user ? (
            <div className="flex items-center gap-2">
              <Link
                to="/profile"
                className="flex items-center gap-2 rounded-full p-1 pr-3 transition-colors hover:bg-ink-100"
              >
                <span className="grid size-8 place-items-center rounded-full bg-brand-600 text-xs font-semibold text-white">
                  {initials(user)}
                </span>
                <span className="hidden text-sm font-medium text-ink-700 sm:block">
                  {displayName(user)}
                </span>
              </Link>
              <Button variant="ghost" size="sm" onClick={() => void signOut()} className="hidden sm:inline-flex">
                Sign out
              </Button>
            </div>
          ) : (
            <>
              <ButtonLink
                to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
                variant="ghost"
                size="sm"
              >
                Sign in
              </ButtonLink>
              <ButtonLink to="/register" size="sm" className="hidden sm:inline-flex">
                Sign up
              </ButtonLink>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

function HeaderLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          'rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          isActive ? 'bg-ink-100 text-ink-900' : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900',
        )
      }
    >
      {children}
    </NavLink>
  )
}

/**
 * Thumb-reachable navigation on phones, where the header is a stretch away.
 * Hidden from `md` up, where the header nav takes over — the two are never both
 * visible, so nothing is announced twice.
 */
function MobileTabBar() {
  const { isAuthenticated } = useAuth()
  const tabs = [
    { to: '/', label: 'Home', icon: <HomeIcon /> },
    { to: '/search', label: 'Search', icon: <SearchIcon /> },
    { to: '/wishlist', label: 'Saved', icon: <HeartIcon /> },
    isAuthenticated
      ? { to: '/trips', label: 'Trips', icon: <BagIcon /> }
      : { to: '/login', label: 'Sign in', icon: <UserIcon /> },
  ]

  return (
    <nav
      aria-label="Primary"
      className="sticky bottom-0 z-40 border-t border-ink-100 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden no-print"
    >
      <ul className="flex">
        {tabs.map((tab) => (
          <li key={tab.to} className="flex-1">
            <NavLink
              to={tab.to}
              end={tab.to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition-colors',
                  isActive ? 'text-brand-600' : 'text-ink-500',
                )
              }
            >
              {tab.icon}
              {tab.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function Footer() {
  return (
    <footer className="border-t border-ink-100 bg-ink-50 no-print">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-4 lg:px-8">
        <div className="md:col-span-2">
          <div className="flex items-center gap-2">
            <LogoMark />
            <span className="font-semibold text-ink-900">Roaming &amp; Wandering</span>
          </div>
          <p className="mt-3 max-w-sm text-sm text-ink-500">
            Hotels, villas, apartments, homestays and resorts across India — booked directly,
            cancelled fairly.
          </p>
        </div>
        <FooterColumn
          title="Explore"
          links={[
            { to: '/search?type=villa', label: 'Villas' },
            { to: '/search?type=homestay', label: 'Homestays' },
            { to: '/search?type=resort', label: 'Resorts' },
            { to: '/search', label: 'All stays' },
          ]}
        />
        <FooterColumn
          title="Account"
          links={[
            { to: '/trips', label: 'My trips' },
            { to: '/wishlist', label: 'Wishlist' },
            { to: '/profile', label: 'Profile' },
            { to: '/settings', label: 'Settings' },
          ]}
        />
      </div>
      <div className="border-t border-ink-200/60 px-4 py-5 text-center text-xs text-ink-500">
        © {new Date().getFullYear()} Roaming &amp; Wandering. Prices include all taxes.
      </div>
    </footer>
  )
}

function FooterColumn({ title, links }: { title: string; links: { to: string; label: string }[] }) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-ink-800">{title}</h2>
      <ul className="mt-3 space-y-2">
        {links.map((link) => (
          <li key={link.to}>
            <Link to={link.to} className="text-sm text-ink-500 transition-colors hover:text-brand-600">
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

function LogoMark() {
  return (
    <span className="grid size-8 place-items-center rounded-xl bg-brand-600 text-sm font-bold text-white">
      R
    </span>
  )
}

const iconClass = 'size-5'
const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round' } as const

function HomeIcon() {
  return <svg className={iconClass} viewBox="0 0 24 24" {...stroke} aria-hidden="true"><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /></svg>
}
function SearchIcon() {
  return <svg className={iconClass} viewBox="0 0 24 24" {...stroke} aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
}
function HeartIcon() {
  return <svg className={iconClass} viewBox="0 0 24 24" {...stroke} aria-hidden="true"><path d="M12 20s-7-4.4-7-9.5A4 4 0 0 1 12 7a4 4 0 0 1 7 3.5C19 15.6 12 20 12 20z" /></svg>
}
function BagIcon() {
  return <svg className={iconClass} viewBox="0 0 24 24" {...stroke} aria-hidden="true"><path d="M4 8h16l-1 12H5L4 8z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /></svg>
}
function UserIcon() {
  return <svg className={iconClass} viewBox="0 0 24 24" {...stroke} aria-hidden="true"><circle cx="12" cy="8" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></svg>
}
