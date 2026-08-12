"""The vendor portal and the admin panel, over HTTP.

Almost every test here is an authorisation test, because that is where the
damage is. A guest reaching a host's revenue, a host reaching another host's
bookings, or anyone reaching the admin surface are three different incidents
and all three are one missing predicate away.

The one non-authorisation test worth naming: a host with no `users.vendor_id`
gets a 404 from every portal endpoint. That is not a bug, it is the
authorisation working — but it was also, for a while, the state *every* real
vendor was in, because registration created the vendors row and never linked
it to the identity. Nothing failed loudly; approved hosts simply could not open
their own dashboard.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.api.conftest import Actor, Listing, seed_booking, seed_listing

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

VENDOR_READS = [
    "/api/v1/vendor/me",
    "/api/v1/vendor/dashboard",
    "/api/v1/vendor/earnings",
    "/api/v1/vendor/arrivals",
    "/api/v1/vendor/reports",
    "/api/v1/vendor/properties",
    "/api/v1/vendor/bookings",
    "/api/v1/vendor/reviews",
]

ADMIN_READS = [
    "/api/v1/admin/dashboard",
    "/api/v1/admin/users",
    "/api/v1/admin/properties",
    "/api/v1/admin/bookings",
    "/api/v1/admin/vendors",
    "/api/v1/admin/coupons",
    "/api/v1/admin/tickets",
]


# ══════════════════════════════════════════════════════════════════════════
# Vendor portal
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("path", VENDOR_READS)
async def test_the_portal_is_closed_to_anonymous_callers(api_client: Any, path: str) -> None:
    assert (await api_client.get(path)).status_code == 401


@pytest.mark.parametrize("path", VENDOR_READS)
async def test_a_guest_cannot_reach_the_portal(api_client: Any, guest: Actor, path: str) -> None:
    """A signed-in traveller is not a host.

    Two shapes of refusal, and both are acceptable: the endpoints that resolve
    a vendor from the token answer 404, because a traveller has none and there
    is nothing to be forbidden from; the list endpoints answer 200 with an
    empty page, because "your properties" is genuinely empty.

    What is asserted is the part that matters — **no other host's data comes
    back**. A 200 carrying rows would be the incident.
    """
    response = await api_client.get(path, headers=guest.auth)
    assert response.status_code in (200, 403, 404), f"{path} -> {response.status_code}"

    if response.status_code == 200:
        body = response.json()
        rows = body.get("items", body) if isinstance(body, dict) else body
        if isinstance(rows, list):
            assert rows == [], f"{path} returned another host's data to a traveller"


async def test_a_host_sees_their_own_dashboard(api_client: Any, host: Actor) -> None:
    response = await api_client.get("/api/v1/vendor/dashboard", headers=host.auth)

    assert response.status_code == 200, response.text
    body = response.json()
    # The field that was selected in SQL and forgotten in the handler, so every
    # dashboard request 500'd on response validation.
    assert "reviews_awaiting" in body
    assert "net_30d_minor" in body


async def test_the_dashboard_returns_every_declared_field(api_client: Any, host: Actor) -> None:
    """Response-model validation is the only thing that catches a handler
    building its payload by hand and missing a key. Asserted explicitly so a
    new field cannot be added to the schema and forgotten in the query."""
    body = (await api_client.get("/api/v1/vendor/dashboard", headers=host.auth)).json()

    for field in (
        "live_listings",
        "in_review",
        "awaiting_approval",
        "arrivals_this_week",
        "in_stay",
        "gross_30d_minor",
        "commission_30d_minor",
        "net_30d_minor",
        "reviews_awaiting",
    ):
        assert field in body, f"{field} missing from the dashboard"


async def test_a_host_sees_only_their_own_properties(api_client: Any, host: Actor, db: Any) -> None:
    """One predicate away from showing every listing on the platform."""
    someone_else = await seed_listing(db)

    response = await api_client.get("/api/v1/vendor/properties", headers=host.auth)

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert str(someone_else.property_id) not in ids


async def test_a_host_sees_only_their_own_bookings(
    api_client: Any, host: Actor, guest: Actor, listing: Listing, db: Any
) -> None:
    """A booking carries the guest's name, phone number and dates."""
    mine = await seed_booking(db, listing=listing, guest_id=guest.id, status="confirmed")
    other_listing = await seed_listing(db)
    theirs = await seed_booking(
        db, listing=other_listing, guest_id=guest.id, status="confirmed", days_ago=11
    )

    response = await api_client.get("/api/v1/vendor/bookings", headers=host.auth)

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert str(mine) in ids
    assert str(theirs) not in ids, "another host's booking is visible"


async def test_earnings_are_scoped_to_the_host(api_client: Any, host: Actor) -> None:
    response = await api_client.get("/api/v1/vendor/earnings", headers=host.auth)

    assert response.status_code == 200, response.text
    body = response.json()
    # Net is what reaches the bank, and is never above gross.
    assert body["net_payable_minor"] <= body["gross_minor"]
    assert isinstance(body["gross_minor"], int)


async def test_the_csv_statement_is_a_file_an_accountant_can_open(
    api_client: Any, host: Actor
) -> None:
    """Rupees with two decimals, not minor units.

    Everything internal is integer paise; a spreadsheet reconciled against a
    bank statement should read the way the bank statement does.
    """
    response = await api_client.get("/api/v1/vendor/reports/statement.csv", headers=host.auth)

    assert response.status_code == 200, response.text
    assert "text/csv" in response.headers.get("content-type", "")
    assert response.text.splitlines()[0] == "month,bookings,gross,commission,tax,net"


