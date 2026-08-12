# 2. Money is an integer count of minor units

**Status:** Accepted · **Date:** 2026-08-06

## Context

Every price, fee, tax, commission and refund in the system is a quantity of
money that must survive arithmetic, a database round trip, JSON, three
TypeScript clients and a Dart one, and still agree with what a payment gateway
charged.

`float` is disqualified on the first line: `0.1 + 0.2` is not `0.3`, and a
booking total assembled from a nightly rate, a cleaning fee, a slabbed tax and
a commission accumulates error that shows up as a one-paisa mismatch against
Razorpay's settlement report — which finance then has to reconcile by hand,
monthly, forever.

`Decimal` is correct in Python and does not survive the trip. JSON has no
decimal type; `json.dumps(Decimal("1.10"))` raises, and the usual fix — encode
as a string, parse in the client — puts a `Number` in JavaScript at the far end
anyway.

## Decision

**Integers, in the currency's minor unit, all the way through.** ₹4,500.00 is
`450000`. The field is named `*_minor` wherever it appears — column, DTO,
TypeScript interface, Dart model — so a value with the wrong scale is visible
at the call site rather than three layers away.

Commission is basis points (`commission_bps`), for the same reason: 12% is
`1200`, and a percentage stored as a float reintroduces exactly the problem
integers were chosen to avoid.

Formatting to "₹4,500" happens once, at the edge, in the presentation layer of
each client.

## Consequences

**Good.** Arithmetic is exact. Postgres `bigint`, JSON number, TypeScript
`number` and Dart `int` all hold it losslessly — there is no encoding decision
at any boundary. Comparing our total to the gateway's is `==`.

**Bad.** Every developer must remember the scale. `450000` reads as four hundred
and fifty thousand rupees to anyone who has not internalised the convention,
which is why the `_minor` suffix is not optional. A currency with three minor
digits (Kuwaiti dinar) or none (Japanese yen) needs the exponent consulted
rather than a hardcoded 100 — `Money` carries its currency for that reason.

**Bad, and accepted.** JavaScript's `Number` is exact only to 2^53. That is
₹90 trillion in paise; the constraint is real and not reachable here.

## What would change this

A currency requiring more precision than its minor unit — a fractional-paisa
fee schedule, say. That would mean a scaled integer with an explicit exponent,
not a float.
