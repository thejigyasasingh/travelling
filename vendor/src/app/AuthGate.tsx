import {
  createContext,
  use,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, setAccessToken, setSessionLostHandler } from '@/core/http'
import { Button } from '@/ui/primitives'

/**
 * Who is signed in, and whether they host anything.
 *
 * **Defence in depth, not the enforcement.** Every vendor endpoint derives the
 * vendor from the token and filters on it server-side; this gate exists so a
 * traveler who finds the URL gets a sentence rather than eight panels that all
 * 404, and so an applicant awaiting approval is told where their application
 * stands instead of being shown an empty revenue chart.
 *
 * `vendor_id` on the user is what makes the portal work at all. It is set when
 * a vendor registers, and until it is set every endpoint here correctly refuses
 * to guess which business the caller means.
 */
export interface CurrentUser {
  id: string
  email: string
  full_name: string | null
  roles: string[]
  permissions: string[]
  vendor_id: string | null
}

interface AuthState {
  readonly user: CurrentUser | null
  readonly status: 'restoring' | 'ready'
  readonly signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [status, setStatus] = useState<'restoring' | 'ready'>('restoring')

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        // The HttpOnly refresh cookie is the credential; the access token lives
        // only in memory, so a reload always starts here.
        const tokens = await api.post<{ tokens: { access_token: string } }>('/auth/refresh', {})
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

  const value = useMemo<AuthState>(() => ({ user, status, signOut }), [user, status, signOut])

  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth(): AuthState {
  const value = use(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}

export function hostsProperties(user: CurrentUser | null): boolean {
  return Boolean(user?.vendor_id)
}

/**
 * Sign-in.
 *
 * The failure message stays vague — "could not sign in", never "no such
 * account" — because the difference between the two tells whoever is trying
 * which addresses are registered.
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
        device_label: 'Host portal',
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
        <h1 className="text-lg font-semibold text-ink-900">Host portal</h1>
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

/**
 * Signed in, but not a host.
 *
 * Says what to do next rather than only refusing. The overwhelmingly likely
 * reader is someone who signed in with their traveller account by mistake, or
 * whose application has not been submitted yet.
 */
export function NotAHostScreen({ onSignOut }: { onSignOut: () => void }) {
  return (
    <div className="grid min-h-dvh place-items-center bg-ink-100 px-4">
      <div className="max-w-md rounded-xl border border-ink-200 bg-white p-6 text-center">
        <h1 className="text-lg font-semibold text-ink-900">No properties on this account</h1>
        <p className="mt-2 text-sm text-ink-600">
          This portal is for hosts listing properties. If you applied recently, the account you
          applied with is the one to sign in with here.
        </p>
        <Button className="mt-5" onClick={onSignOut}>
          Sign out
        </Button>
      </div>
    </div>
  )
}