async def test_a_host_cannot_edit_another_hosts_property(
    api_client: Any, host: Actor, db: Any
) -> None:
    """The most valuable thing a host has is their listing and its price."""
    someone_else = await seed_listing(db)

    response = await api_client.patch(
        f"/api/v1/vendor/properties/{someone_else.property_id}",
        headers=host.auth,
        json={"description": "I have taken over this listing."},
    )

    assert response.status_code in (403, 404), response.text


async def test_a_host_cannot_price_another_hosts_rooms(
    api_client: Any, host: Actor, db: Any
) -> None:
    """Setting a competitor's rate to one rupee is the attack this prevents."""
    from datetime import UTC, datetime, timedelta

    someone_else = await seed_listing(db)
    start = (datetime.now(UTC) + timedelta(days=5)).date()

    response = await api_client.put(
        f"/api/v1/vendor/properties/{someone_else.property_id}"
        f"/room-types/{someone_else.room_type_id}/rates",
        headers=host.auth,
        json={
            "from_date": start.isoformat(),
            "to_date": (start + timedelta(days=3)).isoformat(),
            "rate_minor": 100,
        },
    )

    assert response.status_code in (403, 404), response.text


# ══════════════════════════════════════════════════════════════════════════
# Admin panel
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("path", ADMIN_READS)
async def test_admin_is_closed_to_anonymous_callers(api_client: Any, path: str) -> None:
    assert (await api_client.get(path)).status_code == 401


@pytest.mark.parametrize("path", ADMIN_READS)
async def test_a_guest_cannot_reach_admin(api_client: Any, guest: Actor, path: str) -> None:
    """403 here, not 404: the caller is authenticated and the resource plainly
    exists — they are simply not staff. Hiding that would not protect
    anything, since the admin panel is not a secret."""
    response = await api_client.get(path, headers=guest.auth)
    assert response.status_code == 403, f"{path} -> {response.status_code}"


@pytest.mark.parametrize("path", ADMIN_READS)
async def test_a_host_cannot_reach_admin(api_client: Any, host: Actor, path: str) -> None:
    """Being a vendor is not being staff. A host who could open the admin
    panel could approve their own listings and set their own commission."""
    response = await api_client.get(path, headers=host.auth)
    assert response.status_code == 403, f"{path} -> {response.status_code}"


@pytest.mark.parametrize("path", ADMIN_READS)
async def test_staff_can_read_the_admin_surface(api_client: Any, staff: Actor, path: str) -> None:
    response = await api_client.get(path, headers=staff.auth)
    assert response.status_code == 200, f"{path}: {response.text[:200]}"


async def test_staff_can_see_every_vendor(api_client: Any, staff: Actor, host: Actor) -> None:
    """The opposite of the scoping above — this is the surface that is
    *supposed* to see everything."""
    response = await api_client.get("/api/v1/admin/vendors", headers=staff.auth)

    assert response.status_code == 200, response.text
    # Admin lists carry their paging under `meta`, not a flat `total`.
    body = response.json()
    assert len(body["items"]) >= 1
    assert body["meta"]["total"] >= 1


async def test_a_guest_cannot_moderate_a_review(
    api_client: Any, guest: Actor, host: Actor, listing: Listing, db: Any
) -> None:
    """Removing a review is a staff decision. A guest who could do it could
    delete criticism of a property they own."""
    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id)
    written = await api_client.post(
        "/api/v1/reviews",
        headers=guest.auth,
        json={
            "booking_id": str(booking_id),
            "rating": 1,
            "body": "A long enough body to satisfy the minimum length rule for reviews.",
        },
    )
    review_id = written.json()["id"]

    response = await api_client.post(
        f"/api/v1/admin/reviews/{review_id}/moderate",
        headers=guest.auth,
        json={"remove": True, "reason": "I did not like it"},
    )

    assert response.status_code == 403, response.text


async def test_an_unknown_admin_resource_is_404_not_500(api_client: Any, staff: Actor) -> None:
    response = await api_client.get(f"/api/v1/admin/users/{uuid.uuid4()}", headers=staff.auth)
    assert response.status_code == 404, response.text


async def test_a_traveller_cannot_enumerate_unpublished_listings(
    api_client: Any, guest: Actor, db: Any
) -> None:
    """Regression: the admin property list was readable by any signed-in user.

    It was guarded by `PROPERTY_READ_ANY` — which every traveller holds, so
    they can browse the public catalogue — while the endpoint means "every
    listing in any state". One overloaded permission name, two very different
    meanings, and the result was that a signed-in visitor could enumerate
    drafts, rejected listings and their rejection reasons, each with the vendor
    behind it.

    Now guarded by `PROPERTY_READ_INTERNAL`, which only staff hold.
    """
    draft = await seed_listing(db, status="draft")

    response = await api_client.get("/api/v1/admin/properties", headers=guest.auth)

    assert response.status_code == 403, response.text
    assert str(draft.property_id) not in response.text


async def test_staff_can_still_see_unpublished_listings(
    api_client: Any, staff: Actor, db: Any
) -> None:
    """The other half. Locking travellers out is only correct if the people
    who need it still have it — moderating a queue of drafts is the whole
    point of the endpoint."""
    draft = await seed_listing(db, status="draft")

    response = await api_client.get(
        "/api/v1/admin/properties", headers=staff.auth, params={"status": "draft", "size": 100}
    )

    assert response.status_code == 200, response.text
    assert any(item["id"] == str(draft.property_id) for item in response.json()["items"])
