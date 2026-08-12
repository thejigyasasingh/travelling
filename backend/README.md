# Roaming & Wandering — Backend

Travel booking platform API. FastAPI · Python 3.13 · PostgreSQL 17 (PostGIS) · Redis · Celery.

Built as a **modular monolith** with clean-architecture layering, so that
extracting a service later is a deployment change rather than a rewrite.

---

## Quick start

```bash
make setup     # JWT keypairs, .env, virtualenv
make up        # postgres, redis, minio, mailpit, api, worker, beat
```

| Service         | URL                              |
| --------------- | -------------------------------- |
| API docs        | http://localhost:8000/docs       |
| Health          | http://localhost:8000/health/ready |
| MinIO console   | http://localhost:9001 (`minioadmin`/`minioadmin`) |
| Mail catcher    | http://localhost:8025            |

```bash
make test      # full suite
make check     # lint + types + architecture contracts
make logs      # tail api / worker / beat
make clean     # tear down, delete data volumes
```

`make help` lists everything.

---

## Layout

```
src/app/
├── core/                 Cross-cutting. Imported by every layer, depends on none.
│   ├── config.py           Settings; validates at boot, refuses unsafe production config
│   ├── logging.py          structlog: correlation IDs + PII redaction at the emit boundary
│   ├── errors.py           Error taxonomy; stable `code` is the client contract
│   ├── clock.py            Time as an injected dependency, so time-based rules are testable
│   ├── types/              Money, DateRange, pagination — pure Python, no framework
│   └── security/           Argon2id hashing, RS256 JWT issue/verify
│
├── shared/
│   ├── domain/             Entity, AggregateRoot, DomainEvent, domain errors.
│   │                       Zero framework imports — enforced by .importlinter.
│   └── application/        Use-case base, Actor, and the *ports* infrastructure implements
│
├── infrastructure/       Adapters. Everything that talks to the outside world.
│   ├── database/           Engines (write/read split), Unit of Work, transactional outbox
│   ├── cache/              Redis pools, cache, locks, rate limiter, idempotency store
│   ├── queue/              Celery app, outbox relay
│   ├── storage/            S3/MinIO presigned uploads
│   └── external/           HTTP client, circuit breaker, retry with jitter
│
├── interface/            Delivery. HTTP today, CLI alongside it.
│   ├── api/
│   │   ├── app.py            Application factory + middleware ordering
│   │   ├── deps.py           Request-scoped DI (session, UoW, actor, authorisation)
│   │   ├── exception_handlers.py  The ONLY exception→HTTP mapping in the codebase
│   │   ├── middleware/       Correlation, security headers, access log, body cap, rate limit
│   │   ├── routes/           Health and operational endpoints
│   │   └── v1/               Versioned API surface; module routers mount here
│   └── cli/                Operational commands over the same use cases
│
├── modules/              Business modules: auth, property, booking, payment, …
├── container.py          Composition root — the one place infrastructure is constructed
└── main.py               ASGI entry point
```

**The dependency rule**: `interface → infrastructure → application → domain`.
Arrows point inward, never outward. `lint-imports` fails the build if that is
violated, and separately if anything in `shared/domain` imports FastAPI,
SQLAlchemy, pydantic, Redis, Celery or httpx.

---

## Design decisions worth knowing before you edit

**Config fails at boot, not at request time.** `DEBUG=true`, a wildcard
`ALLOWED_HOSTS`, console logging or `ECHO_SQL` in production are boot failures.
A crash loop is visible and fixable; an API quietly serving stack traces is not.

**Writes go to the primary, always.** `get_write_session()` and
`get_read_session()` are separate dependencies rather than one flag, because
reading availability from a replica with 200 ms of lag corrupts inventory. The
replica engine also sets `default_transaction_read_only`, so a stray write
errors loudly instead of going somewhere unexpected.

**Domain events go through the outbox.** Use cases record events on the
aggregate; the Unit of Work writes them to the `outbox` table *in the same
transaction* as the state change. A relay drains them with
`SELECT … FOR UPDATE SKIP LOCKED`. `commit(); task.delay(...)` loses the event
whenever the process dies in between, and a confirmed booking with no
confirmation email is undetectable after the fact.

**Delivery is at-least-once.** Every consumer must be idempotent and deduplicate
on `event_id`. Exactly-once delivery does not exist across a process boundary.

**Access tokens are stateless and short (15 min); refresh tokens are stateful and
rotate.** Presenting an already-rotated refresh token means it was stolen, so
the whole token family is revoked. RS256, not HS256 — anything that can verify
an HS256 token can also forge one.

**Rate limiting fails open; auth endpoints fail closed.** A Redis outage must
not take the API down, but it also must not remove the only brake on credential
stuffing.

