/**
 * The API client, and specifically its refresh behaviour.
 *
 * **Single-flight is not an optimisation here — it is a correctness
 * requirement.** The backend rotates refresh tokens and treats a reused one as
 * theft: presenting the same refresh token twice revokes the whole family and
 * signs the user out of every device. An admin panel that loads eight panels
 * at once, each getting a 401 and each refreshing independently, would sign
 * itself out on every expiry.
 *
 * So the tests below are mostly about *how many times* refresh was called, not
 * whether it succeeded.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, setAccessToken, setSessionLostHandler } from '@/core/http'

type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function errorBody(code: string, message = 'nope', status = 400): Response {
  return new Response(JSON.stringify({ error: { code, message, request_id: 'r1' } }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/**
 * A typed `fetch` stub, installed globally.
 *
 * Typed so `mock.calls` is not `any[]` — asserting on the headers a request
 * carried is most of what these tests do, and doing it through a cast at every
 * site is noise.
 */
function stubFetch(handler: Fetch) {
  const mock = vi.fn<Fetch>(handler)
  vi.stubGlobal('fetch', mock)
  return mock
}

/** Answers each call from the queue in order. */
function stubSequence(...responses: Response[]) {
  let index = 0
  return stubFetch(() => Promise.resolve(responses[index++]!))
}

/**
 * The URL a call was made to.
 *
 * `fetch` accepts a string, a `URL`, or a `Request`, and only the first two
 * stringify usefully — `String(new Request(...))` is `[object Object]`, so an
 * assertion written that way passes vacuously. The client only ever passes a
 * string, but its type does not say so, so this narrows rather than casts.
 */
function urlOf(input: RequestInfo | URL | undefined): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input?.url ?? ''
}

/** The header a given call carried, or `undefined` if it carried none. */
function headerOf(init: RequestInit | undefined, name: string): string | undefined {
  return (init?.headers as Record<string, string> | undefined)?.[name]
}

