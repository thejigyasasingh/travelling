/**
 * The HTTP client's refresh behaviour.
 *
 * The single-flight guarantee is the reason this file exists. The backend
 * rotates refresh tokens and **treats reuse as theft** — it revokes the whole
 * family and signs the user out everywhere. So N concurrent 401s must produce
 * exactly *one* refresh, or a page that happens to fire four queries at once
 * logs the user out of every device they own.
 *
 * That failure is invisible in development, where the token is always fresh,
 * and catastrophic in production. Hence a test.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { __resetRefreshState, http, setSessionLostHandler } from '@/infrastructure/http/client'
import { tokenStore } from '@/infrastructure/http/tokenStore'
import { ApiError, NetworkError } from '@/core/errors'

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  })
}

/**
 * What `/auth/refresh` actually returns: the full auth response, `{ tokens,
 * user }` — not a bare token. These fixtures mirror the real endpoint, verified
 * against a running server; a fixture that invents a flatter shape lets a bug
 * pass here and fail in production.
 */
function refreshResponse(accessToken = 'fresh', expiresIn = 900) {
  return jsonResponse({
    tokens: {
      access_token: accessToken,
      refresh_token: 'rotated-refresh-token',
      token_type: 'Bearer',
      expires_in: expiresIn,
      refresh_expires_in: 2_592_000,
    },
    user: { id: 'u1', email: 'guest@example.com' },
  })
}

function errorResponse(status: number, code: string, message: string) {
  return jsonResponse({ error: { code, message, request_id: 'req-123' } }, status)
}

beforeEach(() => {
  tokenStore.clear()
  __resetRefreshState()
  setSessionLostHandler(() => {})
  vi.restoreAllMocks()
})

describe('requests', () => {
  it('attaches the access token', async () => {
    tokenStore.set('token-abc', 900)
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await http.get('/ping')

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect((init.headers as Record<string, string>)['Authorization']).toBe('Bearer token-abc')
  })

  it('sends credentials so the HttpOnly refresh cookie travels', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await http.get('/ping')

    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).credentials).toBe('include')
  })

  it('repeats list parameters instead of comma-joining them', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await http.get('/search', { query: { amenity: ['wifi', 'pool'], q: 'Goa', empty: undefined } })

    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('amenity=wifi&amenity=pool')
    expect(url).toContain('q=Goa')
    expect(url).not.toContain('empty')
  })

  it('turns an error envelope into a typed ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(errorResponse(409, 'BOOKING_DATES_UNAVAILABLE', 'Those dates are gone.')),
    )

    const error = await http.get('/bookings').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe('BOOKING_DATES_UNAVAILABLE')
    expect((error as ApiError).status).toBe(409)
    expect((error as ApiError).requestId).toBe('req-123')
    // A 409 is a real conflict, not something a retry fixes.
    expect((error as ApiError).isTransient).toBe(false)
  })

  it('reports a dead network distinctly from a server error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(http.get('/ping')).rejects.toBeInstanceOf(NetworkError)
  })

  it('lets an abort through untouched so a cancelled query stays quiet', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('Aborted', 'AbortError')))
    await expect(http.get('/ping')).rejects.toThrowError(/Aborted/)
  })
})

