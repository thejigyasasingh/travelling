# Roaming & Wandering — Admin

React 19 · TypeScript · Tailwind v4 · React Query · Recharts

The internal panel: dashboard, users, properties, vendors, bookings, payments,
coupons, analytics, notifications and support tickets.

```bash
cp .env.example .env.local
npm install
npm run dev            # http://localhost:5174, /api proxied to :8000
npm run check          # lint + typecheck + tests
ADMIN_LIVE=1 npm test  # also parses live API responses
```

---

## A separate app, deliberately

Not a route inside the customer site. An admin panel bolted onto the public app
ships its routes, its permission names and its whole API surface to everyone who
opens the home page. This deploys separately, behind whatever network controls
the environment has, and carries `noindex`.

The HTTP client is a deliberate copy of the customer app's rather than a shared
package: the two deploy independently, and a shared runtime dependency between
an internal tool and a public site eventually forces one to ship because the
other did. What *is* shared is the API contract, and `tests/liveContract.test.ts`
pins it against a running server.

## Authorisation

The gate in `AuthGate.tsx` is **defence in depth, not enforcement**. Every admin
endpoint checks its own permission server-side. The client-side check exists so
a support agent is not shown a revenue chart that will only 403 when it loads,
and so someone who finds the URL gets one clear sentence instead of ten broken
panels.

The permissions come from the RBAC catalogue the backend already had:
`user:read:any`, `booking:read:any`, `payment:read:any`, `vendor:approve:any`,
`ticket:read:any`, `ticket:resolve:any`. Analytics is gated on payment access
rather than booking access, because it shows fees and vendor payables.

## The decisions that matter

**The dashboard leads with a to-do list, not charts.** The action queue —
vendors awaiting review, tickets past their first-response target, payments
stuck over thirty minutes — is the only part someone can act on. A front page of
six graphs is one where nobody notices the vendor waiting four days.

**Money is integer minor units, and the analytics page shows a breakdown rather
than a number.** "Revenue: ₹50L" is what everyone quotes and nobody can act on;
gross → refunds → gateway fees → commission → vendor payable is a shape that
reconciles against a bank statement. Fees and commission come from the payment
ledger, not from recomputed percentages, so this page and the settlement report
cannot disagree.

**Filters live in the URL.** Support and engineering paste these links to each
other; "the failed payments are here" has to be a link, not a sequence of clicks
to reproduce.

**Every list is one `DataTable`.** Loading, empty, error, forbidden and paging
behave identically across ten screens rather than being re-invented per page —
and a table that shows "no results" when the request actually failed teaches an
admin to distrust the screen.

**A 403 gets no retry button.** Retrying will not grant a permission, and a
button that does nothing teaches people that buttons lie.

**Internal notes are visually unmistakable.** They render on a dashed amber
card with an explicit "not sent to guest" badge, and the compose box changes
colour when the internal toggle is on. The server is what actually filters them
out of the guest's view; this is so an agent never *thinks* they are writing
publicly when they are not, or the reverse.

**`null` is never rendered as zero.** A KPI with no prior period says "no prior
period", not "0%". A coupon with no total limit shows "∞", not "0". The two look
identical on a tile and mean opposite things.

---

## Testing

```bash
npm test                    # unit
ADMIN_LIVE=1 npm test       # also runs the live contract suite
```

The live suite asserts the arithmetic the finance team checks first — gross
minus refunds equals net, vendors are never owed more than was taken — and that
the server refuses an uncapped percentage coupon. It skips itself when nothing
is listening.