**Money is `int` minor units + an explicit currency.** Never a float. Splits go
through `Money.allocate()`, which is lossless by construction — that property is
what makes payout reconciliation possible.

**Stay ranges are half-open `[start, end)`.** Checkout day is not an occupied
night, matching the Postgres `daterange` bound used by the no-overbooking
exclusion constraint.

**Pagination is cursor-based.** `OFFSET 40000` makes Postgres walk and discard
40,000 rows. Offset paging is admin-only.

**Middleware order is load-bearing.** Documented at the top of
`interface/api/app.py`. CORS must sit *outside* rate limiting or a throttled
preflight breaks the browser app; security headers must sit outside the
exception handlers or error responses ship without them.

---

## Environment

Every setting is in `.env.example` with its rationale. Nested keys use a double
underscore: `DATABASE__POOL_SIZE` → `settings.database.pool_size`.

In staging and production **nothing** comes from `.env` — values are injected
from AWS Secrets Manager. `.env` is git-ignored and must never hold a real
credential, including a staging one.

The JWT keypair is generated locally by `make keys` into `secrets/`
(git-ignored). In the cloud the private key is injected as
`SECURITY__JWT_PRIVATE_KEY`; a key that has touched a developer's disk does not
sign production sessions.

---

## Database

```bash
make migration m="add bookings table"   # autogenerate
make migrate                            # apply
make migration-sql                      # print SQL without executing
make psql                               # shell
```

Read the generated migration before committing it. Autogenerate emits
`DROP` + `ADD` for a rename (which loses data), misses CHECK constraints, and
never uses `CONCURRENTLY`. The reviewer checklist is in `alembic/script.py.mako`
and is copied into every new migration.

Deploys are rolling, so the old code runs against the new schema for several
minutes. Schema changes follow **expand → migrate → contract** across three
releases; a column dropped in one step breaks every pod that has not restarted.

Migrations run as a one-shot job (`docker/entrypoint.sh migrate`), never from a
booting API container.

---

## Testing

```bash
make test-unit   # no I/O, milliseconds — run these on save
make test-int    # real postgres + redis (see below)
make test        # everything, with coverage
```

913 tests. The gate is **70%**, and the suite currently sits at 75%.

### Real services, two ways

Integration tests use **real Postgres (PostGIS) and real Redis**, and run
**Alembic migrations** rather than `metadata.create_all()`. Half of what this
system depends on — exclusion constraints, `SKIP LOCKED`, partial indexes,
JSONB, `daterange`, `geography`, Lua scripts — does not exist in SQLite and is
invisible to a mock, and it is the migrations that run in production.

Where those services come from is up to you:

```bash
# Point at something you already have — faster, and no Docker needed:
export TEST_DATABASE_DSN='postgresql+asyncpg://user@localhost:5433/rw_test'
export TEST_REDIS_URL='redis://localhost:6380/0'
make test

# Or set neither, and testcontainers starts throwaway ones (needs Docker).
make test
```

Both paths are exercised: CI uses the first (service containers), every
developer machine with Docker and no env vars uses the second. The database is
**not** cleaned between tests — isolation is by *unique data*, because the
application opens its own sessions through the container and a transaction
rollback in the test would not touch what the request committed.

### The API suite is the one that finds things

`tests/api/` drives the real application over an in-process ASGI transport:
real router, real middleware, real database, real Redis, no mocks. It exists
because of a pattern that held every single time:

> Every serious bug found in this codebase so far lived in code the unit suite
> never executed.

Coverage went 44% → 75% when this suite was added, and the 44% baseline had
every router, repository and unit-of-work at **0%** — precisely where the bugs
were. What it caught on its first run:

| Bug | Consequence |
|---|---|
| Every auth error returned 409 | Clients could not distinguish "wrong password" from "email taken" |
| Search page 2 returned 500 | Cursor pagination was broken for every sort order but one |
| `Idempotency-Key` was accepted and ignored | A double-tapped booking created two holds on real inventory |
| Admin property list guarded by `property:read:any` | Any signed-in traveller could enumerate every listing, including ones hosts had taken down, with rejection reasons |
| Blank `STORAGE__ENDPOINT_URL` crashed boot | boto3 rejects `""`; the documented "leave blank for real S3" was unbootable |

None of them were reachable from a unit test of a use case.

### Two things the fixtures do deliberately

**Rate limiting is off for the suite** (`RATELIMIT__ENABLED=false`). Every test
signs in, the limiter allows five logins per fifteen minutes per IP, and every
test arrives from the same address — so with it on, the sixth test to run fails
and *which one* depends on collection order. It is not left untested:
`tests/api/test_rate_limiting.py` builds its own application with limiting
enabled and picks a fresh identity per test.

