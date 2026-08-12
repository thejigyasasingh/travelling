# Roaming & Wandering — customer web app

React 19 · TypeScript · Tailwind v4 · React Query · Vite

The guest-facing site: search, property pages, booking, checkout, trips, wishlist
and account. It talks to the API in `../backend` and holds no business rules of
its own beyond presentation.

```bash
cp .env.example .env.local     # everything in it is public by design
npm install
npm run dev                    # http://localhost:5173, /api proxied to :8000
npm run check                  # lint + typecheck + tests, the same gate CI runs
```

---

## Layout

The dependency rule points inward. `ui` and `pages` may import `application`;
`application` may import `domain` and `core`; `domain` imports nothing but
`core`. Nothing inward imports React, `fetch`, or a DTO.

```
src/
├── core/            Framework-free primitives: Money, dates, errors, config, URL safety
├── domain/          Types and rules — booking status, cancellation policy, review validity
├── application/     Ports (the seam), React Query hooks, query keys, URL-state
├── infrastructure/  HTTP client, repositories, DTOs, mappers, local storage
├── ui/              Design system: Button, Field, Modal, Rating, feedback states
├── features/        Feature components: search bar, filters, gallery, booking widget
├── pages/           One file per route
└── app/             Router, layout, providers, auth gate, error boundary
```

**`application/ports.ts` is the seam.** Every hook depends on an interface, never
on `fetch`. That is why `tests/searchPage.test.tsx` renders a full page with no
network, no MSW and no mocked `fetch` — just an object literal. If a page test
ever needs a fetch mock, the seam has leaked.

**DTOs stop at `infrastructure/`.** `snake_case` wire types are mapped to domain
types in `mappers.ts`, so a field rename on the server is a change in one file
rather than a search-and-replace through forty components.

---

## The decisions that matter

**The access token lives in memory; the refresh token is an HttpOnly cookie the
app never reads.** A token in `localStorage` is readable by any script that ends
up on the page and survives a tab close. In memory, an XSS must exfiltrate
during the page's lifetime. The cost — a reload starts with no token — is paid
by calling `/auth/refresh` on boot, where the cookie is the credential. This is
also why the app must be **same-origin** with the API: the cookie is scoped to
`/api/v1/auth`, and a cross-origin base URL drops it, so login would work and
session restore would not.

**One refresh, however many 401s.** A page fires several queries at once; if the
token has expired they all get 401. The backend rotates refresh tokens and
treats reuse as theft — it revokes the whole family and signs the user out
everywhere. So the client shares a single in-flight refresh promise and everyone
retries once behind it. Tested in `tests/httpClient.test.ts`, because the
failure is invisible in development and catastrophic in production.

**Money is integer minor units end to end.** Paise, never rupees, until the
moment a string is rendered. `0.1 + 0.2 !== 0.3` is a funny blog post and a
mismatched invoice.

**Search filters live in the URL.** A filtered result set can be shared,
bookmarked and reloaded; the back button undoes one filter instead of leaving
the page. One source of truth means the query string and the UI cannot disagree.

**Prices come from the server, always.** The booking widget asks for a quote and
waits. Nightly rates vary by date, weekends have multipliers and tax is slabbed
— reimplementing that here would produce a number that disagrees with the server
at checkout, which the API correctly rejects with a 409.

**The idempotency key is minted when the booking page mounts, not per click.** A
double-tapped "Reserve" is a second room held on real inventory. A key generated
inside the click handler defeats the entire mechanism.

**The client never decides that a payment succeeded.** Razorpay hands the
browser a signature; only the server, which holds the secret, can say whether it
is genuine. And if verification fails *after* the money moved, the guest is sent
to their booking — which polls — rather than being told something went wrong and
invited to pay twice. The webhook is the authority.

**A dismissed payment sheet is not an error.** People close it to check a card.
The hold is still alive; that is a returnable state, not a red banner.

**Stay dates are half-open.** `[check_in, check_out)` — a 12th→14th stay is two
nights and the 14th is free for the next guest. Dates are `YYYY-MM-DD` strings,
never `Date` objects silently shifted by a timezone.

---

## Two features are not backed by an API yet

Both are isolated behind their port, and swapping either is one file plus one
line in `infrastructure/repositories.ts`.

**Wishlist** — saved stays live in this device's `localStorage`. They do not
follow the guest to another device, and clearing site data loses them. Shipping
it anyway is deliberate: a wishlist is how people plan a trip over days, and the
alternative is no wishlist at all. The limitation is stated on the page rather
than hidden, and each entry stores a snapshot of the card, so the page renders
with no network and a saved stay survives being delisted.

**Reviews** — the backend has no reviews module. Two things are true at once and
both are surfaced honestly: the **star ratings and counts shown across the site
are real** (they come from the property module, through the catalogue), while
individual review *text* has no source, so reads return empty and writes stay on
the device. Seeding plausible-looking reviews would have been easy and is
exactly the wrong call — fabricated reviews on a booking site are
indistinguishable from fraud.

The API also has no profile-update or notification-preference endpoints, so
Profile shows what is true and offers only the actions that exist, and Settings
says its notification toggles are device-local.

---

## Accessibility

Not a pass at the end; the primitives enforce it. Every input is wired to its
label and its error via `aria-describedby` + `aria-invalid` — a red border says
nothing to a screen reader or to someone with a colour vision deficiency. Modals
use the native `<dialog>`, which brings focus trapping, `Esc` and page inertness
that a hand-rolled div never gets right. Focus rings are never removed. Tap
targets are 44px on coarse pointers. `prefers-reduced-motion` is honoured. Every
page has a skip link as its first tab stop.

---

## Testing

```bash
npm test          # vitest
npm run check     # what CI runs
```

Tests cover what breaks expensively: money formatting and Indian digit grouping,
half-open date arithmetic across months, leap days and DST, the single-flight
refresh, the open-redirect guard on `?next=`, and a full search page rendered
against fake repositories.

The `/auth/refresh` fixtures mirror the real endpoint, verified against a running
server. An earlier version of them invented a flatter shape, which let a genuine
bug pass the suite — the client read `access_token` off the top level of a
response that nests it under `tokens`, so **every session restore silently
failed**. Fixtures are now written from real responses, never from a schema
listing.
