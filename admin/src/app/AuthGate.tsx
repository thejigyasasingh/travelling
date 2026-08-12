import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setAccessToken, setSessionLostHandler } from '@/core/http'
import { Button } from '@/ui/primitives'
import type { CurrentUser } from '@/api/types'

/**
 * Who is signed in, and whether they are staff.
 *
 * The gate here is **defence in depth, not the enforcement**. Every admin endpoint
 * checks its own permission server-side; this exists so a support agent is not
 * shown a revenue chart that will only 403 when it loads, and so a guest who
 * finds the URL gets an explanation rather than ten broken panels.
 */
interface AuthState {
  readonly user: CurrentUser | null
  readonly status: 'restoring' | 'ready'
  readonly signOut: () => Promise<void>
  readonly can: (permission: string) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

const STAFF_ROLES = ['admin', 'superadmin', 'support']

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [status, setStatus] = useState<'restoring' | 'ready'>('restoring')

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        // The HttpOnly refresh cookie is the credential; the access token lives
        // only in memory, so a reload always starts here.
        const tokens = await api.post<{ tokens: { access_token: string } }>(
          '/auth/refresh',
          {},
        )
        setAccessToken(tokens.tokens.access_token)
        const me = await api.get<CurrentUser>('/auth/me')
        if (!cancelled) setUser(me)
      } catch {
        if (!cancelled) setUser(null)
      } finally {
        if (!cancelled) setStatus('ready')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    setSessionLostHandler(() => {
      setAccessToken(null)
      setUser(null)
    })
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api.post('/auth/logout', { all_devices: false })
    } finally {
      setAccessToken(null)
      setUser(null)
    }
  }, [])

  const can = useCallback(
    (permission: string) => user?.permissions.includes(permission) ?? false,
    [user],
  )

  const value = useMemo<AuthState>(
    () => ({ user, status, signOut, can }),
    [user, status, signOut, can],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth(): AuthState {
  const value = use(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}

export function isStaff(user: CurrentUser | null): boolean {
  return user?.roles.some((role) => STAFF_ROLES.includes(role)) ?? false
}

/**
 * Sign-in for the admin panel.
 *
 * Deliberately spartan and deliberately vague: "this account cannot use the
 * admin panel" rather than "you are not an admin", because the second sentence
 * confirms to whoever is trying that the panel exists and that accounts differ.
 */
export function SignInScreen() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await api.post<{ tokens: { access_token: string } }>('/auth/login', {
        email,
        password,
        device_label: 'Admin panel',
      })
      setAccessToken(result.tokens.access_token)
      // A full reload rather than setState: it re-runs the restore path, so
      // there is exactly one code path that establishes a session.
      window.location.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not sign in')
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-ink-100 px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl border border-ink-200 bg-white p-6"
      >
        <h1 className="text-lg font-semibold text-ink-900">Admin</h1>
        <p className="mt-1 text-sm text-ink-500">Roaming &amp; Wandering</p>

        {error && (
          <p role="alert" className="mt-4 rounded-lg bg-bad-50 px-3 py-2 text-sm text-bad-700">
            {error}
          </p>
        )}

        <label className="mt-5 block text-sm font-medium text-ink-700">
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            required
            className="mt-1 h-10 w-full rounded-lg border border-ink-200 px-3 text-sm"
          />
        </label>
        <label className="mt-3 block text-sm font-medium text-ink-700">
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
            className="mt-1 h-10 w-full rounded-lg border border-ink-200 px-3 text-sm"
          />
        </label>

        <Button type="submit" variant="primary" disabled={busy} className="mt-5 w-full">
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
    </div>
  )
}

export function NotStaffScreen({ onSignOut }: { onSignOut: () => void }) {
  return (
    <div className="grid min-h-dvh place-items-center bg-ink-100 px-4">
      <div className="max-w-sm rounded-xl border border-ink-200 bg-white p-6 text-center">
        <h1 className="text-lg font-semibold text-ink-900">No access</h1>
        <p className="mt-2 text-sm text-ink-600">
          This account cannot use the admin panel.
        </p>
        <Button className="mt-5" onClick={onSignOut}>
          Sign out
        </Button>
      </div>
    </div>
  )
}
