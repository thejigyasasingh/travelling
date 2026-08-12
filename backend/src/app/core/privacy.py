"""Turning a client address into something safe to keep.

An IP address is personal data under both the GDPR and India's DPDP Act. The
rate limiter already treated it that way — it hashes before using an address as
a bucket key — while the access log wrote it in clear on **every single
request**, at thirty days' retention. One policy, two implementations, and the
one that ran more often was the one that ignored it.

So there is exactly one implementation now, and both callers use it.

What is kept, and why each part earns its place:

* **A stable fingerprint.** "Is one client hammering us?" and "is this the same
  caller as an hour ago?" are the questions an address actually gets asked in
  an incident. A hash answers both without naming anyone.
* **A network prefix.** /24 for IPv4, /48 for IPv6 — enough to tell a data
  centre from a mobile carrier, or one region from another, which is the other
  thing addresses get used for. Truncating to a /24 is what IP anonymisation
  has meant in analytics tooling for a decade.

What is deliberately *not* kept: the address itself. If an abuse investigation
genuinely needs one, that is a decision to make on purpose with its own
retention and access rules — not a side effect of leaving it in a log line.

**On salting.** SHA-256 of an IPv4 address is pseudonymisation, not
anonymisation: the whole space is 2^32 and a rainbow table over it is a laptop
afternoon. A salt makes the digest useless without it, and makes hashes from
two different deployments non-comparable. It is optional because a deployment
that has not set one is still strictly better off than logging the raw value —
but it is worth setting, and the deployment templates set it.
"""

from __future__ import annotations

import hashlib
import ipaddress
from typing import Final

#: Short enough to keep log lines readable, long enough that collisions between
#: two clients in one retention window are not a practical concern.
_DIGEST_CHARS: Final = 16

UNKNOWN: Final = "unknown"


def client_fingerprint(ip: str | None, *, salt: str = "") -> str:
    """A stable, non-reversible handle for one client.

    Stable across a retention window, so two log lines from the same caller can
    be correlated; not reversible to an address without the salt.
    """
    if not ip:
        return UNKNOWN
    digest = hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()
    return digest[:_DIGEST_CHARS]


def network_prefix(ip: str | None) -> str:
    """The address truncated to its network, or ``unknown``.

    /24 for IPv4 and /48 for IPv6 — the conventional anonymisation boundaries.
    Keeps "which network" answerable while dropping "which person".

    Malformed input returns ``unknown`` rather than raising: this runs on every
    request, including ones from a client that sent a nonsense
    ``X-Forwarded-For``, and an exception here would turn a bad header into a
    500.
    """
    if not ip:
        return UNKNOWN
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return UNKNOWN

    if isinstance(address, ipaddress.IPv4Address):
        return str(ipaddress.ip_network(f"{address}/24", strict=False))
    return str(ipaddress.ip_network(f"{address}/48", strict=False))


def client_ip_from_headers(forwarded: str | None, peer: str | None) -> str | None:
    """The originating address, given the proxy chain and the socket peer.

    ``X-Forwarded-For`` is trusted **only** because uvicorn runs behind our own
    nginx with ``--proxy-headers`` and a trusted-hosts list. Reading this header
    at an untrusted edge would let any client choose its own identity — and
    therefore reset its own rate limit at will.

    Leftmost is the original client; everything after it is our own proxies.
    """
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return peer or None
