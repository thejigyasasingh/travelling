import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useRepositories } from '@/application/RepositoryContext'
import { isApiError, messageFor } from '@/core/errors'
import { Button, ButtonLink } from '@/ui/Button'
import { Checkbox, Input } from '@/ui/Field'
import { safeNext } from '@/core/urls'

/** Password rules, mirroring the server's. Shown up front rather than as a
 *  rejection after submitting — a rule you learn by failing is a bad rule. */
const MIN_PASSWORD = 12

export default function RegisterPage() {
  const [params] = useSearchParams()
  const { auth } = useRepositories()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)

  const next = safeNext(params.get('next'))
  const tooShort = password.length > 0 && password.length < MIN_PASSWORD

  // The server returns per-field messages; showing them on the right input is
  // the difference between "fix this" and "something was wrong".
  const fieldError = (field: string) =>
    isApiError(error) ? error.fieldIssues.find((i) => i.field === field)?.message : undefined

  function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    void (async () => {
      try {
        await auth.register({ email, password, fullName })
        // No tokens come back and none should: the account is not usable until
        // the address is verified, and the response deliberately does not say
        // whether it was already registered.
        setSent(true)
      } catch (caught) {
        setError(caught)
      } finally {
        setBusy(false)
      }
    })()
  }

  if (sent) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center sm:px-6">
        <div className="mx-auto grid size-12 place-items-center rounded-full bg-brand-50 text-brand-700">
          ✉
        </div>
        <h1 className="mt-5 text-xl font-semibold text-ink-900">Check your inbox</h1>
        <p className="mt-2 text-sm text-ink-600">
          We have sent a link to <strong>{email}</strong>. Open it to finish setting up your
          account, then sign in.
        </p>
        <p className="mt-4 text-xs text-ink-500">
          If that address already has an account, the email will say so instead — we do not reveal
          which addresses are registered.
        </p>
        <ButtonLink
          to={`/login${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`}
          className="mt-6"
        >
          Go to sign in
        </ButtonLink>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-md flex-col px-4 py-12 sm:px-6">
      <h1 className="text-2xl font-bold tracking-tight text-ink-900">Create your account</h1>
      <p className="mt-1 text-sm text-ink-500">
        One account for booking, trips and invoices.
      </p>

      {error !== null && !isApiError(error) && (
        <div role="alert" className="mt-4 rounded-xl bg-danger-50 p-3 text-sm text-danger-700">
          {messageFor(error)}
        </div>
      )}
      {isApiError(error) && error.fieldIssues.length === 0 && (
        <div role="alert" className="mt-4 rounded-xl bg-danger-50 p-3 text-sm text-danger-700">
          {messageFor(error)}
        </div>
      )}

      <form onSubmit={submit} className="mt-5 space-y-4">
        <Input
          label="Full name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          autoComplete="name"
          error={fieldError('full_name')}
          autoFocus
        />
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          error={fieldError('email')}
          required
        />
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          minLength={MIN_PASSWORD}
          error={fieldError('password') ?? (tooShort ? `At least ${MIN_PASSWORD} characters.` : undefined)}
          hint={`At least ${MIN_PASSWORD} characters. A phrase you can remember beats a short jumble.`}
          required
        />

        <Checkbox
          label={
            <>
              I agree to the terms of service and privacy policy.
            </>
          }
          checked={accepted}
          onChange={(e) => setAccepted(e.target.checked)}
          required
        />

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={busy}
          disabled={!accepted || password.length < MIN_PASSWORD}
        >
          Create account
        </Button>
      </form>

      <p className="mt-8 text-center text-sm text-ink-600">
        Already have an account?{' '}
        <Link
          to={`/login${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`}
          className="font-medium text-brand-600 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </div>
  )
}
