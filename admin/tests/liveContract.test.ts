/**
 * Parses **live** admin responses through the app's real types.
 *
 * Written because this project has already shipped two clients whose types were
 * read off a schema rather than off the wire, and both silently mis-parsed. It
 * skips itself when nothing is listening, so the ordinary suite needs no
 * backend:
 *
 *     npm test                       # skips
 *     ADMIN_LIVE=1 npm test          # runs against localhost:8000
 */

import { beforeAll, describe, expect, it } from "vitest";
// `process` is Node-only; this file runs under vitest, not in the browser
// bundle, so it is declared here rather than pulling @types/node into the app.
declare const process: { env: Record<string, string | undefined> };
import type {
  Analytics,
  Dashboard,
  Paged,
  AdminUser,
  AdminVendor,
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

beforeAll(async () => {
  if (!process.env.ADMIN_LIVE) return;
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

describe("admin API", () => {
  it("the dashboard carries kpis, series and an action queue", async () => {
    if (!live) return;
    const dashboard = await get<Dashboard>("/admin/dashboard?window_days=30");

    expect(dashboard.kpis.length).toBeGreaterThan(0);
    for (const kpi of dashboard.kpis) {
      expect(typeof kpi.value).toBe("number");
      // `null` is meaningful — no prior period to compare against — and must
      // survive the round trip rather than becoming 0.
      expect(
        kpi.change_percent === null || typeof kpi.change_percent === "number",
      ).toBe(true);
    }

    // A dense series: days with no bookings appear as zero, so a chart cannot
    // draw a straight line through a bad week.
    expect(dashboard.bookings_by_day).toHaveLength(30);
    expect(dashboard.revenue_by_day).toHaveLength(30);

    for (const key of [
      "vendors_pending",
      "tickets_open",
      "notifications_failed",
    ]) {
      expect(typeof dashboard.action_queue[key]).toBe("number");
    }
  });

  it("analytics reconciles: gross − refunds = net", async () => {
    if (!live) return;
    const analytics = await get<Analytics>("/admin/analytics");
    const { gross_minor, refunded_minor, net_minor, vendor_payable_minor } =
      analytics.revenue;

    // The one arithmetic relationship the finance team checks first.
    expect(net_minor).toBe(gross_minor - refunded_minor);
    // Vendors can never be owed more than was taken.
    expect(vendor_payable_minor).toBeLessThanOrEqual(net_minor);
    expect(analytics.cancellation_rate).toBeGreaterThanOrEqual(0);
    expect(analytics.cancellation_rate).toBeLessThanOrEqual(100);
  });

  it("lists page with meta the table can drive", async () => {
    if (!live) return;
    const users = await get<Paged<AdminUser>>("/admin/users?page=1&size=5");

    expect(users.meta.page).toBe(1);
    expect(users.meta.size).toBe(5);
    expect(users.meta.pages).toBeGreaterThanOrEqual(1);
    for (const user of users.items) {
      expect(user.email).toContain("@");
      expect(Array.isArray(user.roles)).toBe(true);
      expect(typeof user.email_verified).toBe("boolean");
    }
  });

  it("vendors carry the fields the review panel decides on", async () => {
    if (!live) return;
    const vendors = await get<Paged<AdminVendor>>("/admin/vendors");
    for (const vendor of vendors.items) {
      expect(typeof vendor.commission_bps).toBe("number");
      // Basis points, not a float percentage.
      expect(Number.isInteger(vendor.commission_bps)).toBe(true);
      expect(vendor.commission_bps).toBeLessThanOrEqual(3000);
    }
  });

  it("refuses a percentage coupon with no cap", async () => {
    if (!live) return;
    // The most expensive mistake this API can make: 25% of a ₹4,00,000 week is
    // ₹1,00,000. The server refuses it, not just the form.
    const response = await fetch(`${BASE}/admin/coupons`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        code: "UNCAPPED",
        description: "no cap",
        discount_type: "percent",
        value: 2000,
        starts_at: "2026-08-01T00:00:00Z",
        ends_at: "2026-12-31T00:00:00Z",
      }),
    });
    expect(response.status).toBe(409);
  });
});
