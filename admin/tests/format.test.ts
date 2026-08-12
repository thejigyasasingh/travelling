import { describe, expect, it } from "vitest";
import {
  formatBps,
  formatCompactMoney,
  formatMinor,
  formatPercent,
} from "@/core/format";

/**
 * Formatting.
 *
 * Every number an admin reads goes through here, and several of them are
 * reconciled against a bank statement. A rounding difference between this and
 * the customer's invoice is a support ticket nobody can answer.
 */
describe("money", () => {
  it("renders paise as rupees, grouped the Indian way", () => {
    expect(formatMinor(123456700, "INR")).toBe("₹12,34,567.00");
  });

  it("drops decimals in compact mode only when they are zero", () => {
    expect(formatMinor(450000, "INR", { compact: true })).toBe("₹4,500");
    expect(formatMinor(450050, "INR", { compact: true })).toBe("₹4,500.50");
  });

  it("renders an em dash for an unknown amount, never zero", () => {
    // "₹0" for "we do not know" is a number an admin will act on.
    expect(formatMinor(null)).toBe("—");
    expect(formatMinor(undefined)).toBe("—");
    expect(formatMinor(0)).toBe("₹0.00");
  });

  it("abbreviates large amounts in lakh and crore", () => {
    // An Indian admin reads ₹12.35L far faster than ₹1,234,567.
    expect(formatCompactMoney(123456700)).toBe("₹12.35L");
    expect(formatCompactMoney(1234567800)).toBe("₹1.23Cr");
    expect(formatCompactMoney(450000)).toBe("₹4,500");
  });
});

describe("percentages", () => {
  it("signs a change so direction is readable without colour", () => {
    expect(formatPercent(12.3)).toBe("+12.3%");
    expect(formatPercent(-4)).toBe("-4.0%");
  });

  it("renders an em dash for no prior data", () => {
    // Distinct from 0%: "no change" and "nothing to compare" look identical on
    // a tile and mean completely different things.
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(0)).toBe("0.0%");
  });

  it("converts basis points, which is how commission is stored", () => {
    // Integers on the wire, because a float percentage on a large booking
    // rounds differently on two machines.
    expect(formatBps(1500)).toBe("15%");
    expect(formatBps(1250)).toBe("12.50%");
    expect(formatBps(0)).toBe("0%");
  });
});
