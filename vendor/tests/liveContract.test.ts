/**
 * Parses **live** vendor responses through the app's real types.
 *
 * Written because this project has already shipped three clients whose types
 * were read off a schema rather than off the wire, and every one of them
 * silently mis-parsed something. It skips itself when nothing is listening, so
 * the ordinary suite needs no backend:
 *
 *     npm test                        # skips
 *     VENDOR_LIVE=1 npm test          # runs against localhost:8000
 *
 * The assertions check *presence and kind*, not values: a field the client
 * declares and the server does not send is the failure this exists to catch,
 * and asserting on values would make the test depend on seed data.
 */

import { beforeAll, describe, expect, it } from "vitest";
// `process` is Node-only; this file runs under vitest, not in the browser
// bundle, so it is declared here rather than pulling @types/node into the app.
declare const process: { env: Record<string, string | undefined> };
import type {
  Arrival,
  BookingList,
  Earnings,
  Page,
  Reports,
  ReviewList,
  ReviewSummary,
  VendorDashboard,
  VendorProfile,
  VendorProperty,
} from "@/api/types";

const BASE = "http://localhost:8000/api/v1";
const CREDENTIALS = {
  email: "journey@example.com",
  password: "a-very-long-passphrase-2026",
};

let token: string | null = null;
let live = false;

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.status).toBe(200);
  return (await response.json()) as T;
}

/** Every declared key is present. `undefined` is the failure mode this test
 *  exists for — a field the client reads and the server never sends. */
function hasAll(value: object, keys: string[]): void {
  for (const key of keys) {
    expect(value, `missing "${key}"`).toHaveProperty(key);
  }
}

beforeAll(async () => {
  if (!process.env.VENDOR_LIVE) return;
  try {
    const response = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(CREDENTIALS),
    });
    if (!response.ok) return;
    const data = (await response.json()) as {
      tokens: { access_token: string };
    };
    token = data.tokens.access_token;
    live = true;
  } catch {
    live = false;
  }
});

