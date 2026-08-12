/**
 * Money formatting.
 *
 * Every price on the site goes through this. A bug here is a wrong number in
 * front of a customer, which is the one class of frontend bug that costs real
 * money rather than goodwill.
 */

import { describe, expect, it } from 'vitest'
import { addMoney, formatMinor, formatMoney, formatPerNight, money, subtractMoney } from '@/core/money'

describe('formatting', () => {
  it('renders paise as rupees', () => {
    expect(formatMoney(money(450_000, 'INR'))).toBe('₹4,500.00')
  })

  it('groups in the Indian system, not thousands', () => {
    // ₹12,34,567.00 — not ₹1,234,567.00. Getting this wrong makes every large
    // total look foreign to the audience it is shown to.
    expect(formatMoney(money(123_456_700, 'INR'))).toBe('₹12,34,567.00')
  })

  it('drops decimals in compact mode only when they are zero', () => {
    expect(formatMoney(money(450_000, 'INR'), { compact: true })).toBe('₹4,500')
    expect(formatMoney(money(450_050, 'INR'), { compact: true })).toBe('₹4,500.50')
  })

  it('never rounds a half-rupee away', () => {
    expect(formatMoney(money(1, 'INR'))).toBe('₹0.01')
    expect(formatMoney(money(99, 'INR'))).toBe('₹0.99')
  })

  it('renders an em dash for an unknown amount rather than zero', () => {
    // "₹0" for "we do not know the price" is a lie a customer can act on.
    expect(formatMinor(null, 'INR')).toBe('—')
    expect(formatMinor(undefined, 'INR')).toBe('—')
    expect(formatMinor(0, 'INR')).toBe('₹0.00')
  })

  it('keeps the unit attached to a nightly rate', () => {
    expect(formatPerNight(450_000, 'INR')).toBe('₹4,500 / night')
  })

  it('handles a currency with no minor unit', () => {
    // JPY has no subunit: 4500 is ¥4,500, not ¥45.00. Asserted on the digits
    // rather than the exact string, because the symbol an `en-IN` locale picks
    // for yen ("JP¥") is an ICU detail that may change and is not the point.
    const formatted = formatMoney(money(4_500, 'JPY'))
    expect(formatted).toContain('¥')
    expect(formatted).toContain('4,500')
    expect(formatted).not.toContain('.')
  })
})

describe('arithmetic', () => {
  it('adds and subtracts in integer minor units', () => {
    expect(addMoney(money(10, 'INR'), money(20, 'INR')).amountMinor).toBe(30)
    expect(subtractMoney(money(30, 'INR'), money(20, 'INR')).amountMinor).toBe(10)
  })

  it('has no floating-point drift', () => {
    // The reason the whole app is integer-based: 0.1 + 0.2 !== 0.3.
    let total = money(0, 'INR')
    for (let i = 0; i < 10; i++) total = addMoney(total, money(10, 'INR'))
    expect(total.amountMinor).toBe(100)
  })

  it('refuses to mix currencies', () => {
    expect(() => addMoney(money(10, 'INR'), money(10, 'USD'))).toThrow(/INR.*USD/)
  })
})
