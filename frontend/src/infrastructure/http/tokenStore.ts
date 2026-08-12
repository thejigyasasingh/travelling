/**
 * Where the access token lives: **in memory, and nowhere else.**
 *
 * Not `localStorage`. A token in `localStorage` is readable by any script that
 * ends up on the page — one compromised dependency, one injected analytics tag
 * — and it survives a tab close, so stealing it buys an attacker a session they
 * can use later, from anywhere. In memory, an XSS has to exfiltrate during the
 * page's lifetime, and closing the tab ends it.
 *
 * The cost is that a refresh (F5) starts with no access token. That is paid for
 * by the refresh token, which the server sets as an **HttpOnly** cookie scoped
 * to `/api/v1/auth` — unreadable by any script, sent automatically by the
 * browser. So the app boots by calling `/auth/refresh` with no body: the cookie
 * is the credential. A session survives a reload without the long-lived token
 * ever being reachable from JavaScript.
 *
 * The token is deliberately not React state. Interceptors need it outside the
 * component tree, and putting it in a context would re-render the world on
 * every silent refresh.
 */

type Listener = (token: string | null) => void

let accessToken: string | null = null
let expiresAtMs = 0
const listeners = new Set<Listener>()

export const tokenStore = {
  get(): string | null {
    return accessToken
  },

  /** True shortly *before* real expiry, so a refresh starts before a 401. */
  isExpiring(withinMs = 30_000): boolean {
    return accessToken !== null && Date.now() + withinMs >= expiresAtMs
  },

  set(token: string, expiresInSeconds: number): void {
    accessToken = token
    expiresAtMs = Date.now() + expiresInSeconds * 1000
    listeners.forEach((l) => l(token))
  },

  clear(): void {
    accessToken = null
    expiresAtMs = 0
    listeners.forEach((l) => l(null))
  },

  subscribe(listener: Listener): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
}
