/**
 * The HTTP client.
 *
 * Three things here are load-bearing, and each exists because of a specific
 * failure it prevents.
 *
 * **Single-flight refresh.** A page typically fires several queries at once. If
 * the access token has expired, every one of them gets a 401, and a naive
 * client would fire N concurrent refreshes. The backend rotates refresh tokens
 * and *detects reuse* as a theft signal — so N concurrent refreshes with the
 * same token would look exactly like a stolen token and log the user out of
 * every device. So: one refresh promise, shared; everyone waits on it and
 * retries once.
 *
 * **`credentials: 'include'`.** The refresh token is an HttpOnly cookie. Without
 * this the browser omits it and session restore silently fails.
 *
 * **Every failure becomes an `ApiError` or a `NetworkError`.** Callers never see
 * a raw `Response`, never re-check `res.ok`, and cannot forget to.
 */

import { config } from '@/core/config'
import { ApiError, NetworkError } from '@/core/errors'
import { tokenStore } from './tokenStore'

export interface RequestOptions {
  readonly method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  readonly body?: unknown
  readonly query?: Record<string, unknown>
  readonly headers?: Record<string, string>
  readonly signal?: AbortSignal | undefined
  /** Skip the Authorization header and the refresh dance. Login, refresh. */
  readonly anonymous?: boolean
  readonly idempotencyKey?: string
}

/** Set by the auth layer; called when refresh fails for good. */
let onSessionLost: () => void = () => {}
export function setSessionLostHandler(handler: () => void): void {
  onSessionLost = handler
}

let refreshInFlight: Promise<boolean> | null = null

/**
 * Query values are primitives by construction, but the parameter type is
 * `unknown`. Serialising an object would produce `[object Object]` in a URL —
 * a silent bug that reaches the server as a nonsense filter, so it is dropped
 * instead.
 */
function queryValue(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return null
}

function buildUrl(path: string, query?: Record<string, unknown>): string {
  const url = `${config.apiBaseUrl}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    // Repeated keys, not comma-joined: the API declares these as list params,
    // and `?amenity=wifi&amenity=pool` is what it parses.
    if (Array.isArray(value)) {
      for (const item of value as unknown[]) {
        const serialised = queryValue(item)
        if (serialised !== null) params.append(key, serialised)
      }
    } else {
      const serialised = queryValue(value)
      if (serialised !== null) params.append(key, serialised)
    }
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

async function toApiError(response: Response): Promise<ApiError> {
  let code = 'INTERNAL_ERROR'
  let message = response.statusText || 'Request failed'
  let details: Record<string, unknown> = {}
  let requestId: string | null = response.headers.get('x-request-id')

  try {
    const payload = (await response.json()) as {
      error?: { code?: string; message?: string; details?: Record<string, unknown>; request_id?: string }
    }
    if (payload.error) {
      code = payload.error.code ?? code
      message = payload.error.message ?? message
      details = payload.error.details ?? {}
      requestId = payload.error.request_id ?? requestId
    }
  } catch {
    // A non-JSON error body — a proxy 502, most often. The status is the signal.
  }

  const retryAfter = response.headers.get('retry-after')
  return new ApiError({
    status: response.status,
    code,
    message,
    details,
    requestId,
    retryAfterSeconds: retryAfter ? Number(retryAfter) : null,
  })
}

/**
 * Refresh once, no matter how many callers ask.
 *
 * The body is empty on purpose: the refresh token comes from the HttpOnly
 * cookie, which is the only copy this app can rely on after a page load.
 */
async function refreshAccessToken(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(buildUrl('/auth/refresh'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      })
      if (!response.ok) return false
      // The endpoint answers with the full auth response — `{ tokens, user }`
      // — not a bare token. Reading `access_token` off the top level yields
      // `undefined`, and the failure is silent: every request afterwards would
      // carry `Bearer undefined` and 401.
      const data = (await response.json()) as {
        tokens?: { access_token: string; expires_in: number }
      }
      if (!data.tokens?.access_token) return false
      tokenStore.set(data.tokens.access_token, data.tokens.expires_in)
      return true
    } catch {
      return false
    } finally {
      // Cleared in a microtask so callers awaiting this promise all observe the
      // same result before a new refresh can start.
      queueMicrotask(() => {
        refreshInFlight = null
      })
    }
  })()
  return refreshInFlight
}

async function send(path: string, options: RequestOptions, isRetry = false): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers }

  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey

  if (!options.anonymous) {
    // Refresh *before* the request when the token is about to expire, so the
    // common case never costs a round trip that is guaranteed to 401.
    if (tokenStore.isExpiring() && !isRetry) await refreshAccessToken()
    const token = tokenStore.get()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const init: RequestInit = {
    method: options.method ?? 'GET',
    headers,
    credentials: 'include',
  }
  if (options.signal) init.signal = options.signal
  if (options.body !== undefined) {
    init.body = options.body instanceof FormData ? options.body : JSON.stringify(options.body)
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), init)
  } catch (cause) {
    // An aborted request is a cancelled query, not a network failure. React
    // Query needs to see the AbortError to drop the result quietly.
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new NetworkError(cause)
  }

  if (response.status === 401 && !options.anonymous && !isRetry) {
    const refreshed = await refreshAccessToken()
    if (refreshed) return send(path, options, true)
    tokenStore.clear()
    onSessionLost()
  }

  return response
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options)
  if (!response.ok) throw await toApiError(response)
  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T
  }
  return (await response.json()) as T
}

export const http = {
  get: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'DELETE' }),
}

/** Exposed for tests only — resets the module-level single-flight latch. */
export function __resetRefreshState(): void {
  refreshInFlight = null
}
