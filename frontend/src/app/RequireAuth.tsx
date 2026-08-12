import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import { LoadingBlock } from '@/ui/feedback'

/**
 * The auth gate.
 *
 * The `restoring` state is why this is not a one-liner. On a page reload the
 * app has no access token until `/auth/refresh` answers; redirecting during
 * that window would bounce a signed-in guest to the login page on every F5 —
 * a bug that only ever appears in production, because in development the
 * refresh is instant.
 */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'restoring') return <LoadingBlock label="Checking your session" />

  if (status === 'anonymous') {
    const next = encodeURIComponent(location.pathname + location.search)
    // `replace`, so Back from the login page does not land on the gate again.
    return <Navigate to={`/login?next=${next}`} replace />
  }

  return <Outlet />
}
