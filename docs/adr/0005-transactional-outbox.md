# 5. Events go through a transactional outbox

**Status:** Accepted · **Date:** 2026-08-06

## Context

A cancellation has to do two things: change the booking's state, and cause a
refund. They cannot both be in one transaction — the refund is an HTTP call to
Razorpay — and the order you attempt them in decides which way it breaks.

Call the gateway first and a database failure afterwards means money refunded
for a booking still marked confirmed. Commit first and publish afterwards means
a crash between the two loses the refund entirely, with no record that it was
owed.

Redis is the broker, and Redis is not durable. A publish that succeeds can still
be lost to a restart.

## Decision

**The event is committed to Postgres in the same transaction as the state
change, and a relay publishes it afterwards.**

```
BEGIN
  UPDATE bookings SET status = 'cancelled' …
  INSERT INTO outbox (event_type, payload, …)
COMMIT
                                    ↓  relay, every 2s
                              Celery → consumer
```

The relay claims a batch `FOR UPDATE SKIP LOCKED`, publishes, then marks the
rows processed. If it dies between publishing and marking, the event is
delivered twice — so **every consumer is idempotent**, keyed on something
derived rather than generated: the refund uses `refund-{booking_id}`, the
notification worker uses `{template}:{event_id}`.

Redis is the *transport*. Postgres is the record.

## Consequences

**Good.** No event is ever lost, including across a broker restart. The state
change and the intent to act on it are atomic. The outbox is a queryable audit
trail of everything the system decided to do.

**Bad.** At-least-once, not exactly-once — so idempotency is not optional in a
consumer, it is the contract. A consumer that forgets is a double refund.

**Bad.** Latency is the relay interval, not zero. Two seconds, chosen so a
confirmation feels immediate while a slow batch cannot overlap its own next run.

**Bad, and learned the hard way.** The relay is a single point of starvation.
It had no scheduler entry for the whole early life of this project, so every
event committed correctly and was never delivered — and an undrained outbox
produces no errors at all. `test_task_registry.py` now asserts the schedule
exists, because nothing else would notice.

## What would change this

Postgres logical replication into a CDC pipeline (Debezium) removes the relay,
at the cost of an operational component considerably larger than the relay.
Worth it at a volume this system is nowhere near.
