# 1. A modular monolith, with the boundaries enforced

**Status:** Accepted · **Date:** 2026-08-06

## Context

This is a two-sided travel marketplace: guests, hosts, staff, payments,
inventory, search, reviews, support. Thirteen bounded contexts on the current
count. The obvious modern answer is a service per context.

The obvious answer is wrong for this system, for reasons that are about *this*
domain rather than about microservices in general.

**Booking is one transaction.** Reserving a stay decrements inventory for every
night in a range, records a hold, writes an outbox event and must be atomic
across all of it. In one database that is a transaction with an exclusion
constraint doing the hard part. Across services it is a saga with compensating
actions, and the failure mode is a room held by nobody or sold twice — which is
the single worst thing this system can do.

**Nobody is on call.** A distributed system is a distributed *operations*
commitment: tracing, per-service dashboards, version skew between services,
a deployment order. That cost is paid every week, forever, by a team that does
not exist yet.

## Decision

One deployable, thirteen modules, and **the boundaries enforced by a tool
rather than by discipline**.

Each module owns `domain / application / infrastructure / interface`, may only
depend inward, and may only reach another module through that module's
published `public/` contract. Thirty-one contracts in `.importlinter` say so,
and CI fails when one is broken.

The enforcement is the decision. A modular monolith without it is just a
monolith with good intentions, and good intentions lose to a deadline.

## Consequences

**Good.** Booking stays transactional. One repository, one deploy, one place to
look. Refactoring across a boundary is a compiler-and-linter problem rather than
an API-versioning problem. The module graph is a real map of the domain.

**Bad.** The whole thing scales as one unit — search traffic and payment traffic
share a process. There is no language choice per module. A slow test suite is
everyone's slow test suite.

**The exit, if it is ever needed.** The contracts are what make extraction
tractable: a module that only talks through `public/` and publishes events
already has its seam cut. Search would go first — it is read-only, it has the
most divergent scaling profile, and it already reads from a replica DSN.

## What would change this

Sustained load where one module's traffic profile genuinely conflicts with
another's, *and* a team large enough to own a service each. Not before both.