**The refresh cookie's `Secure` flag is off** for the suite only. The ASGI
transport speaks `http://test` and httpx, behaving exactly as a browser would,
refuses to send a `Secure` cookie over plain HTTP. `test_auth_api.py` still
asserts HttpOnly, the scoped Path and SameSite.

Both overrides mutate `os.environ`, and the fixture restores it — see the
comment on `integration_settings`. It is not tidiness: `AUTH__REFRESH_COOKIE_SECURE=false`
is one of the exact things a production config is refused for, so leaking it
breaks `tests/unit/test_config.py` in a way that only reproduces when the
integration suite ran first.

---

## Running it in production

One image, five roles, selected by argument:

```bash
docker run <image> api       # gunicorn + uvicorn workers
docker run <image> worker    # Celery; QUEUES selects which queues
docker run <image> beat      # scheduler — EXACTLY ONE per environment
docker run <image> migrate   # migrations, then exit
docker run <image> shell
```

Queues are served by separate worker deployments — `critical` (payments,
booking confirmations) must never queue behind `media` or `bulk`.

Probes:

| Endpoint          | Checks                    | On failure |
| ----------------- | ------------------------- | ---------- |
| `/health/live`    | nothing external          | pod is restarted |
| `/health/ready`   | Postgres, Redis, replica  | pod leaves the load balancer |
| `/health/startup` | Postgres                  | boot still in progress |

Liveness deliberately checks nothing external: if it pinged Postgres, a database
blip would fail liveness fleet-wide and Kubernetes would restart everything,
turning a recoverable incident into a full outage with a cold cache.

`/metrics` is Prometheus scrape output and is **not** routed publicly.

---

## Conventions

* **Errors**: raise from `app.core.errors` or `app.shared.domain.errors`. Never
  raise `HTTPException` outside `exception_handlers.py`.
* **Logging**: `get_logger(__name__)`, structured key-values, never f-strings.
  Event names are `snake_case` past tense (`booking_confirmed`). PII is scrubbed
  at the emit boundary, but do not rely on it — don't log bodies.
* **Time**: inject `Clock`. `utcnow()` is for infrastructure only, and exists as
  one named function so a grep finds every unmockable read.
* **Naming**: tables plural (`bookings`), constraints via the convention in
  `database/base.py`, events past tense, use cases `VerbNounUseCase`.
* **Async**: no blocking calls in a coroutine. Sync libraries (boto3) go through
  `asyncio.to_thread`.

---

## Authentication

`src/app/modules/auth/` — the reference implementation for every module that
follows. Sign-in by password, Google or OTP; RS256 access tokens; rotating
refresh tokens with reuse detection; RBAC.

### Endpoints

| | |
| --- | --- |
| `POST /auth/register` · `POST /auth/email/verify` · `POST /auth/email/resend` | account creation |
| `POST /auth/login` · `POST /auth/google` · `POST /auth/otp/request` · `POST /auth/otp/verify` | sign-in |
| `POST /auth/refresh` · `POST /auth/logout` | token lifecycle |
| `POST /auth/password/forgot` · `/reset` · `/change` | recovery |
| `GET /auth/me` · `GET /auth/sessions` · `DELETE /auth/sessions/{id}` | profile and devices |
| `PATCH /auth/users/{id}/roles` | administration (superadmin) |

### The decisions that matter

**Nothing reveals whether an account exists.** `register` and
`password/forgot` return the same response either way, and login treats an
unknown email, a wrong password and an OAuth-only account identically —
including burning an equivalent Argon2 hash on the unknown-email path, because
otherwise response *timing* is the oracle that the generic error message was
meant to close.

**Lockout escalates and does not reset when the lock expires.** 5 failures →
1m, then 5m, 15m, 1h, 24h. The level clears only on a successful sign-in. If it
reset on expiry, an attacker would wait out each 60-second lock and get five
fresh attempts forever.

**Refresh tokens rotate, and replay burns the family.** A 30-day token on a
device we do not control cannot be protected by signature checks — a stolen one
is valid. Rotation means the legitimate client always holds the newest token,
so a *spent* token being presented again means two parties hold the same chain.
The whole family is revoked. A few seconds of grace after each rotation covers
the mobile client that lost its response, which is otherwise indistinguishable
from theft and would log out honest users constantly.

**Role definitions are code; role assignments are data.** `domain/rbac.py` is
the source of truth for what a role can do — version-controlled, reviewed,
identical in every environment. The `roles`/`permissions` tables are a
projection of it, seeded by migration, so an admin UI can list them and
`user_roles` can carry a foreign key. Authorisation therefore costs **zero
database queries**: the token carries roles, permissions expand in-process.

The cost is staleness bounded by the access-token TTL (15 min). Where that is
unacceptable, revoke sessions too — which `PATCH /roles` does on any revocation.