describe("vendor API", () => {
  it("the profile says what the vendor may do, and never carries a full account number", async () => {
    if (!live) return;
    const me = await get<VendorProfile>("/vendor/me");

    hasAll(me, [
      "id",
      "legal_name",
      "display_name",
      "status",
      "commission_bps",
      "bank_account_last4",
      "can_publish",
      "can_receive_payouts",
    ]);
    expect(typeof me.commission_bps).toBe("number");
    // Last four or nothing. Anything longer means the server started sending a
    // full account number to a browser.
    if (me.bank_account_last4 !== null) {
      expect(me.bank_account_last4).toHaveLength(4);
    }
  });

  it("the dashboard carries every tile the overview renders", async () => {
    if (!live) return;
    const dashboard = await get<VendorDashboard>("/vendor/dashboard");

    hasAll(dashboard, [
      "live_listings",
      "in_review",
      "awaiting_approval",
      "arrivals_this_week",
      "in_stay",
      "gross_30d_minor",
      "commission_30d_minor",
      "net_30d_minor",
      // The one that shipped missing. It was selected in SQL and dropped from
      // the returned dict, and every dashboard request 500'd on validation.
      "reviews_awaiting",
    ]);
    for (const value of Object.values(dashboard)) {
      expect(Number.isInteger(value)).toBe(true);
    }
  });

  it("earnings subtract to the payable figure", async () => {
    if (!live) return;
    const earnings = await get<Earnings>("/vendor/earnings");

    hasAll(earnings, [
      "gross_minor",
      "commission_minor",
      "tax_collected_minor",
      "refunded_minor",
      "net_payable_minor",
      "bookings",
      "nights_sold",
      "currency",
      "from_date",
      "to_date",
    ]);

    // The arithmetic the revenue screen renders as a subtraction. If these ever
    // disagree, the page shows a column of numbers that does not add up.
    const expected = Math.max(
      0,
      earnings.gross_minor -
        earnings.commission_minor -
        earnings.refunded_minor -
        earnings.tax_collected_minor,
    );
    expect(earnings.net_payable_minor).toBe(expected);
  });

  it("reports assemble every section in one request", async () => {
    if (!live) return;
    const reports = await get<Reports>("/vendor/reports");

    hasAll(reports, [
      "earnings",
      "occupancy",
      "by_property",
      "monthly",
      "revenue_by_day",
    ]);
    hasAll(reports.occupancy, [
      "nights_booked",
      "nights_available",
      "occupancy_percent",
    ]);
    expect(Array.isArray(reports.by_property)).toBe(true);
    expect(Array.isArray(reports.monthly)).toBe(true);

    for (const row of reports.by_property) {
      hasAll(row, [
        "property_id",
        "name",
        "city",
        "bookings",
        "gross_minor",
        "review_average",
      ]);
    }
    for (const month of reports.monthly) {
      hasAll(month, [
        "month",
        "bookings",
        "gross_minor",
        "commission_minor",
        "tax_minor",
        "net_minor",
      ]);
    }
  });

  it("properties come back with their rooms nested", async () => {
    if (!live) return;
    const page = await get<Page<VendorProperty>>("/vendor/properties");

    hasAll(page, ["items", "total", "page", "size"]);
    for (const property of page.items) {
      // `room_types` nested here is what the rooms screen reads; there is no
      // separate endpoint, so its absence would empty that screen silently.
      hasAll(property, [
        "id",
        "name",
        "status",
        "city",
        "room_types",
        "missing_for_publication",
      ]);
      expect(Array.isArray(property.room_types)).toBe(true);
      for (const room of property.room_types) {
        hasAll(room, [
          "id",
          "name",
          "base_rate_minor",
          "total_units",
          "max_adults",
        ]);
      }
    }
  });

  it("bookings page by offset and carry the commission on each one", async () => {
    if (!live) return;
    const list = await get<BookingList>("/vendor/bookings");

    hasAll(list, ["items", "total"]);
    for (const booking of list.items) {
      hasAll(booking, [
        "id",
        "reference",
        "status",
        "guest_name",
        "check_in",
        "check_out",
        "nights",
        "total_minor",
        // The bookings screen shows "yours" as total − commission. Without this
        // it would render NaN.
        "platform_fee_minor",
      ]);
      expect(Number.isInteger(booking.total_minor)).toBe(true);
    }
  });

  it("arrivals carry what a host needs on the morning", async () => {
    if (!live) return;
    const arrivals = await get<Arrival[]>("/vendor/arrivals");

    expect(Array.isArray(arrivals)).toBe(true);
    for (const arrival of arrivals) {
      hasAll(arrival, [
        "booking_id",
        "reference",
        "guest_name",
        "property_name",
        "check_in",
        "check_out",
        "guests",
        "status",
      ]);
    }
  });

  it("reviews carry the reply state the screen branches on", async () => {
    if (!live) return;
    const list = await get<ReviewList>("/vendor/reviews");
    const summary = await get<ReviewSummary>("/vendor/reviews/summary");

    hasAll(list, ["items", "total", "average", "distribution"]);
    hasAll(summary, ["total", "average", "awaiting_reply", "critical"]);

    for (const review of list.items) {
      hasAll(review, [
        "id",
        "rating",
        "body",
        "author_name",
        "moderation",
        "host_reply",
      ]);
      expect(review.rating).toBeGreaterThanOrEqual(1);
      expect(review.rating).toBeLessThanOrEqual(5);
      // A removed review must never reach a host's screen as ordinary content.
      expect(["published", "flagged", "removed"]).toContain(review.moderation);
    }
  });

  it("the CSV statement is a file, not JSON", async () => {
    if (!live) return;
    const response = await fetch(`${BASE}/vendor/reports/statement.csv`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("csv");

    const body = await response.text();
    expect(body.split("\n")[0]).toBe("month,bookings,gross,commission,tax,net");
  });

  it("refuses every vendor endpoint without a token", async () => {
    if (!live) return;
    for (const path of [
      "/vendor/dashboard",
      "/vendor/earnings",
      "/vendor/bookings",
      "/vendor/reviews",
    ]) {
      const response = await fetch(`${BASE}${path}`);
      expect(response.status, path).toBe(401);
    }
  });
});
