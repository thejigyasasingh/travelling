/**
 * The arithmetic a host reconciles against their bank statement.
 *
 * Everything on the wire is integer minor units. The only place rupees exist is
 * a form field and a rendered string, and both conversions live in one function
 * each — these tests pin those two boundaries, because a rounding error here is
 * a host being paid the wrong amount.
 */

import { describe, expect, it } from "vitest";
import { formatCompactMoney, formatMinor, formatPercent } from "@/core/format";

/** The same conversion the room and calendar forms do: rupees typed by a human
 *  into paise on the wire. Kept here as the specification of that one line. */
function rupeesToMinor(input: string): number {
  return Math.round(Number(input) * 100);
}

describe("rupees to paise", () => {
  it("converts whole rupees", () => {
    expect(rupeesToMinor("6000")).toBe(600_000);
  });

  it("keeps both decimal places", () => {
    expect(rupeesToMinor("1234.55")).toBe(123_455);
  });

  it("rounds rather than truncating", () => {
    // 1234.55 * 100 is 123454.99999999999 in binary floating point. Truncation
    // would quietly underpay by a paisa on a value a host typed exactly.
    expect(rupeesToMinor("1234.55")).not.toBe(123_454);
    expect(rupeesToMinor("0.005")).toBe(1);
  });

  it("handles zero", () => {
    expect(rupeesToMinor("0")).toBe(0);
  });
});

describe("formatMinor", () => {
  it("renders paise as rupees with two decimals", () => {
    // Asserted structurally: ICU renders the symbol and separators differently
    // across Node versions, and pinning the exact string makes the test fail on
    // an upgrade rather than on a bug.
    const rendered = formatMinor(123_455);
    expect(rendered).toContain("1,234.55");
  });

  it("shows an em dash for a missing amount, never zero", () => {
    // ₹0 is a number a host would act on. "we do not know" must look different
    // from "nothing".
    expect(formatMinor(null)).toBe("—");
    expect(formatMinor(undefined)).toBe("—");
    expect(formatMinor(0)).not.toBe("—");
  });

  it("drops the decimals only when they are zero and compact is asked for", () => {
    expect(formatMinor(600_000, "INR", { compact: true })).not.toContain(".00");
    expect(formatMinor(600_050, "INR", { compact: true })).toContain(".50");
  });
});

describe("formatCompactMoney", () => {
  it("uses lakh and crore, which is how the number will be spoken", () => {
    expect(formatCompactMoney(12_34_567_00)).toContain("L");
    expect(formatCompactMoney(1_00_00_000_00)).toContain("Cr");
  });

  it("leaves small amounts alone", () => {
    expect(formatCompactMoney(50_000)).not.toContain("L");
  });
});

describe("formatPercent", () => {
  it("signs a positive change, so a chart label reads as a direction", () => {
    expect(formatPercent(12.3)).toBe("+12.3%");
    expect(formatPercent(-4)).toBe("-4.0%");
  });

  it("shows an em dash rather than 0% for a missing figure", () => {
    expect(formatPercent(null)).toBe("—");
  });
});