**Google links accounts only on a *verified* provider email.** Trusting an
unverified one would let anyone able to create a Google account claiming an
address take over the matching local account.

**OTP verification takes a challenge id, never a phone number.** If it took
both, an attacker could request a code to their own phone and submit it against
someone else's number. Binding the number to the challenge server-side makes
that impossible to express.

**Refresh tokens are returned in the body *and* as an HttpOnly cookie.**
Browsers use the cookie — script cannot read it, so it survives an XSS that
steals everything else. Mobile clients use the body and the platform keychain.

**Some failures must still commit.** A failed login writes the lockout counter
and *then* raises; reuse detection revokes the family and *then* raises.
Rolling those back would make both mechanisms decorative. See
`_PERSIST_ON_FAILURE` in `modules/auth/interface/deps.py`.

### Testing

139 unit tests, no containers. The lockout ladder, rotation grace window and
every RBAC boundary are exercised against a clock the test owns — which is what
keeping the domain framework-free buys.

---

## Properties

`src/app/modules/property/` — hotels, resorts, villas, apartments and
homestays; CRUD, amenities, images, pricing, availability, calendar and search.

### Endpoints

| | |
| --- | --- |
| `GET /search` · `/search/suggest` · `/amenities` | public search |
| `GET /properties/{id-or-slug}` · `/availability` · `POST /quote` | public detail |
| `POST|GET|PATCH|DELETE /vendor/properties[/{id}]` | listing CRUD |
| `/vendor/properties/{id}/room-types[/{id}]` | room types and rates |
| `/vendor/properties/{id}/images` · `/images/upload-url` | direct-to-S3 media |
| `/vendor/properties/{id}/room-types/{id}/calendar` · `/rates` · `/availability` | vendor calendar |
| `/vendor/properties/{id}/submit` · `/visibility` · `/checklist` | lifecycle |
| `/admin/properties/{id}/review` · `/suspend` | review queue |

### The decisions that matter

**One enum for five property types, not five aggregates.** They differ in
presentation and policy, not structure — all have units, rates, availability
and photos. The one real difference is `is_whole_unit`: a villa or apartment is
booked entire, so it may have only one room type and "2 rooms available" is
meaningless. Splitting them would mean five near-identical search queries.

**Inventory rows are sparse, and this is the central design decision.** The
obvious schema pre-materialises one row per room type per date — at a million
properties with three room types and a two-year window that is ~2.2 *billion*
rows that mostly say "nothing happened here". Instead a row exists only when a
date deviates from the default: booked, blocked, or repriced. Readers apply
`COALESCE(row, room_type_default)`. The table's size tracks business activity
rather than the calendar.

**Search is one statement.** Twenty cards need a cover image, a cheapest rate,
a rating and a distance. Hydrating aggregates would be 41 round trips. Sort
keys (`min_rate_minor`, `max_guests`, `review_average`) are trigger-maintained
columns on `properties`, because a sort must be satisfiable *before* the LIMIT
— computing "cheapest room" per candidate would run over every match, not just
the page returned.

**Availability is a `NOT EXISTS`, not a count.** "Is anything free for all
these nights?" is answered by looking for a night that is *not* free and
stopping at the first. Because inventory is sparse, that subquery only ever
touches rows representing a real booking or block.

**Every search index is partial on published + not-deleted.** Drafts are the
majority of rows in a marketplace and search never reads them.

**PostGIS `geography`, never two floats.** Only geography gives metre-accurate
distance on a spheroid and a GIST index `ST_DWithin` can use. Note that
`ST_DWithin` is index-usable and `ST_Distance(...) < x` is not.

**Prices resolve per night: override → weekend → base.** Most specific wins. If
the order were reversed, a vendor's Diwali rate would be silently overwritten
by their generic weekend rule — on exactly the dates that matter most. Tax is
applied to the subtotal, not per night; the cleaning fee is once per stay, per
unit.

**Coordinates and addresses are withheld until a booking is confirmed.** The
pin is coarsened to ~1 km, deterministically — a randomly jittered pin moves on
every page load and averages back to the true location over repeated samples.

**Vendor scoping is enforced three times**: the route checks the permission, the
repository scopes its query by vendor id, and the aggregate re-asserts
ownership. Another vendor's property is a **404**, never a 403 — a 403 confirms
the id exists and lets a competitor enumerate inventory.

**A vendor cannot block a booked date or reduce units below what is booked.**
Either would silently invalidate a confirmed reservation the guest would only
discover at the door. Both refuse with the offending date.

**Overbooking is prevented by a `CHECK (units_booked <= units_total)`**, not by
application code. A check-then-act race always has a window; the database has
none.

### Testing

104 unit tests covering the pricing engine, the sparse-availability rules and
the aggregate lifecycle — all with no database.

