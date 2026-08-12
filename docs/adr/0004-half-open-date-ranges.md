# 4. Stay dates are half-open ranges

**Status:** Accepted · **Date:** 2026-08-06

## Context

A stay from the 1st to the 3rd is two nights. Whether the 3rd is "in" the stay
depends on which of the two obvious conventions you picked, and the two
conventions disagree about whether a guest checking out on the 3rd conflicts
with one checking in on the 3rd. They do not conflict — that is the same day
with a cleaning window in between — but a closed-range overlap check says they
do, and the room goes unsold.

That bug is invisible in a unit test with one booking and appears the first
week two guests want consecutive stays.

## Decision

**`[check_in, check_out)` — half-open — everywhere.** Check-out is the morning
after the last night, and is not part of the stay.

The database enforces it rather than the application remembering it:

```sql
stay_range daterange GENERATED … ('[)')
EXCLUDE USING gist (room_type_id WITH =, stay_range WITH &&)
```

`&&` on two half-open `daterange`s gives exactly the right answer for
back-to-back stays, and the exclusion constraint means two concurrent bookings
cannot both win — Postgres rejects the second, no application-level lock
required.

The convention holds at every boundary: the API's `to_date` is exclusive, the
vendor calendar sends `to_date = last_night + 1`, and `nightsBetween` in each
client is a plain subtraction.

## Consequences

**Good.** Nights are `check_out - check_in`, with no off-by-one. Back-to-back
stays never conflict. Double-booking is impossible at the storage layer, under
concurrency, without a distributed lock.

**Bad.** It looks like a bug to anyone reading it for the first time — a
one-night stay sends a range two days wide, and the temptation to "fix" it is
strong. Every place this surfaces carries a comment saying so, and the vendor
calendar test asserts it explicitly for that reason.

**Bad.** A UI must never show the exclusive end date to a guest. "1–3 September"
means two nights to a person and would read as three.

## What would change this

Nothing. This is the convention Postgres, ISO 8601 intervals and every hotel
system already use; the alternative is worse in every direction.
