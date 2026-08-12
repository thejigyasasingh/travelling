import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom'
import { messageFor } from '@/core/errors'
import { ButtonLink } from '@/ui/Button'

/**
 * The last line of defence.
 *
 * A render error in one route must not blank the whole app. This catches it,
 * says something true, and always offers a way out — a dead end with no link
 * home is how a user closes the tab.
 */
export function RouteErrorBoundary() {
  const error = useRouteError()
  const status = isRouteErrorResponse(error) ? error.status : null

  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
      <p className="text-6xl font-bold text-brand-600">{status ?? '!'}</p>
      <h1 className="mt-4 text-xl font-semibold text-ink-900">
        {status === 404 ? 'We could not find that page' : 'Something went wrong'}
      </h1>
      <p className="mt-2 text-sm text-ink-500">
        {status === 404
          ? 'The link may be old, or the stay may no longer be listed.'
          : messageFor(error)}
      </p>
      <div className="mt-6 flex gap-3">
        <ButtonLink to="/" variant="secondary">
          Go home
        </ButtonLink>
        <ButtonLink to="/search">Search stays</ButtonLink>
      </div>
      <Link to="/trips" className="mt-4 text-sm text-brand-600 hover:underline">
        Or go to your trips
      </Link>
    </div>
  )
}