---

## Bookings

`src/app/modules/booking/` — reservation holds, confirmation, cancellation,
refunds, invoices and the status machine.

### Endpoints

| | |
| --- | --- |
| `POST /bookings` | reserve (takes the hold) — **requires `Idempotency-Key`** |
| `GET /bookings` · `/{id-or-reference}` | history and detail |
| `GET /bookings/{id}/refund-preview` · `POST /{id}/cancel` | cancellation |
| `GET /bookings/{id}/invoice` | GST invoice |
| `GET /vendor/bookings` · `POST /{id}/approve` · `/reject` · `/cancel` | vendor |

### The decisions that matter

**Overbooking is prevented by a database constraint, not by application code —
and there is deliberately no availability check before the hold.** "Check, then
write" is a check-then-act race: two guests read "1 room left" in the same
millisecond and both write, and no amount of care closes a window that exists
*between* two statements. So the write itself is the check. One statement claims
every night of the stay; `CHECK (units_booked <= units_total)` rejects the whole
thing if any night would go over, and Postgres aborts the transaction — a stay
is held entirely or not at all. Availability is read only to *explain* a
refusal.

**The nights are claimed in date order.** Two bookings over overlapping dates
take the same row locks; without a consistent order they deadlock and Postgres
kills one at random. `ORDER BY d.day` makes them queue instead.

**A hold is a real reservation.** `pending_payment` and `pending_approval` both
occupy inventory — a guest entering their card details must not lose the room.
The cost is that abandoned checkouts sit on inventory, so the window is 15
minutes and the expiry job runs every minute on the critical queue. If that job
stops, inventory leaks silently and properties go dark on their busiest dates
with no error anywhere.

**The booking row and its inventory are written in one transaction.** Separate
transactions would leave either a booking with no room or a room held by
nobody — and the second is invisible until a vendor complains their calendar is
wrong.

**Prices are re-computed server-side and a change is a 409, never a silent
reprice.** Charging a different amount from the one the guest agreed to is a
chargeback and, in most jurisdictions, illegal.

**Refunds are computed from the charges recorded on the booking**, never from
today's rates. A guest who paid ₹47,000 is refunded against ₹47,000 even if the
vendor has since doubled their price. Components refund differently: the
cleaning fee comes back in full (nothing was cleaned), and tax is reversed *in
proportion* to what is actually refunded — returning all the tax on a
half-refunded booking means remitting tax that was correctly collected.

**Who cancels changes everything.** A vendor cancelling on a guest refunds in
full regardless of policy: the guest is about to have their trip disrupted and
will rebook at today's higher prices. Applying the policy there would have
vendors dumping low-rate bookings whenever demand rose.

**The gateway is never called inside the cancellation transaction.** That would
hold a database transaction open across a third-party network call, and a
gateway success with a failed commit would refund a booking that is still
confirmed. The refund goes through the outbox with an idempotency key derived
from the booking id.

**Invoice numbers are gapless, and deliberately not a Postgres `SEQUENCE`.**
Sequences are non-transactional: every rollback burns a number. Indian GST
requires consecutive numbering and a gap must be explained to an auditor. A
counter row under `SELECT … FOR UPDATE` gives up concurrency — invoice creation
serialises per financial year — for a guarantee that matters more.

**Booking references are random, not sequential.** A sequential reference tells
a competitor the platform's daily volume and lets anyone enumerate other
people's bookings. The alphabet also excludes `0/O`, `1/I/L`, `5/S` and `8/B`,
because guests read these out to support agents.

**Modules talk through a published contract.** Booking needs property data and
inventory, so it would be trivially easy to import `property.domain.entities`
and depend on that aggregate's shape. Instead `app.modules.property.public`
exposes flat read models and an `InventoryService` protocol, and an
`.importlinter` contract makes that a rule rather than an intention.

### Testing

93 unit tests, no database — the refund ladder, the status machine, hold expiry
and the money invariants. `refund + retained == paid` is asserted across every
policy at eight different cancellation times.

---

## Payments

`src/app/modules/payment/` — Razorpay orders, checkout verification, webhooks,
refunds, retries and the transaction ledger.

### Endpoints

| | |
| --- | --- |
| `POST /payments/orders` | open checkout for a booking |
| `POST /payments/verify` | verify the browser callback |
| `POST /payments/retry` | check whether a failed payment may be retried |
| `GET /payments` · `/{id}` | transaction history and detail with the full ledger |
| `POST /admin/payments/{id}/refund` · `GET /{id}` | support |
| `POST /webhooks/razorpay` | the authoritative payment path (unlisted, unauthenticated, rate-limit exempt) |

### The decisions that matter

