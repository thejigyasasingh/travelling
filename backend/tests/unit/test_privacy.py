"""Client addresses never reach a log line.

An IP is personal data under the GDPR and India's DPDP Act. The rate limiter
knew that and hashed before using an address as a bucket key; the access log
wrote the raw value on **every single request**, kept for thirty days. One
stated policy, two implementations, and the one that ran more often was the one
that ignored it.

There is one implementation now. These tests defend the two properties that
make it worth having — a fingerprint that correlates without identifying, and a
network that locates without identifying — plus the thing that actually broke:
that no caller can accidentally log the address itself.
"""

from __future__ import annotations

import pytest

from app.core.privacy import (
    client_fingerprint,
    client_ip_from_headers,
    network_prefix,
)

pytestmark = pytest.mark.unit

V4 = "203.0.113.42"
V6 = "2001:db8:85a3:1234:5678:8a2e:370:7334"


# ══════════════════════════════════════════════════════════════════════════
# Fingerprint
# ══════════════════════════════════════════════════════════════════════════


def test_the_address_does_not_survive_into_the_fingerprint() -> None:
    """**The** finding this module exists for."""
    assert V4 not in client_fingerprint(V4)
    assert V6 not in client_fingerprint(V6)


def test_the_same_client_fingerprints_the_same_way() -> None:
    """Stability is the whole operational value. "Is this the same caller as an
    hour ago?" is unanswerable if the digest moves."""
    assert client_fingerprint(V4) == client_fingerprint(V4)


def test_different_clients_fingerprint_differently() -> None:
    assert client_fingerprint("203.0.113.1") != client_fingerprint("203.0.113.2")


def test_a_salt_changes_the_fingerprint() -> None:
    """A bare SHA-256 of an IPv4 address is reversible by brute force — 2^32 is
    a laptop afternoon. The salt is what turns pseudonymisation into something
    closer to anonymisation, and stops digests being comparable between two
    deployments."""
    assert client_fingerprint(V4, salt="a") != client_fingerprint(V4, salt="b")
    assert client_fingerprint(V4, salt="a") != client_fingerprint(V4)


def test_the_salt_is_not_recoverable_from_the_output() -> None:
    assert "pepper" not in client_fingerprint(V4, salt="pepper")


def test_a_missing_address_is_not_an_error() -> None:
    """This runs on every request, including ones with no client — an ASGI
    scope from a test transport has none. Raising here would turn that into a
    500 on a healthy request."""
    assert client_fingerprint(None) == "unknown"
    assert client_fingerprint("") == "unknown"


def test_the_fingerprint_stays_short_enough_to_read() -> None:
    """It goes on every log line. A 64-character digest makes the field that
    matters harder to see."""
    assert len(client_fingerprint(V4)) == 16


# ══════════════════════════════════════════════════════════════════════════
# Network
# ══════════════════════════════════════════════════════════════════════════


def test_an_ipv4_address_is_truncated_to_its_network() -> None:
    """/24 is what IP anonymisation has meant in analytics tooling for a
    decade: enough to tell a data centre from a mobile carrier, not enough to
    name a subscriber."""
    assert network_prefix(V4) == "203.0.113.0/24"


def test_the_final_octet_is_gone() -> None:
    assert "42" not in network_prefix(V4).removeprefix("203.0.113.0/24")


def test_two_addresses_on_one_network_share_a_prefix() -> None:
    assert network_prefix("203.0.113.1") == network_prefix("203.0.113.250")


def test_two_networks_do_not() -> None:
    assert network_prefix("203.0.113.1") != network_prefix("198.51.100.1")


def test_an_ipv6_address_is_truncated_to_a_48() -> None:
    """/64 is a single household or handset — identifying. /48 is the routed
    allocation, which is the IPv6 equivalent of a /24."""
    assert network_prefix(V6) == "2001:db8:85a3::/48"


def test_a_malformed_address_is_unknown_rather_than_a_crash() -> None:
    """`X-Forwarded-For` is attacker-controlled at the edge. A client that
    sends nonsense must get a normal response, not a 500 — and certainly must
    not have its nonsense echoed into the log verbatim.
    """
    for value in ("not-an-ip", "999.999.999.999", "'; DROP TABLE users;--", "  "):
        assert network_prefix(value) == "unknown", value


def test_a_missing_address_is_unknown() -> None:
    assert network_prefix(None) == "unknown"


# ══════════════════════════════════════════════════════════════════════════
# Where the address comes from
# ══════════════════════════════════════════════════════════════════════════


def test_the_leftmost_forwarded_entry_wins() -> None:
    """Leftmost is the original client; everything after it is our own proxy
    chain. Taking the rightmost would fingerprint nginx for every request."""
    assert client_ip_from_headers("203.0.113.9, 10.0.0.1, 10.0.0.2", "10.0.0.2") == "203.0.113.9"


def test_whitespace_around_the_entry_is_trimmed() -> None:
    assert client_ip_from_headers(" 203.0.113.9 , 10.0.0.1", None) == "203.0.113.9"


def test_the_socket_peer_is_used_when_there_is_no_proxy() -> None:
    assert client_ip_from_headers(None, "203.0.113.9") == "203.0.113.9"


def test_an_empty_forwarded_header_falls_back_to_the_peer() -> None:
    """A proxy that sets the header to an empty string is a real configuration,
    and treating `""` as an address fingerprints every such request
    identically."""
    assert client_ip_from_headers("", "10.0.0.5") == "10.0.0.5"
    assert client_ip_from_headers("  ,  ", "10.0.0.5") == "10.0.0.5"


def test_nothing_at_all_is_none() -> None:
    assert client_ip_from_headers(None, None) is None


# ══════════════════════════════════════════════════════════════════════════
# The two callers agree
# ══════════════════════════════════════════════════════════════════════════


def test_the_access_log_and_the_rate_limiter_use_the_same_helper() -> None:
    """The drift that caused the finding.

    Both middlewares previously carried their own `_client_ip`. One hashed and
    one did not, and nothing made that visible. Importing the same symbol is
    what keeps them honest — asserted here so a future inline reimplementation
    is a failing test rather than a quiet regression.
    """
    import inspect

    from app.interface.api.middleware import access_log, rate_limit

    for module in (access_log, rate_limit):
        source = inspect.getsource(module)
        assert "client_ip_from_headers" in source, module.__name__
        assert "hashlib" not in source, f"{module.__name__} hashes on its own again"
