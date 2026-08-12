"""Every optional filter on the admin surface, actually exercised.

This file exists because of one bug and the gap that let it live.

``GET /admin/users?role=vendor`` returned a 500 for as long as the endpoint had
existed. The predicate joined ``roles r ON r.id = ur.role_id``; neither column
is real — the grant table stores ``role_name``, which is itself the foreign key
into ``roles(name)``. Python cannot catch that, ``mypy`` cannot catch that, and
the query is only assembled when someone passes the parameter. Nothing did.

The general shape of the hazard: **an optional filter is a separate SQL
statement that only exists when someone uses it.** A list endpoint tested
without parameters proves nothing about the endpoint with them. So the rule
here is one test per filter per endpoint, and the assertion is deliberately
weak — a 200 and a well-formed page.

Weak on purpose. Asserting *which rows* come back would need seeded data for
every combination and would break whenever an unrelated test added a row; these
tests would then be rewritten until they asserted nothing, which is where the
coverage went last time. What is worth pinning permanently is that the
statement parses and runs. Row-level correctness is asserted where the data is
controlled — see `test_portal_api.py`.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from .conftest import Actor

pytestmark = pytest.mark.integration


def page_of(response: Any) -> list[dict[str, Any]]:
    """Assert the standard admin paged envelope and hand back the rows.

    The count lives under `meta`, not at the top level — the admin surface uses
    offset paging with `{items, meta: {total, page, size, pages}}`, unlike the
    guest-facing lists which are cursor-paged and have no total at all.
    Asserting the envelope here means a schema change surfaces once rather than
    in every test below.
    """
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body["items"], list)
    assert body["meta"]["total"] >= 0
    assert body["meta"]["pages"] >= 0
    return list(body["items"])


# ══════════════════════════════════════════════════════════════════════════
# Each (endpoint, filter) pair the routers accept
# ══════════════════════════════════════════════════════════════════════════

#: Enumerated by reading the route signatures rather than generated, so that
#: adding a parameter without adding a case here is a visible omission in the
#: diff rather than a silently unchanged test count.
FILTERS: list[tuple[str, dict[str, Any]]] = [
    ("/api/v1/admin/users", {"q": "example"}),
    ("/api/v1/admin/users", {"status": "active"}),
    # The one that was broken.
    ("/api/v1/admin/users", {"role": "vendor"}),
    ("/api/v1/admin/users", {"page": 2, "size": 5}),
    ("/api/v1/admin/properties", {"q": "villa"}),
    ("/api/v1/admin/properties", {"status": "draft"}),
    ("/api/v1/admin/properties", {"vendor_id": str(uuid.uuid4())}),
    ("/api/v1/admin/bookings", {"q": "RW-26-AAAAAAAA"}),
    ("/api/v1/admin/bookings", {"status": "confirmed"}),
    ("/api/v1/admin/bookings", {"property_id": str(uuid.uuid4())}),
    ("/api/v1/admin/bookings", {"from_date": "2026-01-01", "to_date": "2026-12-31"}),
    ("/api/v1/admin/payments", {"q": "RW-26-AAAAAAAA"}),
    ("/api/v1/admin/payments", {"status": "captured"}),
    ("/api/v1/admin/vendors", {"q": "stays"}),
    ("/api/v1/admin/vendors", {"status": "approved"}),
]


@pytest.mark.parametrize(
    ("path", "params"),
    FILTERS,
    ids=[f"{p.rsplit('/', 1)[-1]}?{'&'.join(q)}" for p, q in FILTERS],
)
async def test_every_filter_produces_a_valid_query(
    api_client: Any, staff: Actor, path: str, params: dict[str, Any]
) -> None:
    """The statement assembles, parses and runs.

    A malformed predicate is a 500 here, which is exactly what happened in
    production for `?role=`.
    """
    page_of(await api_client.get(path, headers=staff.auth, params=params))


async def test_filters_combine(api_client: Any, staff: Actor) -> None:
    """Predicates are AND-ed into one WHERE clause, so a combination is a
    statement no single-filter test builds."""
    page_of(
        await api_client.get(
            "/api/v1/admin/users",
            headers=staff.auth,
            params={"q": "example", "status": "active", "role": "vendor", "size": 5},
        )
    )


# ══════════════════════════════════════════════════════════════════════════
# The role filter specifically — it is the one that was wrong
# ══════════════════════════════════════════════════════════════════════════


async def test_the_role_filter_finds_a_host(api_client: Any, staff: Actor, host: Actor) -> None:
    """Not just 200 — the right person.

    A predicate that is syntactically valid and semantically wrong (matching
    nothing, or everything) would pass the parametrised sweep above. `host`
    holds the `vendor` role, so they must be in the result.
    """
    rows = page_of(
        await api_client.get(
            "/api/v1/admin/users",
            headers=staff.auth,
            params={"q": host.email, "role": "vendor"},
        )
    )

    assert [r["email"] for r in rows] == [host.email]


async def test_the_role_filter_excludes_a_traveller(
    api_client: Any, staff: Actor, guest: Actor
) -> None:
    """The other half. Without this, a predicate that ignored `:role` entirely
    would still pass the test above."""
    rows = page_of(
        await api_client.get(
            "/api/v1/admin/users",
            headers=staff.auth,
            params={"q": guest.email, "role": "vendor"},
        )
    )

    assert rows == []


async def test_an_unfiltered_list_includes_the_traveller(
    api_client: Any, staff: Actor, guest: Actor
) -> None:
    """The control for the test above: the guest *is* findable, so their
    absence there is the role filter working rather than the search failing."""
    rows = page_of(
        await api_client.get("/api/v1/admin/users", headers=staff.auth, params={"q": guest.email})
    )

    assert [r["email"] for r in rows] == [guest.email]


async def test_an_unknown_role_returns_nothing_rather_than_erroring(
    api_client: Any, staff: Actor
) -> None:
    """`role` is free text on the wire. A value that is not a role is an empty
    result, not a 500 and not every user."""
    rows = page_of(
        await api_client.get("/api/v1/admin/users", headers=staff.auth, params={"role": "wizard"})
    )

    assert rows == []


# ══════════════════════════════════════════════════════════════════════════
# The endpoints no test called at all
# ══════════════════════════════════════════════════════════════════════════


async def test_the_analytics_endpoint_returns(api_client: Any, staff: Actor) -> None:
    """The heaviest aggregate in the system, and nothing proved it ran."""
    response = await api_client.get(
        "/api/v1/admin/analytics",
        headers=staff.auth,
        params={"from_date": "2026-01-01", "to_date": "2026-12-31"},
    )

    assert response.status_code == 200, response.text


async def test_the_payments_list_returns(api_client: Any, staff: Actor) -> None:
    page_of(await api_client.get("/api/v1/admin/payments", headers=staff.auth))


async def test_the_notifications_list_returns(api_client: Any, staff: Actor) -> None:
    page_of(await api_client.get("/api/v1/admin/notifications", headers=staff.auth))


@pytest.mark.parametrize(
    "path",
    ["/api/v1/admin/analytics", "/api/v1/admin/payments", "/api/v1/admin/notifications"],
)
async def test_the_untested_endpoints_are_also_closed_to_travellers(
    api_client: Any, guest: Actor, path: str
) -> None:
    """These three were never called by a test, so nothing had checked they
    were guarded either."""
    response = await api_client.get(path, headers=guest.auth)

    assert response.status_code == 403, response.text
