# 6. Refresh tokens rotate, and reuse revokes the family

**Status:** Accepted · **Date:** 2026-08-06

## Context

Access tokens are short-lived JWTs, verified by signature with no database
round trip. That is what makes them cheap, and it is also why they cannot be
revoked — a stolen access token is valid until it expires.

The refresh token is the long-lived credential, and on a phone there is no
HttpOnly cookie to hide it in. If one leaks, the attacker has an account for as
long as the token lives, and nothing in a stateless design notices.

## Decision

**Every refresh issues a new refresh token and invalidates the one presented.**
Tokens are chained into a *family* rooted at the original sign-in.

Presenting a token that has already been used is, by construction, either a
replay or a theft: the legitimate client would be holding the newer one. So
reuse **revokes the entire family** — every device in that sign-in chain is
signed out, and the user is told why.

Two consequences fall out of that, and both are load-bearing:

**Refresh must be single-flight in every client.** A screen firing eight
requests that all 401 together would present the same refresh token eight
times, and seven of those look exactly like theft. So the customer site, the
admin panel, the vendor portal and the Flutter app each implement single-flight
refresh, and each has a test that asserts *how many times* refresh was called
rather than whether it succeeded.

**A little clock skew is expected.** The mobile client refreshes thirty seconds
before expiry rather than after a 401, so a request in flight during the
turnover still succeeds.

## Consequences

**Good.** A stolen refresh token is useful once, and using it locks the thief
and the victim out together — which is loud, and recoverable, rather than
silent. Sign-out is real: revoking the family ends every session.

**Bad.** A client that gets refresh wrong signs its users out constantly, and
the bug only appears under concurrency. That is the single most delicate piece
of client code in the project, in four languages, and it is why each copy has
its own test rather than a shared one — a shared test would pass while one copy
diverged.

**Bad.** Family state lives in the database, so refresh is not stateless. It is
one indexed lookup on a path that runs once every fifteen minutes per user.

## What would change this

Nothing foreseeable. The alternative — long-lived, non-rotating refresh
tokens — trades a detectable compromise for an undetectable one.
