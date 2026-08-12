/** The signed-in guest. */

export interface User {
  readonly id: string
  readonly email: string
  readonly fullName: string | null
  readonly phone: string | null
  readonly avatarUrl: string | null
  readonly status: string
  readonly roles: readonly string[]
  readonly permissions: readonly string[]
  readonly emailVerified: boolean
  readonly phoneVerified: boolean
  /** False for a Google-only account: there is no password to change. */
  readonly hasPassword: boolean
  readonly locale: string
  readonly timezone: string
  readonly vendorId: string | null
  readonly lastLoginAt: string | null
}

export interface AuthTokens {
  readonly accessToken: string
  /**
   * Also set as an HttpOnly cookie by the server. The app never stores this —
   * see `infrastructure/http/tokenStore.ts` for why.
   */
  readonly refreshToken: string
  readonly expiresIn: number
}

export interface Session {
  readonly id: string
  readonly deviceLabel: string | null
  readonly userAgent: string | null
  readonly createdAt: string
  readonly lastUsedAt: string | null
  readonly expiresAt: string
  readonly isCurrent: boolean
}

export interface OtpChallenge {
  readonly challengeId: string
  readonly expiresIn: number
  readonly resendAfter: number
}

export function displayName(user: User): string {
  return user.fullName?.trim() || user.email.split('@')[0] || 'Guest'
}

export function initials(user: User): string {
  const source = user.fullName?.trim() || user.email
  return source
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function hasPermission(user: User | null, permission: string): boolean {
  return user?.permissions.includes(permission) ?? false
}

export function isVendor(user: User | null): boolean {
  return user?.roles.includes('vendor') ?? false
}