describe('token refresh', () => {
  it('refreshes once on a 401 and replays the request', async () => {
    tokenStore.set('stale', 900)
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(errorResponse(401, 'TOKEN_EXPIRED', 'Expired'))
      .mockResolvedValueOnce(refreshResponse())
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(http.get('/auth/me')).resolves.toEqual({ ok: true })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(tokenStore.get()).toBe('fresh')
    // The replay carries the *new* token, not the stale one.
    const replay = fetchMock.mock.calls[2]?.[1] as RequestInit
    expect((replay.headers as Record<string, string>)['Authorization']).toBe('Bearer fresh')
  })

  it('refreshes ONCE for many concurrent 401s', async () => {
    tokenStore.set('stale', 900)
    let refreshCalls = 0

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/auth/refresh')) {
          refreshCalls += 1
          return Promise.resolve(refreshResponse())
        }
        // Anything still presenting the stale token is rejected, exactly as the
        // server would.
        return Promise.resolve(
          tokenStore.get() === 'fresh'
            ? jsonResponse({ ok: true })
            : errorResponse(401, 'TOKEN_EXPIRED', 'Expired'),
        )
      }),
    )

    await Promise.all([
      http.get('/bookings'),
      http.get('/payments'),
      http.get('/auth/me'),
      http.get('/wishlist'),
    ])

    // The whole point: four 401s, one refresh. More than one looks like token
    // reuse to the server and signs the user out everywhere.
    expect(refreshCalls).toBe(1)
  })

  it('treats a refresh response without tokens as a failed refresh', async () => {
    // The bug this guards: reading `access_token` off the top level of the
    // response silently yields `undefined`, and every later request carries
    // `Bearer undefined` while the app still believes it is signed in.
    tokenStore.set('stale', 900)
    const onLost = vi.fn()
    setSessionLostHandler(onLost)

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) =>
        Promise.resolve(
          url.includes('/auth/refresh')
            ? jsonResponse({ access_token: 'flat-and-wrong', expires_in: 900 })
            : errorResponse(401, 'TOKEN_EXPIRED', 'Expired'),
        ),
      ),
    )

    await expect(http.get('/auth/me')).rejects.toBeInstanceOf(ApiError)
    expect(tokenStore.get()).toBeNull()
    expect(onLost).toHaveBeenCalledOnce()
  })

  it('gives up and reports the session lost when the refresh fails', async () => {
    tokenStore.set('stale', 900)
    const onLost = vi.fn()
    setSessionLostHandler(onLost)

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) =>
        Promise.resolve(
          url.includes('/auth/refresh')
            ? errorResponse(401, 'TOKEN_INVALID', 'Invalid')
            : errorResponse(401, 'TOKEN_EXPIRED', 'Expired'),
        ),
      ),
    )

    await expect(http.get('/auth/me')).rejects.toBeInstanceOf(ApiError)
    expect(tokenStore.get()).toBeNull()
    expect(onLost).toHaveBeenCalledOnce()
  })

  it('does not retry a 401 twice — one replay, then the error stands', async () => {
    tokenStore.set('stale', 900)
    const fetchMock = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        url.includes('/auth/refresh')
          ? refreshResponse()
          : errorResponse(401, 'TOKEN_EXPIRED', 'Expired'),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(http.get('/auth/me')).rejects.toBeInstanceOf(ApiError)
    // request, refresh, replay — and then it stops. An unbounded loop here
    // would hammer the auth endpoint until the tab was closed.
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('never attaches a token or refreshes for an anonymous call', async () => {
    const fetchMock = vi.fn().mockResolvedValue(errorResponse(401, 'UNAUTHENTICATED', 'Nope'))
    vi.stubGlobal('fetch', fetchMock)

    await expect(http.post('/auth/login', {}, { anonymous: true })).rejects.toBeInstanceOf(ApiError)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect((init.headers as Record<string, string>)['Authorization']).toBeUndefined()
  })

  it('refreshes proactively when the token is about to expire', async () => {
    // Two seconds left: the request should refresh *before* asking, rather than
    // spending a round trip to be told what it already knows.
    tokenStore.set('nearly-stale', 2)
    const fetchMock = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        url.includes('/auth/refresh')
          ? refreshResponse()
          : jsonResponse({ ok: true }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await http.get('/auth/me')

    expect(fetchMock.mock.calls[0]?.[0]).toContain('/auth/refresh')
    expect(tokenStore.get()).toBe('fresh')
  })
})

describe('idempotency', () => {
  it('passes the key through as a header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await http.post('/bookings', { property_id: 'x' }, { idempotencyKey: 'key-1' })

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect((init.headers as Record<string, string>)['Idempotency-Key']).toBe('key-1')
  })
})
