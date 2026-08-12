/**
 * Session state for the UI.
 *
 * The access token itself lives in `tokenStore` (module scope, in memory) and
 * deliberately *not* here: interceptors need it outside React, and putting it
 * in context would re-render the tree on every silent refresh. What lives here
 * is the part the UI actually renders — who is signed in.
 *
 * On boot the app calls `/auth/refresh` with no body. The HttpOnly cookie is
 * the credential, so a reload restores the session without any long-lived token
 * ever being reachable from JavaScript.
 */

import {
  createContext,
  use,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { mergeLocalInto } from '@/infrastructure/api/wishlist'
import { useRepositories } from '@/application/RepositoryContext'
import { restoreSession } from '@/infrastructure/api/auth'
import { setSessionLostHandler } from '@/infrastructure/http/client'
import type { User } from '@/domain/user'

export type AuthStatus = 'restoring' | 'authenticated' | 'anonymous'

interface AuthState {
  readonly user: User | null
  readonly status: AuthStatus
  readonly isAuthenticated: boolean
  readonly signIn: (user: User) => void
  readonly signOut: (allDevices?: boolean) => Promise<void>
  readonly refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { auth } = useRepositories()
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthStatus>('restoring')

  useEffect(() => {
    let cancelled = false
    void restoreSession().then((result) => {
      if (cancelled) return
      setUser(result?.user ?? null)
      setStatus(result ? 'authenticated' : 'anonymous')
    })
    return () => {
      cancelled = true
    }
  }, [])

  // The client calls this when a refresh fails for good. Without it the UI
  // would keep rendering a signed-in header while every request 401s.
  useEffect(() => {
    setSessionLostHandler(() => {
      setUser(null)
      setStatus('anonymous')
      queryClient.clear()
    })
    return () => setSessionLostHandler(() => {})
  }, [queryClient])

  const signIn = useCallback(
    (next: User) => {
      setUser(next)
      setStatus('authenticated')
      // Anything cached for the previous visitor — including "no bookings" —
      // belongs to a different person.
      queryClient.clear()

      // Hand this device's signed-out wishlist to the account. Fire and
      // forget, deliberately: sign-in must not wait on it, and must not fail
      // because of it. The server is additive and idempotent, so the local
      // list survives a failure here and merges on the next sign-in.
      void mergeLocalInto()
        .then((merged) => {
          if (merged > 0) void queryClient.invalidateQueries({ queryKey: ['wishlist'] })
        })
        .catch(() => {
          /* the local list is untouched on failure; nothing is lost */
        })
    },
    [queryClient],
  )

  const signOut = useCallback(
    async (allDevices = false) => {
      await auth.logout(allDevices)
      setUser(null)
      setStatus('anonymous')
      // Not just invalidate: another user on a shared laptop must not be able
      // to read the previous one's trips out of a warm cache.
      queryClient.clear()
    },
    [auth, queryClient],
  )

  const refreshUser = useCallback(async () => {
    try {
      setUser(await auth.me())
    } catch {
      // A failed re-read is not a sign-out; the interceptor owns that decision.
    }
  }, [auth])

  const value = useMemo<AuthState>(
    () => ({
      user,
      status,
      isAuthenticated: status === 'authenticated' && user !== null,
      signIn,
      signOut,
      refreshUser,
    }),
    [user, status, signIn, signOut, refreshUser],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth(): AuthState {
  const value = use(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
