import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useRepositories } from '@/application/RepositoryContext'
import { useAuth } from '@/app/AuthProvider'
import { messageFor } from '@/core/errors'
import { ButtonLink } from '@/ui/Button'
import { LoadingBlock } from '@/ui/feedback'

/** Landing page for the link in the verification email. */
export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const { auth } = useRepositories()
  const { refreshUser, isAuthenticated } = useAuth()
  const token = params.get('token') ?? ''

  const [state, setState] = useState<'verifying' | 'done' | 'failed'>('verifying')
  const [error, setError] = useState<unknown>(null)
  // StrictMode double-mounts effects in development, and a verification token
  // is single-use — the second call would fail and show an error for a
  // verification that actually succeeded.
  const attempted = useRef(false)

  useEffect(() => {
    if (!token || attempted.current) return
    attempted.current = true
    void (async () => {
      try {
        await auth.verifyEmail(token)
        if (isAuthenticated) await refreshUser()
        setState('done')
      } catch (caught) {
        setError(caught)
        setState('failed')
      }
    })()
  }, [token, auth, refreshUser, isAuthenticated])

  if (!token) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center sm:px-6">
        <h1 className="text-xl font-semibold text-ink-900">This link is incomplete</h1>
        <p className="mt-2 text-sm text-ink-600">Open the link from your email again.</p>
      </div>
    )
  }

  if (state === 'verifying') return <LoadingBlock label="Verifying your email" />

  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center sm:px-6">
      <div
        className={`mx-auto grid size-12 place-items-center rounded-full ${
          state === 'done' ? 'bg-success-50 text-success-700' : 'bg-danger-50 text-danger-700'
        }`}
      >
        {state === 'done' ? '✓' : '!'}
      </div>
      <h1 className="mt-5 text-xl font-semibold text-ink-900">
        {state === 'done' ? 'Email verified' : 'We could not verify that link'}
      </h1>
      <p className="mt-2 text-sm text-ink-600">
        {state === 'done'
          ? 'Thanks — your address is confirmed. Booking confirmations and invoices will reach you.'
          : `${messageFor(error)} Verification links expire, and each one works only once.`}
      </p>
      <div className="mt-6 flex justify-center gap-3">
        <ButtonLink to="/">Go home</ButtonLink>
        {state === 'failed' && (
          <ButtonLink to="/settings" variant="secondary">
            Send a new link
          </ButtonLink>
        )}
      </div>
      <p className="mt-6 text-xs text-ink-500">
        <Link to="/search" className="hover:underline">
          Or start looking for a stay
        </Link>
      </p>
    </div>
  )
}
