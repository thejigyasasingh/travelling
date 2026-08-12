/**
 * The API client.
 *
 * Deliberately a copy of the customer app's shape rather than a shared package:
 * the two deploy separately, and a shared runtime dependency between an
 * internal tool and a public site is a coupling that eventually forces one to
 * ship because the other did. What *is* shared is the contract, and the tests
 * pin it against the live server.
 *
 * The single-flight refresh is the same mechanism and exists for the same
 * reason: the backend rotates refresh tokens and treats reuse as theft, so
 * concurrent refreshes sign the user out of every device.
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  readonly requestId: string | null

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
    requestId: string | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
  }

  /** A permission failure, which the UI explains rather than offering a retry. */
  get isForbidden(): boolean {
    return this.status === 403
  }

  get isRetryable(): boolean {
    return this.status === 429 || this.status >= 500
  }
}

let accessToken: string | null = null
let refreshInFlight: Promise<boolean> | null = null
let onSessionLost: () => void = () => {}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function setSessionLostHandler(handler: () => void): void {
  onSessionLost = handler
}

async function refresh(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      })
      if (!response.ok) return false
      // `{ tokens, user }` — not a bare token. Reading `access_token` off the
      // top level yields undefined, and every later request then carries
      // `Bearer undefined` while the app believes it is signed in.
      const data = (await response.json()) as {
        tokens?: { access_token: string }
      }
      if (!data.tokens?.access_token) return false
      accessToken = data.tokens.access_token
      return true
    } catch {
      return false
    } finally {
      queueMicrotask(() => {
        refreshInFlight = null
      })
    }
  })()
  return refreshInFlight
}

type QueryValue = string | number | boolean | undefined | null

interface Options {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  // `| undefined` explicitly: under `exactOptionalPropertyTypes` an optional
  // property still rejects an explicit `undefined`, which is exactly what a
  // caller passes when a filter is unset.
  query?: Record<string, QueryValue> | undefined
  signal?: AbortSignal | undefined
  anonymous?: boolean
}

function url(path: string, query?: Options['query']): string {
  if (!query) return `${BASE}${path}`
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${BASE}${path}?${qs}` : `${BASE}${path}`
}

async function send(path: string, options: Options, isRetry = false): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (!options.anonymous && accessToken) headers['Authorization'] = `Bearer ${accessToken}`

  const init: RequestInit = {
    method: options.method ?? 'GET',
    headers,
    credentials: 'include',
  }
  if (options.signal) init.signal = options.signal
  if (options.body !== undefined) init.body = JSON.stringify(options.body)

  const response = await fetch(url(path, options.query), init)

  if (response.status === 401 && !options.anonymous && !isRetry) {
    if (await refresh()) return send(path, options, true)
    accessToken = null
    onSessionLost()
  }
  return response
}

export async function request<T>(path: string, options: Options = {}): Promise<T> {
  const response = await send(path, options)
  if (!response.ok) {
    let code = 'INTERNAL_ERROR'
    let message = response.statusText || 'Request failed'
    let details: Record<string, unknown> = {}
    let requestId: string | null = null
    try {
      const payload = (await response.json()) as {
        error?: {
          code?: string
          message?: string
          details?: Record<string, unknown>
          request_id?: string
        }
      }
      code = payload.error?.code ?? code
      message = payload.error?.message ?? message
      details = payload.error?.details ?? {}
      requestId = payload.error?.request_id ?? null
    } catch {
      /* a proxy error page; the status is the signal */
    }
    throw new ApiError(response.status, code, message, details, requestId)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string, query?: Options['query'], signal?: AbortSignal) =>
    request<T>(path, { query, ...(signal ? { signal } : {}) }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
}