beforeEach(() => {
  setAccessToken(null)
  setSessionLostHandler(() => {})
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('request', () => {
  it('sends the access token when there is one', async () => {
    const fetchMock = stubFetch(() => Promise.resolve(json({ ok: true })))
    setAccessToken('tok-123')

    await api.get('/thing')

    expect(headerOf(fetchMock.mock.calls[0]?.[1], 'Authorization')).toBe('Bearer tok-123')
  })

  it('sends no Authorization header when signed out', async () => {
    const fetchMock = stubFetch(() => Promise.resolve(json({ ok: true })))

    await api.get('/thing')

    expect(headerOf(fetchMock.mock.calls[0]?.[1], 'Authorization')).toBeUndefined()
  })

  it('always sends credentials', async () => {
    /**
     * The refresh cookie is HttpOnly and only travels if the request asks for
     * it. Omitting this silently breaks refresh in production while everything
     * works locally against a same-origin dev server.
     */
    const fetchMock = stubFetch(() => Promise.resolve(json({ ok: true })))

    await api.get('/thing')

    expect(fetchMock.mock.calls[0]?.[1]?.credentials).toBe('include')
  })

  it('turns an error envelope into an ApiError carrying its code', async () => {
    /**
     * The UI switches on `code`, not on the message — messages are for people
     * and change; codes are the contract.
     */
    stubFetch(() => Promise.resolve(errorBody('VENDOR_NOT_FOUND', 'No vendor', 404)))

    await expect(api.get('/vendors/x')).rejects.toMatchObject({
      status: 404,
      code: 'VENDOR_NOT_FOUND',
    })
  })

  it('survives an error response that is not JSON', async () => {
    /**
     * A proxy 502 is an HTML page. Parsing it must not throw a `SyntaxError`
     * that hides the actual status.
     */
    stubFetch(() => Promise.resolve(new Response('<html>Bad Gateway</html>', { status: 502 })))

    await expect(api.get('/thing')).rejects.toBeInstanceOf(ApiError)
    await expect(api.get('/thing')).rejects.toMatchObject({ status: 502 })
  })

  it('drops query parameters that are unset', async () => {
    /** `?status=undefined` is a filter the server will try to honour. */
    const fetchMock = stubFetch(() => Promise.resolve(json({ items: [] })))

    await api.get('/vendors', { status: undefined, q: '', page: 2 })

    const url = urlOf(fetchMock.mock.calls[0]?.[0])
    expect(url).toContain('page=2')
    expect(url).not.toContain('status')
    expect(url).not.toContain('q=')
  })
})

describe('refresh', () => {
  it('refreshes once and retries the original request', async () => {
    const fetchMock = stubSequence(
      errorBody('UNAUTHENTICATED', 'expired', 401),
      json({ tokens: { access_token: 'fresh' } }),
      json({ ok: true }),
    )
    setAccessToken('stale')

    await expect(api.get('/thing')).resolves.toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('reads the token from data.tokens, not the top level', async () => {
    /**
     * `/auth/refresh` returns `{tokens, user}`. Reading `access_token` off the
     * top level yields `undefined`, and every later request then carries
     * `Bearer undefined` while the app believes it is signed in — which is
     * exactly what happened before this was pinned.
     */
    const fetchMock = stubSequence(
      errorBody('UNAUTHENTICATED', 'expired', 401),
      json({ tokens: { access_token: 'fresh' }, user: { id: 'u1' } }),
      json({ ok: true }),
    )
    setAccessToken('stale')

    await api.get('/thing')

    expect(headerOf(fetchMock.mock.calls[2]?.[1], 'Authorization')).toBe('Bearer fresh')
  })

  it('refreshes once for many concurrent 401s', async () => {
    /**
     * **The** reason this is single-flight.
     *
     * The backend rotates refresh tokens and treats reuse as theft. Eight
     * panels refreshing in parallel would present the same token eight times
     * and revoke the family — signing the admin out of every device, on every
     * token expiry.
     */
    let refreshes = 0
    stubFetch(async (input) => {
      if (urlOf(input).includes('/auth/refresh')) {
        refreshes += 1
        // A real round trip takes time; without a delay the calls serialise
        // and the test passes even without single-flight.
        await new Promise((resolve) => setTimeout(resolve, 10))
        return json({ tokens: { access_token: 'fresh' } })
      }
      return refreshes === 0 ? errorBody('UNAUTHENTICATED', 'expired', 401) : json({ ok: true })
    })
    setAccessToken('stale')

    await Promise.all([api.get('/a'), api.get('/b'), api.get('/c'), api.get('/d')])

    expect(refreshes).toBe(1)
  })

  it('gives up and reports the session lost when refresh fails', async () => {
    const onLost = vi.fn()
    setSessionLostHandler(onLost)
    stubFetch(() => Promise.resolve(errorBody('UNAUTHENTICATED', 'gone', 401)))
    setAccessToken('stale')

    await expect(api.get('/thing')).rejects.toBeInstanceOf(ApiError)
    expect(onLost).toHaveBeenCalled()
  })

  it('does not retry more than once', async () => {
    /**
     * A refresh that succeeds but yields a token the server still rejects
     * would otherwise loop forever, hammering the auth endpoint.
     */
    const fetchMock = stubFetch((input) =>
      Promise.resolve(
        urlOf(input).includes('/auth/refresh')
          ? json({ tokens: { access_token: 'fresh' } })
          : errorBody('UNAUTHENTICATED', 'still expired', 401),
      ),
    )
    setAccessToken('stale')

    await expect(api.get('/thing')).rejects.toBeInstanceOf(ApiError)
    // original + refresh + one retry, and no more.
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
})

describe('ApiError', () => {
  it('knows a permission failure is not retryable', () => {
    /**
     * Retrying will not grant the permission, and three attempts turn one
     * clear refusal into three seconds of spinner.
     */
    expect(new ApiError(403, 'FORBIDDEN', 'no').isForbidden).toBe(true)
    expect(new ApiError(403, 'FORBIDDEN', 'no').isRetryable).toBe(false)
  })

  it('knows a rate limit and a server error are retryable', () => {
    expect(new ApiError(429, 'RATE_LIMITED', 'slow down').isRetryable).toBe(true)
    expect(new ApiError(503, 'UNAVAILABLE', 'later').isRetryable).toBe(true)
  })

  it('knows a validation failure is not retryable', () => {
    expect(new ApiError(422, 'VALIDATION_ERROR', 'bad').isRetryable).toBe(false)
  })
})