**The webhook is the authority; the browser callback is a convenience.** A
client-reported "I paid" is a claim. Both paths are idempotent and share one
state-application function, so whichever arrives first wins and the other is a
no-op — two implementations would eventually disagree about what "captured"
means.

**The signature is verified over the raw request bytes, before anything is
parsed.** `json.dumps(await request.json())` round-trips to different bytes —
key order, whitespace, unicode escaping — so the HMAC never matches, and the
tempting fix is to stop verifying. Two secrets, deliberately separate:
`KEY_SECRET` signs `order_id|payment_id` on the checkout callback,
`WEBHOOK_SECRET` signs the webhook body. A leaked webhook secret must not
authenticate API calls. Comparison is constant-time.

**A signature alone is not enough — the amount is checked too.** The signature
proves Razorpay issued that order/payment pair; it does not prove the pair is
worth what the booking costs. Without the amount check a client could replay a
genuine ₹1 payment from another order it also owns. Exactly the expected amount,
not "at least": an overpayment is a bug or a tampered order.

**The webhook answers 200 for duplicates, unknown event types and business
conditions it has already recorded.** Razorpay redelivers on any non-2xx, so a
handler that errors on normal traffic buries the real failures under retries.
It is also exempt from rate limiting — a throttled webhook makes the gateway
retry and eventually give up on a real payment.

**Delivery is at-least-once, and three independent things make the effect
exactly-once**: the delivery is claimed by `INSERT … ON CONFLICT DO NOTHING` on
the event id (atomic — two workers receiving the same redelivery cannot both
proceed), payment status only moves forward, and refunds are keyed. Webhooks
routinely arrive out of order; `payment.captured` before `payment.authorized` is
normal, and the stale event is ignored rather than applied or rejected.

**Double refunds are guarded three times over**, because a double refund is
unrecoverable in practice: the aggregate returns the existing attempt for a
known key, `UNIQUE (payment_id, idempotency_key)` stops a second row, and the
same key goes to Razorpay as `X-Razorpay-Idempotency-Key` so even a refund we
never managed to record is not issued twice. The key is derived from the
booking id, so a retried task and an impatient support agent collide.

**The refund attempt is written before the gateway is called.** A process that
dies in between leaves something to retry; the reverse order leaves money gone
with nothing pointing at it.

**The ledger is append-only, and `net_position` is `sum(ledger)`.** Every
movement is a row — the charge, each refund, Razorpay's fee, the tax on that
fee, a chargeback — never updated, never deleted. A maintained column drifts
from the entries it claims to summarise; a sum cannot. A `CHECK` enforces the
sign convention, because a `SUM()` that is silently wrong surfaces at month end
in a report nobody can balance. The gateway's fee and tax are recorded even
though the guest never paid them: a reconciliation that ignores them never
balances against the settlement report.

**No card data is stored, ever** — only Razorpay's opaque ids, the method, and a
last-4 or VPA for recognition. A PAN, even encrypted, changes the PCI-DSS
compliance burden entirely.

**Retrying a payment always creates a new order.** Razorpay orders are not
designed to be paid twice: reusing one produces confusing dashboard state and,
on some methods, a duplicate charge. Retries only work while the booking's hold
is alive, since paying after it lapses produces a booking with no inventory.

**`reconcile_payments` is the safety net that matters most.** Webhooks are
delivered at least once, which occasionally means never — a misconfigured
endpoint, an outage, a deploy that returned 502 for five minutes. Without it, a
guest who paid sits with an unconfirmed booking until they contact support.

**Payment confirms bookings through `booking.public`, which calls booking's own
`ConfirmBookingUseCase`** — never an `UPDATE`. A shortcut that set
`status='confirmed'` would skip the invoice number, the confirmation event and
the hold re-check. The dependency runs one way: booking emits
`booking.refund.requested` and payment executes the gateway call, so booking
never learns what a gateway is.


## Status

**Phase 4 — project setup**: complete. Configuration, logging, DI, middleware,
exception handling, database layer, health checks, Docker, migrations, CI.

**Phase 5 — authentication**: complete. Migration `0002_auth`, RBAC catalogue.

**Phase 6 — properties**: complete. Migration `0003_property`, PostGIS search,
sparse inventory, pricing and the vendor calendar.

**Phase 7 — booking engine**: complete. Migration `0004_booking`, atomic holds,
the refund engine, gapless invoicing, and `property.public` — the first
published inter-module contract.

**Phase 8 — payments**: complete. Migration `0005_payment`, Razorpay
integration, signature verification, the webhook dedupe store, the append-only
ledger, and `booking.public` — the second published inter-module contract.
`app.events.dispatch` also lands here: the consumer end of the outbox relay,
with one routing table of `event_type -> task`.

**Phase 9 — customer website**: complete. See `../frontend`. Running the web app
against a live server found four bugs that every prior phase's tests had missed,
all of them in the HTTP boundary rather than the logic beneath it:

