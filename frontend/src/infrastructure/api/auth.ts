/**
 * `AuthRepository` over `/auth`.
 *
 * Every call that mints tokens hands the access token to `tokenStore` and
 * **discards the refresh token**. The server also sets it as an HttpOnly
 * cookie, and that copy is the one this app uses — see `tokenStore.ts`.
 */

import type { AuthRepository, AuthResult } from '@/application/ports'
import { http } from '@/infrastructure/http/client'
import { tokenStore } from '@/infrastructure/http/tokenStore'
import type * as dto from './dto'
import { toOtpChallenge, toSession, toUser } from './mappers'

function deviceLabel(): string {
  // Shown in the session list so a guest can recognise "which device is this?"
  // and revoke the one they do not know.
  const ua = navigator.userAgent
  const browser =
    /Edg\//.test(ua) ? 'Edge'
    : /Chrome\//.test(ua) ? 'Chrome'
    : /Safari\//.test(ua) ? 'Safari'
    : /Firefox\//.test(ua) ? 'Firefox'
    : 'Browser'
  const os =
    /iPhone|iPad/.test(ua) ? 'iOS'
    : /Android/.test(ua) ? 'Android'
    : /Mac OS X/.test(ua) ? 'macOS'
    : /Windows/.test(ua) ? 'Windows'
    : 'Web'
  return `${browser} on ${os}`
}

function adopt(data: dto.AuthResponseDto): AuthResult {
  tokenStore.set(data.tokens.access_token, data.tokens.expires_in)
  return {
    user: toUser(data.user),
    accessToken: data.tokens.access_token,
    expiresIn: data.tokens.expires_in,
    isNewUser: data.is_new_user ?? false,
  }
}

export const authRepository: AuthRepository = {
  async register(input) {
    // 202 with a message, deliberately: the response says nothing about whether
    // the address was already registered, because that would turn this endpoint
    // into a membership oracle for any leaked email list. No tokens either —
    // the user signs in after verifying. See the backend's register route.
    const result = await http.post<{ message: string; detail?: string }>(
      '/auth/register',
      { email: input.email, password: input.password, full_name: input.fullName ?? null },
      { anonymous: true },
    )
    return { message: result.message, detail: result.detail ?? null }
  },

  async login(input) {
    return adopt(
      await http.post<dto.AuthResponseDto>(
        '/auth/login',
        {
          email: input.email,
          password: input.password,
          device_label: input.deviceLabel ?? deviceLabel(),
        },
        { anonymous: true },
      ),
    )
  },

  async loginWithGoogle(input) {
    return adopt(
      await http.post<dto.AuthResponseDto>(
        '/auth/google',
        { id_token: input.idToken, nonce: input.nonce ?? null, device_label: deviceLabel() },
        { anonymous: true },
      ),
    )
  },

  async requestOtp(input) {
    return toOtpChallenge(
      await http.post<dto.OtpChallengeDto>(
        '/auth/otp/request',
        { phone: input.phone, purpose: input.purpose ?? 'login' },
        // `link_phone` attaches a number to the signed-in account, so it must
        // carry the token; `login` has none to carry.
        input.purpose === 'link_phone' ? {} : { anonymous: true },
      ),
    )
  },

  async verifyOtp(input) {
    return adopt(
      await http.post<dto.AuthResponseDto>(
        '/auth/otp/verify',
        { challenge_id: input.challengeId, code: input.code },
        { anonymous: true },
      ),
    )
  },

  async logout(allDevices = false) {
    try {
      await http.post<void>('/auth/logout', { all_devices: allDevices })
    } finally {
      // Cleared even if the call fails. A network error must not leave a user
      // who pressed "sign out" still signed in on the screen in front of them.
      tokenStore.clear()
    }
  },

  async me(signal) {
    return toUser(await http.get<dto.UserDto>('/auth/me', { signal }))
  },

  async forgotPassword(email) {
    // Always 202, whether or not the address exists — telling an attacker which
    // emails are registered is an account-enumeration oracle.
    await http.post<void>('/auth/password/forgot', { email }, { anonymous: true })
  },

  async resetPassword(input) {
    await http.post<void>(
      '/auth/password/reset',
      { token: input.token, new_password: input.newPassword },
      { anonymous: true },
    )
  },

  async changePassword(input) {
    await http.post<void>('/auth/password/change', {
      current_password: input.currentPassword,
      new_password: input.newPassword,
    })
  },

  async verifyEmail(token) {
    await http.post<void>('/auth/email/verify', { token }, { anonymous: true })
  },

  async resendVerification() {
    await http.post<void>('/auth/email/resend', {})
  },

  async sessions(signal) {
    const data = await http.get<dto.SessionDto[]>('/auth/sessions', { signal })
    return data.map(toSession)
  },

  async revokeSession(sessionId) {
    await http.delete<void>(`/auth/sessions/${encodeURIComponent(sessionId)}`)
  },
}

/**
 * Restore a session on boot, using the HttpOnly refresh cookie.
 *
 * Returns `null` for a visitor who is simply not signed in — the overwhelmingly
 * common case, and not an error worth surfacing anywhere.
 */
export async function restoreSession(): Promise<AuthResult | null> {
  try {
    // The refresh endpoint returns the user alongside the tokens, so restoring
    // a session is one round trip rather than a refresh followed by `/auth/me`.
    const data = await http.post<dto.AuthResponseDto>('/auth/refresh', {}, { anonymous: true })
    return adopt(data)
  } catch {
    tokenStore.clear()
    return null
  }
}
