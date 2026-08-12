/**
 * The API's error envelope, as a typed thing the UI can switch on.
 *
 * The backend returns `{ error: { code, message, details, request_id } }` for
 * every failure. `code` is the stable contract; `message` is for humans and may
 * change. So the app switches on `code` and *displays* `message` — the reverse
 * (parsing the message) breaks the first time someone improves the wording.
 */

export const ErrorCode = {
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  UNAUTHENTICATED: 'UNAUTHENTICATED',
  TOKEN_EXPIRED: 'TOKEN_EXPIRED',
  TOKEN_INVALID: 'TOKEN_INVALID',
  FORBIDDEN: 'FORBIDDEN',
  NOT_FOUND: 'NOT_FOUND',
  CONFLICT: 'CONFLICT',
  RATE_LIMITED: 'RATE_LIMITED',
  DEPENDENCY_UNAVAILABLE: 'DEPENDENCY_UNAVAILABLE',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  // Domain codes worth handling specifically, because each one has a distinct
  // recovery the user can actually perform.
  BOOKING_DATES_UNAVAILABLE: 'BOOKING_DATES_UNAVAILABLE',
  PRICE_CHANGED: 'PRICE_CHANGED',
  HOLD_EXPIRED: 'HOLD_EXPIRED',
  PAYMENTS_DISABLED: 'PAYMENTS_DISABLED',
  EMAIL_NOT_VERIFIED: 'EMAIL_NOT_VERIFIED',
  ACCOUNT_LOCKED: 'ACCOUNT_LOCKED',
} as const

export type ErrorCodeValue = (typeof ErrorCode)[keyof typeof ErrorCode] | (string & {})

export interface FieldIssue {
  readonly field: string
  readonly message: string
  readonly code: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: ErrorCodeValue
  readonly details: Record<string, unknown>
  readonly requestId: string | null
  readonly retryAfterSeconds: number | null

  constructor(init: {
    status: number
    code: ErrorCodeValue
    message: string
    details?: Record<string, unknown>
    requestId?: string | null
    retryAfterSeconds?: number | null
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.status = init.status
    this.code = init.code
    this.details = init.details ?? {}
    this.requestId = init.requestId ?? null
    this.retryAfterSeconds = init.retryAfterSeconds ?? null
  }

  /** Per-field messages, so a form can attach each to the right input. */
  get fieldIssues(): FieldIssue[] {
    const raw = this.details['fields']
    return Array.isArray(raw) ? (raw as FieldIssue[]) : []
  }

  get isAuthError(): boolean {
    return this.status === 401
  }

  /** Worth a retry button. A 409 is not — the state genuinely differs. */
  get isTransient(): boolean {
    return this.status === 429 || this.status >= 500
  }
}

/** The network never answered. Distinct from a 500: nothing reached the server. */
export class NetworkError extends Error {
  constructor(cause?: unknown) {
    super('Could not reach the server. Check your connection and try again.')
    this.name = 'NetworkError'
    this.cause = cause
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function hasErrorCode(error: unknown, ...codes: ErrorCodeValue[]): boolean {
  return isApiError(error) && codes.includes(error.code)
}

/**
 * What to actually show a user.
 *
 * Server messages are written for humans and are shown as-is. The exceptions
 * are 5xx and unknown throwables, where the server's text is either useless or
 * leaks internals.
 */
export function messageFor(error: unknown): string {
  if (error instanceof NetworkError) return error.message
  if (isApiError(error)) {
    if (error.status >= 500) return 'Something went wrong on our side. Please try again.'
    return error.message
  }
  return 'Something went wrong. Please try again.'
}
