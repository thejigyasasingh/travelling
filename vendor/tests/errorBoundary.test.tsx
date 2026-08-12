/**
 * The boundary that stops one broken page blanking the whole tool.
 *
 * Without it a render error unmounts the tree and leaves a white page — no
 * message, no navigation, nothing to say anything happened. The customer site
 * has had one since it was built; the two internal tools did not, which is
 * backwards: a host who hits a blank screen mid-way through pricing a season
 * assumes their changes were lost, and re-enters all of them.
 *
 * These render a route that throws for real, through a real router, rather
 * than rendering the boundary component directly with a prop. Rendering it
 * directly would prove the markup is fine and prove nothing about whether the
 * router is wired to reach it — and the wiring is the part that was missing.
 */

import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RouteErrorBoundary } from '@/app/RouteErrorBoundary'
import { ApiError } from '@/core/http'

function Boom({ error }: { error: unknown }): never {
  throw error
}

function renderThrowing(error: unknown) {
  const router = createMemoryRouter(
    [{ path: '/', element: <Boom error={error} />, errorElement: <RouteErrorBoundary /> }],
    { initialEntries: ['/'] },
  )
  return render(<RouterProvider router={router} />)
}

beforeEach(() => {
  // React logs the caught error, which is correct and makes the test output
  // unreadable. Silenced here only — a boundary that swallows errors silently
  // in production would be a different and worse problem.
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('RouteErrorBoundary', () => {
  it('catches a render error instead of blanking the page', () => {
    renderThrowing(new TypeError('cannot read properties of undefined'))

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })

  it('always offers a way out', () => {
    // A dead end with no navigation is a closed tab.
    renderThrowing(new Error('boom'))

    expect(screen.getByRole('button', { name: /reload/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /overview/i })).toBeInTheDocument()
  })

  it('does not show a raw exception message to an admin', () => {
    // `TypeError: Cannot read properties of undefined (reading 'map')` is
    // gibberish to the person reading it and useful only in the console, where
    // it already is.
    renderThrowing(new TypeError("Cannot read properties of undefined (reading 'map')"))

    expect(screen.queryByText(/undefined/i)).toBeNull()
  })

  it('reports a permission failure as a refusal, not a fault', () => {
    // **The** distinction on this screen. A 403 is not a bug and not
    // retryable — telling an admin "something went wrong" sends a host to
    // support for something only an administrator can grant.
    renderThrowing(new ApiError(403, 'FORBIDDEN', 'Missing permission'))

    expect(screen.getByText(/do not have access/i)).toBeInTheDocument()
    expect(screen.queryByText(/something went wrong/i)).toBeNull()
  })

  it('says a permission failure will not resolve by retrying', () => {
    renderThrowing(new ApiError(403, 'FORBIDDEN', 'Missing permission'))

    expect(screen.getByText(/retrying will not help/i)).toBeInTheDocument()
  })

  it('reports a missing record as missing', () => {
    renderThrowing(new ApiError(404, 'NOT_FOUND', 'gone'))

    expect(screen.getByText(/does not exist/i)).toBeInTheDocument()
  })

  it('shows the request id for a real fault', () => {
    // Support quoting this turns "the portal broke" into one log lookup.
    renderThrowing(new ApiError(500, 'INTERNAL_ERROR', 'boom', {}, 'req-abc123'))

    expect(screen.getByText(/req-abc123/)).toBeInTheDocument()
  })

  it('does not show a request id for a permission refusal', () => {
    // There is nothing to look up: the request arrived and was answered
    // correctly. Offering an id invites a support ticket for a non-event.
    renderThrowing(new ApiError(403, 'FORBIDDEN', 'nope', {}, 'req-abc123'))

    expect(screen.queryByText(/req-abc123/)).toBeNull()
  })

  it('shows the status code when there is one', () => {
    renderThrowing(new ApiError(502, 'BAD_GATEWAY', 'upstream'))

    expect(screen.getByText('502')).toBeInTheDocument()
  })

  it('survives something thrown that is not an Error at all', () => {
    // `throw 'oops'` and `throw {code: 1}` are both legal, and a boundary that
    // assumes `.message` exists throws inside the boundary — which React
    // cannot catch, and which really does blank the page.
    renderThrowing('a bare string')

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })
})
