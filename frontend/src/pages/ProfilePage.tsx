import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/app/AuthProvider'
import { useRepositories } from '@/application/RepositoryContext'
import { useBookings } from '@/application/hooks/useBookings'
import { useWishlist } from '@/application/hooks/useWishlist'
import { displayName, initials } from '@/domain/user'
import { formatDateTime } from '@/core/dates'
import { messageFor } from '@/core/errors'
import { Button, ButtonLink } from '@/ui/Button'
import { Input } from '@/ui/Field'
import { Badge, LoadingBlock } from '@/ui/feedback'
import { Modal } from '@/ui/Modal'

/**
 * Profile.
 *
 * **The API has no "update profile" endpoint yet** — `/auth/me` is read-only,
 * and the only mutations auth exposes are password change, phone link and email
 * re-verification. So this page shows what is true and offers exactly the
 * actions that exist. A name field that silently discarded what was typed would
 * be worse than no field.
 */
export default function ProfilePage() {
  const { user, status } = useAuth()
  const { auth } = useRepositories()
  const { data: bookings } = useBookings()
  const { data: wishlist } = useWishlist()

  const [linkingPhone, setLinkingPhone] = useState(false)
  const [phone, setPhone] = useState('')
  const [challengeId, setChallengeId] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (status === 'restoring') return <LoadingBlock />
  if (!user) return null

  const tripCount = bookings?.items.length ?? 0
  const savedCount = wishlist?.length ?? 0

  async function resendVerification() {
    setBusy(true)
    setError(null)
    try {
      await auth.resendVerification()
      setNotice('Verification email sent. Check your inbox.')
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  async function startPhoneLink(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const challenge = await auth.requestOtp({ phone, purpose: 'link_phone' })
      setChallengeId(challenge.challengeId)
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  async function confirmPhoneLink(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await auth.verifyOtp({ challengeId: challengeId as string, code })
      setLinkingPhone(false)
      setChallengeId(null)
      setCode('')
      setNotice('Phone number linked.')
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex items-center gap-4">
        <span className="grid size-16 place-items-center rounded-full bg-brand-600 text-xl font-semibold text-white">
          {initials(user)}
        </span>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">{displayName(user)}</h1>
          <p className="text-sm text-ink-500">{user.email}</p>
        </div>
      </div>

      {notice && (
        <p role="status" className="mt-4 rounded-xl bg-success-50 p-3 text-sm text-success-700">
          {notice}
        </p>
      )}
      {error !== null && (
        <p role="alert" className="mt-4 rounded-xl bg-danger-50 p-3 text-sm text-danger-700">
          {messageFor(error)}
        </p>
      )}

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <StatCard label="Trips" value={tripCount} to="/trips" />
        <StatCard label="Saved stays" value={savedCount} to="/wishlist" />
        <StatCard
          label="Member since"
          value={user.lastLoginAt ? formatDateTime(user.lastLoginAt).split(',')[0] ?? '—' : '—'}
        />
      </div>

      <section className="mt-8 rounded-2xl border border-ink-100">
        <h2 className="border-b border-ink-100 px-5 py-4 font-semibold text-ink-900">
          Contact details
        </h2>
        <dl className="divide-y divide-ink-100">
          <Row label="Email" value={user.email}>
            {user.emailVerified ? (
              <Badge tone="success">Verified</Badge>
            ) : (
              <div className="flex items-center gap-2">
                <Badge tone="pending">Unverified</Badge>
                <Button size="sm" variant="ghost" loading={busy} onClick={() => void resendVerification()}>
                  Resend
                </Button>
              </div>
            )}
          </Row>

          <Row label="Phone" value={user.phone ?? 'Not linked'}>
            {user.phone && user.phoneVerified ? (
              <Badge tone="success">Verified</Badge>
            ) : (
              <Button size="sm" variant="secondary" onClick={() => setLinkingPhone(true)}>
                {user.phone ? 'Verify' : 'Add a number'}
              </Button>
            )}
          </Row>

          <Row label="Password" value={user.hasPassword ? '••••••••••••' : 'Not set (Google sign-in)'}>
            <ButtonLink to="/settings" size="sm" variant="ghost">
              {user.hasPassword ? 'Change' : 'Set a password'}
            </ButtonLink>
          </Row>
        </dl>
      </section>

      {!user.emailVerified && (
        <p className="mt-4 rounded-xl bg-warning-50 p-4 text-sm text-warning-700">
          Your email is not verified yet. Booking confirmations and GST invoices are sent there, so
          it is worth doing before your next trip.
        </p>
      )}

      <p className="mt-8 text-sm text-ink-500">
        Looking for sessions, password or notifications?{' '}
        <Link to="/settings" className="text-brand-600 hover:underline">
          Account settings
        </Link>
      </p>

      <Modal
        open={linkingPhone}
        onClose={() => {
          setLinkingPhone(false)
          setChallengeId(null)
        }}
        title="Link a phone number"
        description="The property may need to reach you about your arrival."
        footer={
          <Button variant="ghost" onClick={() => setLinkingPhone(false)}>
            Cancel
          </Button>
        }
      >
        {challengeId === null ? (
          <form onSubmit={startPhoneLink} className="space-y-4">
            <Input
              label="Phone number"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91 98765 43210"
              required
            />
            <Button type="submit" fullWidth loading={busy}>
              Send code
            </Button>
          </form>
        ) : (
          <form onSubmit={confirmPhoneLink} className="space-y-4">
            <Input
              label="Six-digit code"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              autoComplete="one-time-code"
              required
            />
            <Button type="submit" fullWidth loading={busy}>
              Verify
            </Button>
          </form>
        )}
      </Modal>
    </div>
  )
}

function StatCard({ label, value, to }: { label: string; value: string | number; to?: string }) {
  const body = (
    <>
      <div className="text-2xl font-semibold text-ink-900">{value}</div>
      <div className="text-sm text-ink-500">{label}</div>
    </>
  )
  return to ? (
    <Link to={to} className="rounded-2xl border border-ink-100 p-4 transition-colors hover:border-brand-300">
      {body}
    </Link>
  ) : (
    <div className="rounded-2xl border border-ink-100 p-4">{body}</div>
  )
}

function Row({
  label,
  value,
  children,
}: {
  label: string
  value: string
  children?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
      <div>
        <dt className="text-xs font-medium text-ink-500">{label}</dt>
        <dd className="mt-0.5 text-sm text-ink-900">{value}</dd>
      </div>
      {children}
    </div>
  )
}