* `vars()` on a `@dataclass(slots=True)` raises — and every router mapped its
  responses that way, so **no response-returning endpoint had ever worked**.
  Earlier phases verified use cases directly against Postgres and never went
  through a router. Fixed with `core/serialization.dto_dict`.
* `_DOMAIN_STATUS` was keyed by exact type, so every module-specific domain
  error fell through to 409 — including the two that documented themselves as
  404 precisely so the endpoint would not be an enumeration oracle, and the
  gateway error that documented itself as a retryable 503. The lookup now walks
  the MRO and honours an explicitly declared `status_code`.
* `PropertyResponse` was built by splatting a shallow dict, leaving nested
  images and room types as dataclasses that Pydantic could not coerce; property
  detail 500'd. Nested views are now mapped explicitly.
* `StaleDataError` reached the catch-all and answered 500 rather than 409, on
  every optimistically-locked aggregate.

**Phase 10 — Flutter app**: complete. See `../mobile`. Running it against a
live server found a denial of service in this API: `sort`, `property_type` and
`cancellation` were taken as `str` and converted to enums *inside* the search
handler, so an unrecognised value raised a `ValueError` that escaped to the ASGI
layer — where **no response is ever written**. The client hung until it timed
out, and repeated requests wedged the worker. It was reachable by anyone with a
URL, and both of our own clients were triggering it: they sent `sort=rating`,
which this API spells `rating_desc`. The parameters are now typed on the
signature, so FastAPI answers 422 before the handler runs; see
`tests/unit/test_search_query_validation.py`.

**Phase 11 — admin panel**: complete. See `../admin`. Four new modules —
`vendor`, `coupon`, `support`, `notification` — plus an `admin` module of
cross-module read projections and analytics. Migration `0006_admin`.

The `admin` module is the one deliberate exception to the module boundaries: it
reads across every module in raw SQL against a **read replica**, because a user
row joins bookings and payments and doing that through four repositories is
either a boundary violation or an N+1 per row. What it must not do is *write* —
every admin action calls the owning module's use case, so that module's
invariants, events and audit trail still run. It owns no domain and no
repositories, which the import contracts enforce.

**Phase 12 — reviews and the vendor portal**: complete. See `../vendor`. A
`review` module (migration `0007_review`), vendor reporting endpoints, and
`auth.public` — the third published inter-module contract. Running the portal
against a live server found four bugs, three of them serious:

* **No vendor could use any vendor endpoint.** Registration created the
  `vendors` row and stopped: `users.vendor_id` and the `vendor` role — which
  every vendor endpoint authorises against — were never written. A host could
  apply, be approved, and still get `404 VENDOR_NOT_FOUND` from their own
  dashboard forever. Fixed by publishing `auth.public.VendorAccess`, granting
  inside the registration transaction, and backfilling in migration
  `0008_vendor_link`.
* **No property could ever be published.** `geoalchemy2.to_shape` needs
  Shapely, which was not installed, and the decode was wrapped in
  `except Exception` — so every property on the platform decoded to *no
  coordinates* and the publish checklist reported `map_location` missing for
  all of them. Nothing failed loudly: map search runs through raw PostGIS and
  kept working, so it read as a product rule rather than a missing package.
  Shapely is now a declared dependency and the except clause is narrow enough
  to let an `ImportError` through. See
  `tests/unit/property/test_geometry_decode.py`.
* **Every rating decrease and removal returned 409.** Postgres evaluates CHECK
  constraints against the row *proposed* for insertion, before it arbitrates
  `ON CONFLICT` — so the rating upsert's bare `-1` tripped
  `ck_rating_summaries_count_non_negative` from a branch that is never taken.
  The `GREATEST` in the `DO UPDATE` clause cannot save it; the one in `VALUES`
  is what fixes it. See `tests/integration/test_rating_aggregate.py`.
* `/vendor/dashboard` 500'd on response validation: `reviews_awaiting` was
  selected in SQL and dropped from the returned dict. `VendorQueries` now
  returns typed rows rather than `dict[str, Any]`, which turned that class of
  mistake from a runtime 500 into a mypy error — and immediately located every
  call site.

Two smaller things came out of the same run. The integrity-error handler logged
`constraint=None` and nothing else, which is useless for the unnamed violations
(a CHECK, a NOT NULL) — it now logs the driver's message beside it, log-only.
And `admin/reviews/{id}/moderate` takes `{remove, reason}`, not an action verb;
removal requires a reason at the database level as well as in the domain.

The `review` module deliberately does *not* let a flag hide a review or stop it
counting: a listing that could suppress criticism by objecting to it is a
listing whose rating means nothing. Removal is a staff decision, needs a
recorded reason, and is reversible.

