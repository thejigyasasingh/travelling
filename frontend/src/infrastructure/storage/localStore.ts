/**
 * A typed, versioned wrapper over `localStorage`.
 *
 * Direct `localStorage` calls throw in Safari private mode and in an iframe
 * with third-party storage blocked, which would take down a whole page for a
 * feature as peripheral as a saved-stays list. Everything here degrades to a
 * no-op instead.
 *
 * The version prefix means a shape change is a cache miss, not a crash on data
 * written by last month's build.
 */

const VERSION = 'v1'

function key(name: string): string {
  return `rw:${VERSION}:${name}`
}

export function readJson<T>(name: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key(name))
    if (raw === null) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function writeJson(name: string, value: unknown): void {
  try {
    localStorage.setItem(key(name), JSON.stringify(value))
  } catch {
    // Quota exceeded or storage blocked. Losing a wishlist entry is bad;
    // throwing out of a click handler and blanking the page is worse.
  }
}

export function removeItem(name: string): void {
  try {
    localStorage.removeItem(key(name))
  } catch {
    /* see above */
  }
}
