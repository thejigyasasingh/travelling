# Vendor portal

The tool a host runs their properties from: listings, rooms, pricing,
availability, bookings, reviews, revenue and reports.

```bash
npm install
npm run dev            # http://localhost:5175, proxying /api to :8000
npm run check          # lint + typecheck + tests
```

## Why this is a third app

There are three front ends against one API — the customer site, the admin
panel, and this. They could have been one build with role-gated routes. They are
not, and the reason is the one that matters: **staff see every vendor's revenue,
and a vendor must see only their own.** The safest way to keep that true is for
this bundle to contain no admin route at all. A role check inside a shared
bundle is one `if` away from shipping a competitor's numbers.

The same argument applies to the customer site in the other direction: none of
this belongs in the JavaScript a member of the public downloads.

What *is* shared is the contract, not the runtime. `core/http.ts`,
`core/format.ts` and the table primitives are deliberate copies of the admin
panel's. A shared package between three apps that deploy independently
eventually forces one to ship because another did.

## The rule the whole portal is built around

**No request sends a vendor id.** The server derives it from the access token
and filters every query on it in SQL. A client-supplied id is one `curl` away
from another host's bookings, and no amount of UI makes that safe. If you find
yourself adding `vendor_id` to a request, the endpoint is wrong, not the client.

Related: a resource belonging to another vendor returns **404, not 403**. The
difference between "not yours" and "does not exist" is a way to enumerate what
exists.

## Screens

| Route | What it is for |
| --- | --- |
| `/` | What needs doing, then the month's money, then this week's arrivals |
| `/properties` | Listings, and inside each: details, rooms, the publish checklist |
| `/calendar` | Pricing **and** availability on one screen, edited by night range |
| `/bookings` | Requests to accept or decline, and every stay past and future |
| `/reviews` | What guests said, and the host's one reply |
| `/revenue` | The payout subtraction: booked → commission → refunds → tax → yours |
| `/reports` | Per-property and month-by-month, plus the CSV an accountant opens |

Pricing and availability are one screen on purpose. A host raising the New Year
rate is also closing the 31st and setting a three-night minimum; splitting those
across pages means doing the same date arithmetic three times and being unable
to see the first change while making the second.

## Two things that will bite you

**Ranges are half-open, and the calendar deals in nights.** Every date range in
this system — stays included — is `[from, to)`. A calendar grid selects
*nights*, so the last night selected has to become the day after it before the
request goes out. The conversion lives in exactly one place, `CalendarPage`'s
`EditPanel`, and is pinned by `tests/calendarDates.test.ts`. Without it,
selecting 24–31 December and setting a New Year rate silently leaves the 31st —
the most valuable night of the year — at the default price, and a single-night
edit fails with a 422 because the server rejects `from === to`.

**Money is integer minor units end to end.** Paise on the wire, always. Rupees
exist in exactly two places: a form field a human types into, and a string that
gets rendered. Both conversions are one function each and both are tested. A
`Math.round`, never a truncation — `1234.55 * 100` is `123454.99999999999` in
binary floating point, and truncating underpays a host by a paisa on a number
they typed exactly.

## Tests

```bash
npm test                     # unit; no backend needed
VENDOR_LIVE=1 npm test       # also parses live responses through the real types
```

`tests/liveContract.test.ts` is the one that earns its keep. This project has
now shipped clients whose types were read off a schema rather than off the wire,
and every one of them mis-parsed something silently. It logs in against a
running server, fetches each endpoint, and asserts that every field the client
reads is actually present. It skips itself when nothing is listening, so the
ordinary suite needs no backend.

It also checks two things that are not shape:

- `net_payable_minor` equals the subtraction the revenue screen renders, so the
  page cannot show a column of numbers that does not add up;
- `bank_account_last4` is four characters or null, so a full account number
  reaching a browser fails the build rather than the audit.

## What is not here

Image upload beyond the existing endpoints, messaging, and multi-user vendor
accounts (`vendor_staff` exists in the RBAC catalogue but nothing grants it
yet). Vendor registration itself is on the customer site — this portal assumes
you already have a vendor and tells you plainly when you do not.
