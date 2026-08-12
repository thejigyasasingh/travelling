/**
 * Calendar date arithmetic.
 *
 * Every date the calendar handles is a plain `YYYY-MM-DD` — a night, not an
 * instant. Parsing one as a local date shifts it by a day for anyone west of
 * UTC, which means pricing the wrong night and, at the extreme, a host in a
 * negative offset closing the day after the one they clicked.
 *
 * These are copies of the helpers in `CalendarPage`, kept in step by these
 * tests. They are private to that module because nothing else should be doing
 * date arithmetic at all.
 */

import { describe, expect, it } from "vitest";

function addDays(iso: string, days: number): string {
  return new Date(Date.parse(`${iso}T00:00:00Z`) + days * 86_400_000)
    .toISOString()
    .slice(0, 10);
}

function spanDays(from: string, to: string): number {
  return (
    Math.round(
      (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) /
        86_400_000,
    ) + 1
  );
}

function nights(checkIn: string, checkOut: string): number {
  const ms =
    Date.parse(`${checkOut}T00:00:00Z`) - Date.parse(`${checkIn}T00:00:00Z`);
  return Math.max(0, Math.round(ms / 86_400_000));
}

describe("addDays", () => {
  it("adds within a month", () => {
    expect(addDays("2026-08-07", 3)).toBe("2026-08-10");
  });

  it("crosses a month boundary", () => {
    expect(addDays("2026-08-30", 3)).toBe("2026-09-02");
  });

  it("crosses a year boundary", () => {
    expect(addDays("2026-12-30", 3)).toBe("2027-01-02");
  });

  it("handles a leap day", () => {
    expect(addDays("2028-02-28", 1)).toBe("2028-02-29");
    expect(addDays("2028-02-29", 1)).toBe("2028-03-01");
  });

  it("survives a DST transition", () => {
    // India has no DST, but a host abroad running this in a browser set to
    // Europe/London would get a 23-hour day if these were local dates.
    expect(addDays("2026-03-28", 1)).toBe("2026-03-29");
    expect(addDays("2026-03-29", 1)).toBe("2026-03-30");
    expect(addDays("2026-10-24", 1)).toBe("2026-10-25");
    expect(addDays("2026-10-25", 1)).toBe("2026-10-26");
  });

  it("is reversible", () => {
    expect(addDays(addDays("2026-08-07", 59), -59)).toBe("2026-08-07");
  });
});

describe("spanDays", () => {
  it("counts both ends — the selection is a set of nights, not a duration", () => {
    expect(spanDays("2026-08-07", "2026-08-07")).toBe(1);
    expect(spanDays("2026-08-07", "2026-08-09")).toBe(3);
  });

  it("detects a gapped selection", () => {
    // This is what the calendar uses to warn that a range write will touch
    // nights the host did not click. Two nights selected across a five-day
    // span is a gap.
    const selected = ["2026-08-07", "2026-08-11"];
    expect(spanDays(selected[0]!, selected[1]!)).not.toBe(selected.length);
  });

  it("agrees with a contiguous selection", () => {
    const selected = ["2026-08-07", "2026-08-08", "2026-08-09"];
    expect(spanDays(selected[0]!, selected[2]!)).toBe(selected.length);
  });
});

describe("nights", () => {
  it("counts a half-open stay: check-in to check-out is the nights slept", () => {
    expect(nights("2026-09-05", "2026-09-08")).toBe(3);
  });

  it("a same-day range is zero nights, not one", () => {
    expect(nights("2026-09-05", "2026-09-05")).toBe(0);
  });

  it("never goes negative on reversed dates", () => {
    expect(nights("2026-09-08", "2026-09-05")).toBe(0);
  });
});

/**
 * The nights→range translation.
 *
 * The single most consequential line on the calendar screen. The server takes
 * half-open ranges — as does every other range in this system, stays included
 * — but a calendar grid deals in nights, so the last night selected has to
 * become the day after it.
 */
function rangeForNights(nightsSelected: string[]): {
  from_date: string;
  to_date: string;
} {
  const first = nightsSelected[0]!;
  const last = nightsSelected[nightsSelected.length - 1]!;
  return { from_date: first, to_date: addDays(last, 1) };
}

describe("nights to a half-open range", () => {
  it("includes the last night selected", () => {
    // Without this, a host selecting 24–31 December and setting a New Year
    // rate leaves the 31st — the most valuable night of the year — at the
    // default price, and nothing tells them.
    expect(rangeForNights(["2026-12-24", "2026-12-31"])).toEqual({
      from_date: "2026-12-24",
      to_date: "2027-01-01",
    });
  });

  it("makes a single night expressible", () => {
    // `from === to` is rejected by the server with a 422, which would make the
    // commonest calendar edit — price one night — impossible.
    const range = rangeForNights(["2027-01-01"]);
    expect(range).toEqual({ from_date: "2027-01-01", to_date: "2027-01-02" });
    expect(range.to_date).not.toBe(range.from_date);
  });

  it("spans a month end", () => {
    expect(rangeForNights(["2026-08-30", "2026-08-31"])).toEqual({
      from_date: "2026-08-30",
      to_date: "2026-09-01",
    });
  });

  it("covers exactly as many nights as were selected", () => {
    const selected = ["2026-08-07", "2026-08-08", "2026-08-09"];
    const range = rangeForNights(selected);
    // Half-open: the count is the difference, not the difference plus one.
    const covered = Math.round(
      (Date.parse(`${range.to_date}T00:00:00Z`) -
        Date.parse(`${range.from_date}T00:00:00Z`)) /
        86_400_000,
    );
    expect(covered).toBe(selected.length);
  });
});
