import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useRepositories } from '@/application/RepositoryContext'
import { useAuth } from '@/app/AuthProvider'
import { ErrorCode, hasErrorCode, messageFor } from '@/core/errors'
import { Button } from '@/ui/Button'
import { Input } from '@/ui/Field'
import { safeNext } from '@/core/urls'
import { cn } from '@/ui/cn'

type Method = 'password' | 'otp'

/**
 * Sign in.
 *
 * The `next` parameter is validated before use. An open redirect on a login
 * page is a phishing primitive: `?next=https://evil.example` would send a
 * freshly-authenticated user off-site with the site's own domain in the referrer.
 * Only same-site paths are honoured.
 */
export default function LoginPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { auth } = useRepositories()
  const { signIn } = useAuth()

  const [method, setMethod] = useState<Method>('password')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [phone, setPhone] = useState('')
  const [challengeId, setChallengeId] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const next = safeNext(params.get('next'))

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  const submitPassword = (event: React.FormEvent) => {
    event.preventDefault()
    void run(async () => {
      const result = await auth.login({ email, password })
      signIn(result.user)
      void navigate(next, { replace: true })
    })
  }

  const requestOtp = (event: React.FormEvent) => {
    event.preventDefault()
    void run(async () => {
      const challenge = await auth.requestOtp({ phone })
      setChallengeId(challenge.challengeId)
    })
  }

  const submitOtp = (event: React.FormEvent) => {
    event.preventDefault()
    void run(async () => {
      const result = await auth.verifyOtp({ challengeId: challengeId as string, code })
      signIn(result.user)
      void navigate(next, { replace: true })
    })
  }

  const locked = hasErrorCode(error, ErrorCode.ACCOUNT_LOCKED)

  return (
    <div className="mx-auto flex max-w-md flex-col px-4 py-12 sm:px-6">
      <h1 className="text-2xl font-bold tracking-tight text-ink-900">Welcome back</h1>
      <p className="mt-1 text-sm text-ink-500">Sign in to manage your trips and bookings.</p>

      <div className="mt-6 flex rounded-xl bg-ink-100 p-1">
        {(['password', 'otp'] as const).map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => {
              setMethod(value)
              setError(null)
            }}
            aria-pressed={method === value}
            className={cn(
              'flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              method === value ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-600',
            )}
          >
            {value === 'password' ? 'Email' : 'Phone OTP'}
          </button>
        ))}
      </div>

      {error !== null && (
        <div role="alert" className="mt-4 rounded-xl bg-danger-50 p-3 text-sm text-danger-700">
          {locked
            ? 'Too many attempts. This account is locked for a short while — try again shortly, or reset your password.'
            : messageFor(error)}
        </div>
      )}

      {method === 'password' ? (
        <form onSubmit={submitPassword} className="mt-5 space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
            autoFocus
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
          <div className="flex justify-end">
            <Link to="/forgot-password" className="text-sm text-brand-600 hover:underline">
              Forgot your password?
            </Link>
          </div>
          <Button type="submit" size="lg" fullWidth loading={busy}>
            Sign in
          </Button>
        </form>
      ) : challengeId === null ? (
        <form onSubmit={requestOtp} className="mt-5 space-y-4">
          <Input
            label="Phone number"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+91 98765 43210"
            autoComplete="tel"
            hint="We will text you a six-digit code."
            required
            autoFocus
          />
          <Button type="submit" size="lg" fullWidth loading={busy}>
            Send code
          </Button>
        </form>
      ) : (
        <form onSubmit={submitOtp} className="mt-5 space-y-4">
          <Input
            label="Six-digit code"
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            autoComplete="one-time-code"
            hint={`Sent to ${phone}`}
            required
            autoFocus
          />
          <Button type="submit" size="lg" fullWidth loading={busy}>
            Verify and sign in
          </Button>
          <button
            type="button"
            onClick={() => {
              setChallengeId(null)
              setCode('')
            }}
            className="w-full text-sm text-ink-500 hover:text-ink-800"
          >
            Use a different number
          </button>
        </form>
      )}

      <p className="mt-8 text-center text-sm text-ink-600">
        New here?{' '}
        <Link
          to={`/register${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`}
          className="font-medium text-brand-600 hover:underline"
        >
          Create an account
        </Link>
      </p>
    </div>
  )
}
