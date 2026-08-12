"""Reviews and the wishlist, over HTTP.

Two features with the same shape — a guest writing something about a property —
and two very different failure modes.

A **review** is public, permanent and affects a host's income, so the rules are
about who may write one and what happens to the aggregate. A **wishlist** is
private, and the rules are about nobody else seeing it and nothing stale being
shown.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.api.conftest import Actor, Listing, seed_booking, seed_listing

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

BODY = (
    "The villa was spotless and the host left directions to the bakery. "
    "Road noise at night was worse than the photographs suggest."
)


# ══════════════════════════════════════════════════════════════════════════
# Reviews
# ══════════════════════════════════════════════════════════════════════════


async def test_a_completed_stay_can_be_reviewed(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id)

    response = await api_client.post(
        "/api/v1/reviews",
        headers=guest.auth,
        json={"booking_id": str(booking_id), "rating": 5, "title": "Lovely", "body": BODY},
    )

    assert response.status_code in (200, 201), response.text
    assert response.json()["rating"] == 5


async def test_reviewing_requires_authentication(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id)

    response = await api_client.post(
        "/api/v1/reviews",
        json={"booking_id": str(booking_id), "rating": 5, "body": BODY},
    )

    assert response.status_code == 401


async def test_you_cannot_review_someone_elses_stay(
    api_client: Any, guest: Actor, other_guest: Actor, listing: Listing, db: Any
) -> None:
    """**The** rule that makes a rating mean anything.

    Without it, anyone with a booking id — or a lucky guess — can review a
    property they have never been to, which is the whole business model of a
    review farm.
    """
    theirs = await seed_booking(db, listing=listing, guest_id=other_guest.id)

    response = await api_client.post(
        "/api/v1/reviews",
        headers=guest.auth,
        json={"booking_id": str(theirs), "rating": 1, "body": BODY},
    )

    assert response.status_code in (403, 404), response.text


async def test_you_cannot_review_a_stay_that_has_not_happened(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    """A confirmed booking for next month is not a stay. Reviewing from the
    taxi on the way in is not a review of the stay."""
    future = await seed_booking(
        db, listing=listing, guest_id=guest.id, status="confirmed", days_ago=-30
    )

    response = await api_client.post(
        "/api/v1/reviews",
        headers=guest.auth,
        json={"booking_id": str(future), "rating": 5, "body": BODY},
    )

    assert response.status_code in (400, 403, 409, 422), response.text


async def test_one_booking_gets_one_review(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    """Enforced by a unique constraint rather than a prior read — two taps on a
    slow connection both pass a check-then-act."""
    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id)
    payload = {"booking_id": str(booking_id), "rating": 5, "body": BODY}

    first = await api_client.post("/api/v1/reviews", headers=guest.auth, json=payload)
    second = await api_client.post("/api/v1/reviews", headers=guest.auth, json=payload)

    assert first.status_code in (200, 201), first.text
    assert second.status_code == 409, second.text


@pytest.mark.parametrize("rating", [0, 6, -1, 100])
async def test_a_rating_outside_one_to_five_is_refused(
    api_client: Any, guest: Actor, listing: Listing, db: Any, rating: int
) -> None:
    """The property rating is a running aggregate. A 100 that reaches it is not
    a rating anybody can find and delete afterwards — it is a permanently
    wrong average."""
    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id)

    response = await api_client.post(
        "/api/v1/reviews",
        headers=guest.auth,
        json={"booking_id": str(booking_id), "rating": rating, "body": BODY},
    )

    assert response.status_code in (400, 422), response.text


async def test_a_review_moves_the_property_rating(api_client: Any, guest: Actor, db: Any) -> None:
    """The aggregate is maintained in the same transaction as the review.

    A rating that advanced for a review that rolled back is a number nobody
    can reproduce.
    """
    from sqlalchemy import text

    one_off = await seed_listing(db)
    booking_id = await seed_booking(db, listing=one_off, guest_id=guest.id)

    before = (
        await db.execute(
            text("SELECT review_average, review_count FROM properties WHERE id = :p"),
            {"p": one_off.property_id},
        )
    ).one()
    assert before == (0, 0)

    posted = await api_client.post(
        "/api/v1/reviews",
        headers=guest.auth,
        json={"booking_id": str(booking_id), "rating": 4, "body": BODY},
    )
    assert posted.status_code in (200, 201), posted.text

    after = (
        await db.execute(
            text("SELECT review_average, review_count FROM properties WHERE id = :p"),
            {"p": one_off.property_id},
        )
    ).one()
    assert after[1] == 1
    assert float(after[0]) == 4.0


async def test_reviews_for_a_property_are_public(api_client: Any, guest: Actor, db: Any) -> None:
    """No authentication. Reviews are the thing people read before deciding
    whether to make an account."""
    one_off = await seed_listing(db)
    booking_id = await seed_booking(db, listing=one_off, guest_id=guest.id)
    await api_client.post(
        "/api/v1/reviews",
        headers=guest.auth,
        json={"booking_id": str(booking_id), "rating": 5, "body": BODY},
    )

    response = await api_client.get(f"/api/v1/reviews/property/{one_off.property_id}")

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


async def test_a_guest_sees_their_own_reviews(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id)
    await api_client.post(
        "/api/v1/reviews",
        headers=guest.auth,
        json={"booking_id": str(booking_id), "rating": 5, "body": BODY},
    )

    response = await api_client.get("/api/v1/reviews/mine", headers=guest.auth)

    assert response.status_code == 200, response.text
    assert len(response.json()) >= 1


async def test_mine_is_not_swallowed_by_the_id_route(api_client: Any) -> None:
    """`/reviews/mine` is declared before `/reviews/{review_id}`.

    FastAPI matches in declaration order, so a later literal route loses to an
    earlier parameterised one — and `mine` would be parsed as a UUID and 422.
    """
    response = await api_client.get("/api/v1/reviews/mine")
    assert response.status_code == 401, "should be an auth failure, not a parse failure"


# ══════════════════════════════════════════════════════════════════════════
# Wishlist
# ══════════════════════════════════════════════════════════════════════════


async def test_saving_a_property_is_idempotent(
    api_client: Any, guest: Actor, listing: Listing
) -> None:
    """A heart icon is a control people press twice on a slow connection."""
    first = await api_client.put(
        f"/api/v1/wishlist/{listing.property_id}", headers=guest.auth, json={"note": "for June"}
    )
    second = await api_client.put(
        f"/api/v1/wishlist/{listing.property_id}", headers=guest.auth, json={"note": "updated"}
    )

    assert first.status_code == 204, first.text
    assert second.status_code == 204, second.text

    listed = await api_client.get("/api/v1/wishlist", headers=guest.auth)
    matching = [i for i in listed.json() if i["property_id"] == str(listing.property_id)]
    assert len(matching) == 1
    assert matching[0]["note"] == "updated"


async def test_the_wishlist_is_private(
    api_client: Any, guest: Actor, other_guest: Actor, listing: Listing
) -> None:
    """A list of places someone is thinking about going is more revealing than
    most of what this platform stores."""
    await api_client.put(f"/api/v1/wishlist/{listing.property_id}", headers=guest.auth, json={})

    theirs = await api_client.get("/api/v1/wishlist", headers=other_guest.auth)

    assert theirs.status_code == 200
    assert all(i["property_id"] != str(listing.property_id) for i in theirs.json())


async def test_the_wishlist_needs_authentication(api_client: Any) -> None:
    assert (await api_client.get("/api/v1/wishlist")).status_code == 401


async def test_prices_are_read_live_not_stored(api_client: Any, guest: Actor, db: Any) -> None:
    """**The** wishlist rule.

    A saved card showing the price from the month it was saved misleads
    someone into clicking. Nothing display-shaped is stored, so a price change
    shows through immediately.
    """
    from sqlalchemy import text

    one_off = await seed_listing(db, rate_minor=450_000)
    await api_client.put(f"/api/v1/wishlist/{one_off.property_id}", headers=guest.auth, json={})

    await db.execute(
        text("UPDATE properties SET min_rate_minor = 999000 WHERE id = :p"),
        {"p": one_off.property_id},
    )
    await db.commit()

    listed = await api_client.get("/api/v1/wishlist", headers=guest.auth)
    saved = next(i for i in listed.json() if i["property_id"] == str(one_off.property_id))

    assert saved["from_price_minor"] == 999000, "the wishlist served a stale price"


async def test_a_delisted_property_becomes_a_tombstone(
    api_client: Any, guest: Actor, db: Any
) -> None:
    """It stays on the list, flagged and priceless.

    A list that quietly gets shorter reads as a bug, and the guest goes looking
    for the place they lost.
    """
    from sqlalchemy import text

    one_off = await seed_listing(db)
    await api_client.put(f"/api/v1/wishlist/{one_off.property_id}", headers=guest.auth, json={})

    await db.execute(
        text("UPDATE properties SET status = 'unpublished' WHERE id = :p"),
        {"p": one_off.property_id},
    )
    await db.commit()

    listed = await api_client.get("/api/v1/wishlist", headers=guest.auth)
    saved = next(i for i in listed.json() if i["property_id"] == str(one_off.property_id))

    assert saved["available"] is False
    assert saved["from_price_minor"] is None, "a price on something nobody can book"


async def test_saving_an_unpublished_property_is_404(
    api_client: Any, guest: Actor, db: Any
) -> None:
    """404, not 403 — a different answer would confirm the listing exists."""
    draft = await seed_listing(db, status="draft")

    response = await api_client.put(
        f"/api/v1/wishlist/{draft.property_id}", headers=guest.auth, json={}
    )

    assert response.status_code == 404, response.text


async def test_removing_something_absent_is_still_204(api_client: Any, guest: Actor) -> None:
    """Un-hearting something already gone is the guest getting what they
    wanted. A 404 would surface as an error toast for a successful no-op."""
    response = await api_client.delete(f"/api/v1/wishlist/{uuid.uuid4()}", headers=guest.auth)
    assert response.status_code == 204


async def test_merging_a_devices_list_is_additive_and_repeatable(
    api_client: Any, guest: Actor, listing: Listing, db: Any
) -> None:
    """Called once at sign-in, and safe to retry after a timeout."""
    second = await seed_listing(db)

    first_merge = await api_client.post(
        "/api/v1/wishlist/merge",
        headers=guest.auth,
        json={"property_ids": [str(listing.property_id), str(second.property_id)]},
    )
    replay = await api_client.post(
        "/api/v1/wishlist/merge",
        headers=guest.auth,
        json={"property_ids": [str(listing.property_id), str(second.property_id)]},
    )

    assert first_merge.json()["merged"] == 2
    assert replay.json()["merged"] == 0, "a replayed merge duplicated entries"


async def test_one_stale_id_does_not_fail_the_whole_merge(
    api_client: Any, guest: Actor, listing: Listing
) -> None:
    """A device's local list can hold something delisted months ago. Refusing
    the merge over it would lose the other nineteen."""
    response = await api_client.post(
        "/api/v1/wishlist/merge",
        headers=guest.auth,
        json={"property_ids": [str(uuid.uuid4()), str(listing.property_id)]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["merged"] == 1
