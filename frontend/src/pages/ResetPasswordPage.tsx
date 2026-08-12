import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useRepositories } from '@/application/RepositoryContext'
import { messageFor } from '@/core/errors'
import { Button } from '@/ui/Button'
import { Input } from '@/ui/Field'

const MIN_PASSWORD = 12

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { auth } = useRepositories()

  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const mismatch = confirm.length > 0 && password !== confirm

  if (!token) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center sm:px-6">
        <h1 className="text-xl font-semibold text-ink-900">This link is incomplete</h1>
        <p className="mt-2 text-sm text-ink-600">
          Reset links expire after an hour and work only once. Request a fresh one.
        </p>
        <Link to="/forgot-password" className="mt-6 inline-block text-sm text-brand-600 hover:underline">
          Send a new link
        </Link>
      </div>
    )
  }

  function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    void (async () => {
      try {
        await auth.resetPassword({ token, newPassword: password })
        // Signing them in automatically would be convenient and wrong: resetting
        // a password also signs out every other session, and the new password
        // should be typed once more where it counts.
        void navigate('/login?reset=1', { replace: true })
      } catch (caught) {
        setError(caught)
      } finally {
        setBusy(false)
      }
    })()
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12 sm:px-6">
      <h1 className="text-2xl font-bold tracking-tight text-ink-900">Choose a new password</h1>
      <p className="mt-1 text-sm text-ink-500">
        Setting a new password signs you out everywhere else.
      </p>

      {error !== null && (
        <div role="alert" className="mt-4 rounded-xl bg-danger-50 p-3 text-sm text-danger-700">
          {messageFor(error)} If the link has expired, request a new one.
        </div>
      )}

      <form onSubmit={submit} className="mt-6 space-y-4">
        <Input
          label="New password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          minLength={MIN_PASSWORD}
          hint={`At least ${MIN_PASSWORD} characters.`}
          required
          autoFocus
        />
        <Input
          label="Confirm new password"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          error={mismatch ? 'These do not match.' : undefined}
          required
        />
        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={busy}
          disabled={mismatch || password.length < MIN_PASSWORD}
        >
          Set new password
        </Button>
      </form>
    </div>
  )
}