**Phase 13 — AI features**: complete. An `ai` module (migration `0009_ai`) with
recommendations, itineraries, a chat assistant, review sentiment and image
tagging.

The design decision that shapes the whole module: **the model explains, it does
not decide.** Ranking is arithmetic in `ai/domain/ranking.py` — Bayesian
shrinkage on ratings, log-scaled co-booking, geography — and the language model
writes the sentence underneath. Three reasons, and the third is why it survives
review: a model-produced ranking cannot be reproduced or audited; a model that
reads vendor-written descriptions to rank them can be ranked *by* them; and it
fails closed, so a provider outage costs the explanatory copy rather than the
page. Every AI feature has a path that works with the model switched off, and
`AI__ENABLED` defaults to false.

The security boundary is `ai/domain/grounding.py`. The model never emits an
identifier — it is handed a numbered candidate list and may only return those
numbers, and anything not on the list it was given is dropped and logged. A
hallucinated `P17` when eight candidates were offered is a dropped line, not a
wrong booking. Untrusted spans — review bodies, chat messages, house rules —
are fenced and stripped, but that is mitigation: the load-bearing defence is
that the assistant has no tools, cannot quote a price, and cannot act.

Running it against a stub that speaks the Messages API found a bug that had
nothing to do with AI and everything to do with every background job on the
platform:

* **Every Celery task failed after its first run in each worker process.**
  Tasks are async functions behind sync entry points and every one of them
  bridged with `asyncio.run`, which closes its loop on return — while the
  process-global container holds an engine whose pool holds asyncpg connections
  bound to that loop. Task one succeeded and closed the loop its connections
  lived on; task two failed with `Event loop is closed`. A prefork worker runs
  many tasks per process, so in production this reads as refunds stopping,
  holds never expiring and leaking the inventory they reserve, payments never
  reconciling, and the outbox relay — which delivers every event — going quiet,
  each after exactly one task, each fixed for exactly one more by a restart.
  Reproduced with the booking expiry task before any AI code was involved.
  Fixed by `infrastructure/queue/async_bridge.run_async`, one persistent loop
  per worker process; `tests/unit/test_async_bridge.py` includes a check that
  no task module reintroduces `asyncio.run`.

Two smaller things came out of the same session. The fence-lookalike pattern
matched the opening delimiter's shape but not the closing one, so untrusted
content could terminate its own fence and have everything after it read as
prompt — caught by `test_content_cannot_close_its_own_fence`. And "more like
this" returned an empty rail for any listing nobody had booked in a price band
nothing else in the city occupied; it now falls back to the city, labelled
`nearby` rather than `similar`, because those are different claims.

There is no vector index and no pretence of one — pgvector is not installed, and
the signals used (co-booking, attribute overlap, geography) are ones this schema
already indexes and a host can be told the truth about. `CandidateSource` is the
seam to reimplement when there is enough behavioural data to warrant embeddings.

**Wishlist** (migration `0010_wishlist`): one table, four endpoints, plus a
`merge` that adopts a signed-out device's list at sign-in. The design decision
is what is *not* stored — no price, no rating, no image. Those are read live
through `property/public`'s new batch `cards()` call, because a wishlist
quoting the price from the month it was saved misleads someone into clicking.
The one stored display field, `name_snapshot`, is a tombstone: rendered only
when the listing is gone, so a guest sees what they lost rather than a list
that quietly got shorter.

**Phase 14 — production**: `deploy/` holds the whole topology — compose, nginx
with TLS and rate limiting, Prometheus/Alertmanager/Grafana/Loki, hourly
verified backups, and a deployment guide. See `deploy/README.md`.

Building it found three configuration bugs, all of which would have stopped the
container starting on the first deploy and none of which are visible by reading
either file alone. All three were found the same way — constructing the real
`Settings` class from the compose file's environment:

* `CORS_ORIGINS=a,b` — pydantic-settings parses a `list[str]` from the
  environment as JSON, so the comma-separated form every deployment guide shows
  raised inside the environment source, before any validator, and exited naming
  only the section. Both forms are accepted now (`NoDecode` plus a `before`
  validator).
* `DATABASE__REPLICA_DSN: ${...:-}` — an unset compose variable arrives as
  `""`, not as absent, and `PostgresDsn | None` rejects it. Blank now means
  "no replica", which is the configuration most likely to leave it unset.
* `HTTP__ALLOWED_HOSTS` was never set, and the production safety validator
  correctly refuses a wildcard. The compose supplies it now.

`tests/unit/test_deployment_config.py` pins all three.

Each new module follows the same layout: its own domain, use cases, repositories
and router; mount it in `interface/api/v1/router.py`, add `.importlinter` layers
and domain-purity contracts, and expose a `public/` contract if another module
needs it.
