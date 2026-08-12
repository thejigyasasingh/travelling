import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useRepositories } from '@/application/RepositoryContext'
import { Button } from '@/ui/Button'
import { Input } from '@/ui/Field'

/**
 * Forgot password.
 *
 * The confirmation is deliberately identical whether or not the address is
 * registered. Saying "no account with that email" is an account-enumeration
 * oracle: it lets anyone test a list of addresses against the site. The server
 * behaves the same way, and this page must not undo that by reporting an error
 * the server took care not to give.
 */
export default function ForgotPasswordPage() {
  const { auth } = useRepositories()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    void (async () => {
      try {
        await auth.forgotPassword(email)
      } catch {
        // Swallowed on purpose — see above. A rate-limit or outage still ends
        // in the same message, which is the honest thing to show: we have
        // accepted the request.
      } finally {
        setBusy(false)
        setSent(true)
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
          If an account exists for <strong>{email}</strong>, a reset link is on its way. The link
          expires in an hour and can only be used once.
        </p>
        <p className="mt-4 text-sm text-ink-500">
          Nothing arrived? Check spam, then{' '}
          <button
            type="button"
            onClick={() => setSent(false)}
            className="text-brand-600 hover:underline"
          >
            try another address
          </button>
          .
        </p>
        <Link to="/login" className="mt-8 inline-block text-sm text-brand-600 hover:underline">
          Back to sign in
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12 sm:px-6">
      <h1 className="text-2xl font-bold tracking-tight text-ink-900">Reset your password</h1>
      <p className="mt-1 text-sm text-ink-500">
        Enter the email you signed up with and we will send a reset link.
      </p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
          autoFocus
        />
        <Button type="submit" size="lg" fullWidth loading={busy}>
          Send reset link
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-600">
        <Link to="/login" className="text-brand-600 hover:underline">
          Back to sign in
        </Link>
      </p>
    </div>
  )
}
