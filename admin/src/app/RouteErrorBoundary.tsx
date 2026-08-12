import { isRouteErrorResponse, useNavigate, useRouteError } from 'react-router-dom'
import { ApiError } from '@/core/http'
import { Button, Card } from '@/ui/primitives'

/**
 * The last line of defence.
 *
 * Without one of these a render error unmounts the whole tree and leaves a
 * white page — no message, no navigation, no indication that anything happened
 * beyond the browser going blank. The customer site has had one since it was
 * built; the two internal tools did not, which is backwards. An admin who hits
 * a blank screen mid-moderation files a ticket about *the platform* being
 * down, and the on-call engineer starts by checking the API.
 *
 * Three things it must do, in order of how often they matter:
 *
 * 1. **Say what happened**, distinguishing a permission refusal from a bug —
 *    those have completely different next steps and only one is worth
 *    reporting.
 * 2. **Offer a way out.** A dead end with no navigation is a closed tab.
 * 3. **Show the request id.** Support quoting one turns "the admin panel broke"
 *    into a single log lookup.
 */
export function RouteErrorBoundary() {
  const error = useRouteError()
  const navigate = useNavigate()

  const status = isRouteErrorResponse(error)
    ? error.status
    : error instanceof ApiError
      ? error.status
      : null

  const forbidden = status === 403
  const notFound = status === 404

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 px-4 py-16">
      <Card>
        <div className="flex flex-col gap-3 p-6">
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            {status ?? 'Error'}
          </p>
          <h1 className="text-lg font-semibold text-ink-900">
            {forbidden
              ? 'You do not have access to this'
              : notFound
                ? 'That page does not exist'
                : 'Something went wrong'}
          </h1>
          <p className="text-sm text-ink-500">
            {forbidden
              ? 'Your account is missing a permission this screen needs. Ask an administrator to grant it — retrying will not help.'
              : notFound
                ? 'The link may be stale, or the record may have been removed.'
                : describe(error)}
          </p>

          {/* Only for a real fault. A 403 has nothing to look up — the request
              reached us and was answered correctly. */}
          {requestIdOf(error) && !forbidden && !notFound ? (
            <p className="font-mono text-xs text-ink-400">
              Request {requestIdOf(error)} — quote this to support
            </p>
          ) : null}

          <div className="mt-2 flex gap-2">
            {/* `reload`, not a re-render. The error boundary has already torn
                the tree down; a router navigation would land on a component
                whose state is gone but whose caches are not. */}
            <Button variant="primary" onClick={() => window.location.reload()}>
              Reload
            </Button>
            <Button variant="secondary" onClick={() => void navigate('/')}>
              Back to dashboard
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (isRouteErrorResponse(error)) return error.statusText || 'The request failed.'
  // Deliberately not `String(error)`. An unhandled `TypeError` reads as
  // gibberish to an admin, and the stack is already in the console for whoever
  // is debugging it.
  return 'An unexpected error occurred. Reloading usually clears it.'
}

function requestIdOf(error: unknown): string | null {
  return error instanceof ApiError ? error.requestId : null
}
