"""Booking, over HTTP.

The endpoints that take money, so the tests are about what happens when
something goes wrong rather than when it goes right.

The property that matters most is **the quoted price is the server's, not the
client's**. A booking request carries `quoted_total_minor` so the server can
refuse a stale or tampered figure — a client that could name its own price
could book a villa for one rupee.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.api.conftest import Actor, Listing, seed_booking

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def stay(offset_days: int = 21, nights: int = 2) -> tuple[str, str]:
    start = (datetime.now(UTC) + timedelta(days=offset_days)).date()
    return start.isoformat(), (start + timedelta(days=nights)).isoformat()


async def quote(client: Any, listing: Listing, **overrides: Any) -> dict[str, Any]:
    check_in, check_out = stay()
    body = {
        "room_type_id": str(listing.room_type_id),
        "check_in": check_in,
        "check_out": check_out,
        "adults": 2,
        "children": 0,
        "rooms": 1,
        **overrides,
    }
    response = await client.post(f"/api/v1/properties/{listing.property_id}/quote", json=body)
    assert response.status_code == 200, response.text
    return {**body, "quote": response.json()}


# ══════════════════════════════════════════════════════════════════════════
# Creating a booking
# ══════════════════════════════════════════════════════════════════════════


async def test_booking_requires_authentication(api_client: Any, listing: Listing) -> None:
    check_in, check_out = stay()
    response = await api_client.post(
        "/api/v1/bookings",
        json={
            "property_id": str(listing.property_id),
            "room_type_id": str(listing.room_type_id),
            "check_in": check_in,
            "check_out": check_out,
            "adults": 2,
            "guest_name": "Anon",
            "guest_email": "anon@example.com",
            "guest_phone": "+919876500000",
            "quoted_total_minor": 900000,
        },
    )

    assert response.status_code == 401


async def test_creating_a_booking_requires_an_idempotency_key(
    api_client: Any, guest: Actor, listing: Listing
) -> None:
    """Required, not optional, and the endpoint says so.

    A booking POST that times out is retried by the client, by the browser, or
    by the person pressing the button again. Without a key the retry is a
    second booking and a second charge; the header is what makes the retry
    safe, so the server refuses the request that cannot be made safe.
    """
    priced = await quote(api_client, listing)

    response = await api_client.post(
        "/api/v1/bookings",
        headers=guest.auth,
        json={
            "property_id": str(listing.property_id),
            "room_type_id": priced["room_type_id"],
            "check_in": priced["check_in"],
            "check_out": priced["check_out"],
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "guest_name": "Test Guest",
            "guest_email": guest.email,
            "guest_phone": "+919876500000",
            "quoted_total_minor": priced["quote"]["total_minor"],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"]["header"] == "Idempotency-Key"


async def test_a_guest_can_book_a_quoted_stay(
    api_client: Any, guest: Actor, listing: Listing
) -> None:
    priced = await quote(api_client, listing)

    response = await api_client.post(
        "/api/v1/bookings",
        headers={**guest.auth, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "property_id": str(listing.property_id),
            "room_type_id": priced["room_type_id"],
            "check_in": priced["check_in"],
            "check_out": priced["check_out"],
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "guest_name": "Test Guest",
            "guest_email": guest.email,
            "guest_phone": "+919876500000",
            "quoted_total_minor": priced["quote"]["total_minor"],
        },
    )

    assert response.status_code in (200, 201), response.text
    body = response.json()
    assert body["reference"].startswith("RW-")
    assert body["total_minor"] == priced["quote"]["total_minor"]
    # A held booking, not a confirmed one — nothing is confirmed before payment.
    assert body["status"] in ("pending_payment", "pending_approval")


async def test_replaying_the_same_idempotency_key_returns_the_same_booking(
    api_client: Any, guest: Actor, listing: Listing
) -> None:
    """**The** reason the header exists.

    The guest pressed the button twice, or their connection dropped after the
    request left. Two bookings and two charges is the failure this prevents,
    and it has to hold at the HTTP layer because that is where the retry
    happens.
    """
    priced = await quote(api_client, listing)
    key = str(uuid.uuid4())
    payload = {
        "property_id": str(listing.property_id),
        "room_type_id": priced["room_type_id"],
        "check_in": priced["check_in"],
        "check_out": priced["check_out"],
        "adults": 2,
        "children": 0,
        "rooms": 1,
        "guest_name": "Test Guest",
        "guest_email": guest.email,
        "guest_phone": "+919876500000",
        "quoted_total_minor": priced["quote"]["total_minor"],
    }
    headers = {**guest.auth, "Idempotency-Key": key}

    first = await api_client.post("/api/v1/bookings", headers=headers, json=payload)
    second = await api_client.post("/api/v1/bookings", headers=headers, json=payload)

    assert first.status_code in (200, 201), first.text
    assert second.status_code in (200, 201), second.text
    assert first.json()["id"] == second.json()["id"], "a retry created a second booking"
    assert first.json()["reference"] == second.json()["reference"]


async def test_a_tampered_price_is_refused(api_client: Any, guest: Actor, listing: Listing) -> None:
    """**The** money rule.

    The client sends back the figure it was quoted; the server recomputes and
    compares. Without this, the price is whatever the request says it is.
    """
    priced = await quote(api_client, listing)

    response = await api_client.post(
        "/api/v1/bookings",
        headers={**guest.auth, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "property_id": str(listing.property_id),
            "room_type_id": priced["room_type_id"],
            "check_in": priced["check_in"],
            "check_out": priced["check_out"],
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "guest_name": "Test Guest",
            "guest_email": guest.email,
            "guest_phone": "+919876500000",
            # One rupee.
            "quoted_total_minor": 100,
        },
    )

    assert response.status_code in (400, 409, 422), response.text
    assert response.status_code != 201, "a client must not be able to name its own price"


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        ({"adults": 0}, "a stay for nobody"),
        ({"adults": 99}, "beyond the room's occupancy"),
        ({"rooms": 0}, "no rooms"),
        ({"rooms": 99}, "more rooms than exist"),
    ],
)
async def test_an_impossible_party_is_refused(
    api_client: Any, guest: Actor, listing: Listing, overrides: dict[str, Any], why: str
) -> None:
    check_in, check_out = stay()
    response = await api_client.post(
        "/api/v1/bookings",
        headers={**guest.auth, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "property_id": str(listing.property_id),
            "room_type_id": str(listing.room_type_id),
            "check_in": check_in,
            "check_out": check_out,
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "guest_name": "Test Guest",
            "guest_email": guest.email,
            "guest_phone": "+919876500000",
            "quoted_total_minor": 900000,
            **overrides,
        },
    )

    assert response.status_code in (400, 409, 422), f"{why}: {response.text[:160]}"


async def test_booking_an_unpublished_property_is_refused(
    api_client: Any, guest: Actor, db: Any
) -> None:
    """A draft listing has no price and no inventory. Booking one by guessing
    its id must fail as "not found" rather than proceeding."""
    from tests.api.conftest import seed_listing

    draft = await seed_listing(db, status="draft")
    check_in, check_out = stay()

    response = await api_client.post(
        "/api/v1/bookings",
        headers={**guest.auth, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "property_id": str(draft.property_id),
            "room_type_id": str(draft.room_type_id),
            "check_in": check_in,
            "check_out": check_out,
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "guest_name": "Test Guest",
            "guest_email": guest.email,
            "guest_phone": "+919876500000",
            "quoted_total_minor": 900000,
        },
    )

    assert response.status_code in (400, 404, 409, 422), response.text


# ══════════════════════════════════════════════════════════════════════════
# Reading bookings
# ══════════════════════════════════════════════════════════════════════════


async def test_a_guest_sees_only_their_own_bookings(
    api_client: Any, guest: Actor, other_guest: Actor, listing: Listing, db: Any
) -> None:
    """The single most important authorisation property on this endpoint.

    A bookings list scoped by a client-supplied id — or not scoped at all —
    hands over every guest's travel dates, phone number and address.
    """
    mine = await seed_booking(db, listing=listing, guest_id=guest.id)
    theirs = await seed_booking(db, listing=listing, guest_id=other_guest.id, days_ago=9)

    response = await api_client.get("/api/v1/bookings", headers=guest.auth)

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert str(mine) in ids
    assert str(theirs) not in ids, "another guest's booking is visible"


async def test_fetching_someone_elses_booking_is_404_not_403(
    api_client: Any, guest: Actor, other_guest: Actor, listing: Listing, db: Any
) -> None:
    """404, because 403 confirms the booking exists — and a booking reference
    is short enough to guess at."""
    theirs = await seed_booking(db, listing=listing, guest_id=other_guest.id)

    response = await api_client.get(f"/api/v1/bookings/{theirs}", headers=guest.auth)

    assert response.status_code == 404, response.text


async def test_an_unknown_booking_is_404(api_client: Any, guest: Actor) -> None:
    response = await api_client.get(f"/api/v1/bookings/{uuid.uuid4()}", headers=guest.auth)
    assert response.status_code == 404


async def test_a_guest_can_read_their_own_booking(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id)

    response = await api_client.get(f"/api/v1/bookings/{booking_id}", headers=guest.auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(booking_id)
    # Money is integer minor units all the way to the client.
    assert isinstance(body["total_minor"], int)


async def test_the_bookings_list_is_paginated(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    """An unbounded list is a slow page for a frequent traveller and a
    denial of service for whoever has the most bookings."""
    for offset in range(3):
        await seed_booking(db, listing=listing, guest_id=guest.id, days_ago=5 + offset * 3)

    response = await api_client.get("/api/v1/bookings", headers=guest.auth, params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()["items"]) <= 2


# ══════════════════════════════════════════════════════════════════════════
# Cancelling
# ══════════════════════════════════════════════════════════════════════════


async def test_a_refund_preview_does_not_move_money(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    """A preview is a GET and must stay one.

    It is what the cancellation dialog renders, so it runs far more often than
    a cancellation and must never change state.
    """
    booking_id = await seed_booking(
        db, listing=listing, guest_id=guest.id, status="confirmed", days_ago=-20
    )

    response = await api_client.get(
        f"/api/v1/bookings/{booking_id}/refund-preview", headers=guest.auth
    )

    assert response.status_code == 200, response.text
    after = await api_client.get(f"/api/v1/bookings/{booking_id}", headers=guest.auth)
    assert after.json()["status"] == "confirmed", "a preview changed the booking"


async def test_a_guest_cannot_cancel_someone_elses_booking(
    api_client: Any, guest: Actor, other_guest: Actor, listing: Listing, db: Any
) -> None:
    theirs = await seed_booking(
        db, listing=listing, guest_id=other_guest.id, status="confirmed", days_ago=-20
    )

    response = await api_client.post(
        f"/api/v1/bookings/{theirs}/cancel",
        headers=guest.auth,
        json={"reason": "not mine to cancel"},
    )

    assert response.status_code in (403, 404), response.text
    assert response.status_code != 200


async def test_cancelling_a_completed_stay_is_refused(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    """The stay already happened. Cancelling it would issue a refund for a
    night somebody slept in."""
    booking_id = await seed_booking(
        db, listing=listing, guest_id=guest.id, status="completed", days_ago=10
    )

    response = await api_client.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        headers=guest.auth,
        json={"reason": "changed my mind, a week later"},
    )

    assert response.status_code in (400, 409, 422), response.text


async def test_reusing_a_key_with_a_different_stay_is_a_conflict(
    api_client: Any, guest: Actor, listing: Listing
) -> None:
    """A key identifies one request, not one client.

    Replaying it with a different body means the client has a bug — reusing a
    key it already spent. Returning the *first* booking would silently discard
    the second request; a 409 says what happened.
    """
    priced = await quote(api_client, listing)
    key = str(uuid.uuid4())
    base = {
        "property_id": str(listing.property_id),
        "room_type_id": priced["room_type_id"],
        "check_in": priced["check_in"],
        "check_out": priced["check_out"],
        "adults": 2,
        "children": 0,
        "rooms": 1,
        "guest_name": "Test Guest",
        "guest_email": guest.email,
        "guest_phone": "+919876500000",
        "quoted_total_minor": priced["quote"]["total_minor"],
    }
    headers = {**guest.auth, "Idempotency-Key": key}

    first = await api_client.post("/api/v1/bookings", headers=headers, json=base)
    assert first.status_code in (200, 201), first.text

    later = await quote(api_client, listing, adults=1)
    second = await api_client.post(
        "/api/v1/bookings",
        headers=headers,
        json={**base, "adults": 1, "quoted_total_minor": later["quote"]["total_minor"]},
    )

    assert second.status_code == 409, second.text


async def test_one_guests_key_cannot_replay_anothers_booking(
    api_client: Any, guest: Actor, other_guest: Actor, listing: Listing
) -> None:
    """The fingerprint includes the actor.

    Without it, a client-chosen key like `"1"` collides across users and the
    second guest receives the first guest's booking confirmation — with their
    name, dates and phone number on it.
    """
    priced = await quote(api_client, listing)
    shared_key = "shared-key-" + uuid.uuid4().hex[:8]
    payload = {
        "property_id": str(listing.property_id),
        "room_type_id": priced["room_type_id"],
        "check_in": priced["check_in"],
        "check_out": priced["check_out"],
        "adults": 2,
        "children": 0,
        "rooms": 1,
        "guest_phone": "+919876500000",
        "quoted_total_minor": priced["quote"]["total_minor"],
    }

    mine = await api_client.post(
        "/api/v1/bookings",
        headers={**guest.auth, "Idempotency-Key": shared_key},
        json={**payload, "guest_name": "Guest One", "guest_email": guest.email},
    )
    theirs = await api_client.post(
        "/api/v1/bookings",
        headers={**other_guest.auth, "Idempotency-Key": shared_key},
        json={**payload, "guest_name": "Guest Two", "guest_email": other_guest.email},
    )

    assert mine.status_code in (200, 201), mine.text
    if theirs.status_code in (200, 201):
        assert theirs.json()["id"] != mine.json()["id"], "one guest received another's booking"
