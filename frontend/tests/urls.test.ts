/**
 * The post-login redirect.
 *
 * An open redirect on a login page is a phishing primitive: the attacker sends
 * a link to *our* domain, the victim signs in for real, and lands on a
 * lookalike with their trust already established.
 */

import { describe, expect, it } from 'vitest'
import { safeNext } from '@/core/urls'

describe('safeNext', () => {
  it('allows a same-site path', () => {
    expect(safeNext('/trips')).toBe('/trips')
    expect(safeNext('/search?q=Goa&adults=2')).toBe('/search?q=Goa&adults=2')
  })

  it('rejects an absolute URL', () => {
    expect(safeNext('https://evil.example/login')).toBe('/')
    expect(safeNext('http://evil.example')).toBe('/')
  })

  it('rejects a protocol-relative URL', () => {
    // The one people miss: `//evil.example` has no scheme but browsers treat it
    // as absolute, so a leading-slash check alone lets it through.
    expect(safeNext('//evil.example')).toBe('/')
  })

  it('rejects a backslash-prefixed path', () => {
    expect(safeNext('/\\evil.example')).toBe('/')
  })

  it('rejects a javascript: URL', () => {
    expect(safeNext('javascript:alert(1)')).toBe('/')
  })

  it('falls back for empty input', () => {
    expect(safeNext(null)).toBe('/')
    expect(safeNext('')).toBe('/')
    expect(safeNext(undefined)).toBe('/')
  })
})
