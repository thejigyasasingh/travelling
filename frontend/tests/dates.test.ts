/**
 * Stay dates.
 *
 * The half-open range is the rule the whole booking flow rests on: a 12th→14th
 * stay is two nights, and the 14th is free for the next guest. An off-by-one
 * here is either a wrong price or an overbooking.
 */

import { describe, expect, it } from 'vitest'
import {
  addDays,
  formatCountdown,
  formatStay,
  isIsoDate,
  isValidStay,
  nightsBetween,
  nightsIn,
} from '@/core/dates'

describe('nights', () => {
  it('counts a half-open range', () => {
    expect(nightsBetween('2026-09-12', '2026-09-14')).toBe(2)
  })

  it('counts one night for consecutive days', () => {
    expect(nightsBetween('2026-09-12', '2026-09-13')).toBe(1)
  })

  it('lists the nights actually slept in, excluding check-out', () => {
    expect(nightsIn('2026-09-12', '2026-09-15')).toEqual(['2026-09-12', '2026-09-13', '2026-09-14'])
  })

  it('crosses a month boundary', () => {
    expect(nightsBetween('2026-09-29', '2026-10-02')).toBe(3)
  })

  it('crosses a leap day', () => {
    // 2028 is a leap year: 28 Feb → 1 Mar is two nights, not one.
    expect(nightsBetween('2028-02-28', '2028-03-01')).toBe(2)
  })

  it('crosses a year boundary', () => {
    expect(nightsBetween('2026-12-30', '2027-01-02')).toBe(3)
  })
})

describe('arithmetic', () => {
  it('adds days across a month end', () => {
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01')
  })

  it('survives a DST-style shift', () => {
    // Arithmetic is anchored in UTC precisely so a local DST transition cannot
    // turn a 24-hour step into 23 and silently drop a night.
    expect(addDays('2026-03-28', 1)).toBe('2026-03-29')
    expect(nightsBetween('2026-03-28', '2026-03-30')).toBe(2)
  })
})

describe('validation', () => {
  it('rejects a checkout on or before check-in', () => {
    expect(isValidStay({ checkIn: '2026-09-12', checkOut: '2026-09-12' })).toBe(false)
    expect(isValidStay({ checkIn: '2026-09-12', checkOut: '2026-09-11' })).toBe(false)
    expect(isValidStay({ checkIn: '2026-09-12', checkOut: '2026-09-13' })).toBe(true)
  })

  it('rejects a partial or malformed range', () => {
    expect(isValidStay({ checkIn: '2026-09-12' })).toBe(false)
    expect(isValidStay({ checkIn: 'tomorrow', checkOut: '2026-09-13' })).toBe(false)
  })

  it('rejects an impossible date that still matches the shape', () => {
    expect(isIsoDate('2026-13-45')).toBe(false)
    expect(isIsoDate('2026-09-12')).toBe(true)
  })
})

describe('display', () => {
  // The month abbreviation ("Sep" vs "Sept") is an ICU detail that varies by
  // version. What matters is the collapsing, so these assert the structure.
  it('collapses a repeated month in a stay range', () => {
    expect(formatStay('2026-09-12', '2026-09-14')).toMatch(/^12 – 14 Sept? 2026$/)
  })

  it('keeps both months when they differ', () => {
    expect(formatStay('2026-09-29', '2026-10-02')).toMatch(/^29 Sept? – 2 Oct 2026$/)
  })

  it('pads the countdown seconds', () => {
    expect(formatCountdown(605)).toBe('10:05')
    expect(formatCountdown(0)).toBe('0:00')
    expect(formatCountdown(-5)).toBe('0:00')
  })
})
