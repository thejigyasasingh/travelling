import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useRepositories } from '@/application/RepositoryContext'
import { queryKeys } from '@/application/queryKeys'
import { useAuth } from '@/app/AuthProvider'
import { formatDateTime, formatRelative } from '@/core/dates'
import { messageFor } from '@/core/errors'
import { readJson, writeJson } from '@/infrastructure/storage/localStore'
import { Button } from '@/ui/Button'
import { Checkbox, Input } from '@/ui/Field'
import { Badge, ErrorState, Skeleton } from '@/ui/feedback'
import { Modal } from '@/ui/Modal'

const MIN_PASSWORD = 12

interface Preferences {
  bookingEmails: boolean
  marketingEmails: boolean
  priceAlerts: boolean
}

const DEFAULT_PREFERENCES: Preferences = {
  bookingEmails: true,
  marketingEmails: false,
  priceAlerts: false,
}

/**
 * Settings: password, sessions, notifications, sign-out.
 *
 * The **sessions** list is the part that matters. It is the only place a guest
 * can see that someone else is signed into their account and end it, which is
 * the entire point of tracking sessions server-side. Each row shows a device
 * label and when it was last used, because "Chrome on Windows, 3 minutes ago"
 * is what makes an unfamiliar entry recognisable as unfamiliar.
 *
 * Notification preferences are stored on the device: there is no preferences
 * endpoint yet, and that is said on the page rather than implied.
 */
export default function SettingsPage() {
  const { auth } = useRepositories()
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const sessions = useQuery({
    queryKey: queryKeys.auth.sessions,
    queryFn: ({ signal }) => auth.sessions(signal),
  })

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [confirmSignOutAll, setConfirmSignOutAll] = useState(false)

  const [preferences, setPreferences] = useState<Preferences>(() =>
    readJson('preferences', DEFAULT_PREFERENCES),
  )

  function updatePreference(patch: Partial<Preferences>) {
    const next = { ...preferences, ...patch }
    setPreferences(next)
    writeJson('preferences', next)
  }

  async function changePassword(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await auth.changePassword({ currentPassword, newPassword })
      setCurrentPassword('')
      setNewPassword('')
      // Changing a password revokes every other session server-side, so the
      // list on screen is now wrong.
      void queryClient.invalidateQueries({ queryKey: queryKeys.auth.sessions })
      setNotice('Password changed. Other devices have been signed out.')
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  async function revoke(sessionId: string) {
    try {
      await auth.revokeSession(sessionId)
      void queryClient.invalidateQueries({ queryKey: queryKeys.auth.sessions })
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold tracking-tight text-ink-900">Settings</h1>

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

      <section className="mt-6 rounded-2xl border border-ink-100 p-5">
        <h2 className="font-semibold text-ink-900">
          {user?.hasPassword ? 'Change password' : 'Set a password'}
        </h2>
        <p className="mt-1 text-sm text-ink-500">
          {user?.hasPassword
            ? 'Changing your password signs out every other device.'
            : 'You signed up with Google. Setting a password lets you sign in either way.'}
        </p>
        <form onSubmit={changePassword} className="mt-4 space-y-4">
          {user?.hasPassword && (
            <Input
              label="Current password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          )}
          <Input
            label="New password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            minLength={MIN_PASSWORD}
            hint={`At least ${MIN_PASSWORD} characters.`}
            required
          />
          <Button type="submit" loading={busy} disabled={newPassword.length < MIN_PASSWORD}>
            Update password
          </Button>
        </form>
      </section>

      <section className="mt-6 rounded-2xl border border-ink-100 p-5">
        <h2 className="font-semibold text-ink-900">Signed-in devices</h2>
        <p className="mt-1 text-sm text-ink-500">
          Anything here you do not recognise, end it — then change your password.
        </p>

        <div className="mt-4">
          {sessions.isPending ? (
            <div className="space-y-2">
              {Array.from({ length: 2 }, (_, i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
          ) : sessions.isError ? (
            <ErrorState error={sessions.error} onRetry={() => void sessions.refetch()} />
          ) : (
            <ul className="divide-y divide-ink-100">
              {sessions.data?.map((session) => (
                <li key={session.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-sm font-medium text-ink-900">
                      {session.deviceLabel ?? 'Unknown device'}
                      {session.isCurrent && <Badge tone="active">This device</Badge>}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-500">
                      Last used {formatRelative(session.lastUsedAt ?? session.createdAt)} · expires{' '}
                      {formatDateTime(session.expiresAt)}
                    </p>
                  </div>
                  {!session.isCurrent && (
                    <Button variant="ghost" size="sm" onClick={() => void revoke(session.id)}>
                      Sign out
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <Button variant="secondary" size="sm" className="mt-4" onClick={() => setConfirmSignOutAll(true)}>
          Sign out everywhere
        </Button>
      </section>

      <section className="mt-6 rounded-2xl border border-ink-100 p-5">
        <h2 className="font-semibold text-ink-900">Notifications</h2>
        <p className="mt-1 text-sm text-ink-500">
          Saved on this device for now — a server-side preference centre is coming.
        </p>
        <div className="mt-4 space-y-3">
          <Checkbox
            label="Booking emails"
            description="Confirmations, invoices and cancellation notices. These are transactional and cannot be turned off."
            checked
            disabled
            readOnly
          />
          <Checkbox
            label="Offers and inspiration"
            description="Occasional emails about places to go."
            checked={preferences.marketingEmails}
            onChange={(e) => updatePreference({ marketingEmails: e.target.checked })}
          />
          <Checkbox
            label="Price alerts for saved stays"
            description="Tell me when something on my wishlist drops in price."
            checked={preferences.priceAlerts}
            onChange={(e) => updatePreference({ priceAlerts: e.target.checked })}
          />
        </div>
      </section>

      <section className="mt-6 rounded-2xl border border-danger-200 bg-danger-50/40 p-5">
        <h2 className="font-semibold text-ink-900">Sign out</h2>
        <p className="mt-1 text-sm text-ink-600">
          End this session on this device. Your trips and saved stays stay where they are.
        </p>
        <Button
          variant="secondary"
          className="mt-4"
          onClick={() => {
            void signOut().then(() => navigate('/'))
          }}
        >
          Sign out
        </Button>
      </section>

      <Modal
        open={confirmSignOutAll}
        onClose={() => setConfirmSignOutAll(false)}
        title="Sign out of every device?"
        description="Every phone, tablet and browser signed into this account will be signed out, including this one."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmSignOutAll(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                void signOut(true).then(() => navigate('/'))
              }}
            >
              Sign out everywhere
            </Button>
          </>
        }
      />
    </div>
  )
}
