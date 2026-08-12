"""Search, property detail, quotes and availability.

The public read surface. Two things it has to get right, and one of them once
took down a worker.

**Every parameter is a typed enum on the signature.** An unvalidated `sort=`
reached a `ValueError` inside a repository, escaped the handler, and left the
ASGI connection with no response written — a hung request and a wedged worker,
reachable by anyone with a URL bar. Both the web and Flutter clients were
sending `sort=rating`, which was never a valid value.

**A property that is not published does not exist.** Not 403, which confirms
it; 404, which does not.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.api.conftest import Listing, seed_listing

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ══════════════════════════════════════════════════════════════════════════
# Search
# ══════════════════════════════════════════════════════════════════════════


async def test_search_returns_a_published_listing(api_client: Any, db: Any) -> None:
    """`q` is the free-text parameter. There is no `city=` filter.

    Worth stating: unknown query parameters are silently ignored, so a search
    with a misspelled filter returns *everything* and looks like it worked.
    That is how the first version of these tests passed while asserting
    nothing.

    The search matches on `name % :q` (trigram) OR `city ILIKE :q_prefix`.
    A unique city is used here rather than a unique name, because trigram
    similarity matches every listing sharing a prefix — and this database
    accumulates one per run — whereas the city predicate is an exact prefix.
    """
    one_off = await seed_listing(db, city=f"Findable{uuid.uuid4().hex[:8]}")

    response = await api_client.get("/api/v1/search", params={"q": one_off.city})

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["id"] for item in body["items"]] == [str(one_off.property_id)]


async def test_search_needs_no_authentication(api_client: Any, listing: Listing) -> None:
    """Browsing before signing in is the whole funnel."""
    response = await api_client.get("/api/v1/search", params={"q": listing.city})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "sort",
    [
        # The two values the clients were actually sending before the enum
        # landed. Each one used to reach a `ValueError` inside the repository,
        # escape the handler and hang the connection.
        "rating",
        "distance",
        "'; DROP TABLE properties; --",
        "../../etc/passwd",
        "\x00null",
        "a" * 500,
    ],
)
async def test_an_invalid_sort_is_422_not_a_hung_connection(api_client: Any, sort: str) -> None:
    """**The** regression. A 500 would be bad; no response at all was worse.

    Validation on the signature means FastAPI rejects it before any of our code
    runs, so there is nothing left to throw.
    """
    response = await api_client.get("/api/v1/search", params={"q": "Anjuna", "sort": sort})

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"]


@pytest.mark.parametrize(
    ("params", "why"),
    [
        # Search is cursor-paged, so the bound that matters is `limit`.
        ({"limit": 0}, "an empty page is not a page"),
        ({"limit": 10_000}, "an unbounded page is a denial of service"),
        ({"min_price": -1}, "negative money"),
        ({"adults": 0}, "a stay for nobody"),
        ({"adults": 999}, "beyond any real property"),
        ({"rooms": 0}, "a booking of no rooms"),
        ({"min_rating": 6}, "no such rating"),
        ({"min_rating": -1}, "no such rating"),
        ({"lat": 91}, "off the planet"),
        ({"lng": -181}, "off the planet"),
        ({"radius_m": 50}, "below the useful floor"),
        ({"radius_m": 10_000_000}, "the whole planet is not a search"),
        ({"property_type": "spaceship"}, "not in the enum"),
        ({"cancellation": "whenever"}, "not in the enum"),
    ],
)
async def test_out_of_range_parameters_are_refused(
    api_client: Any, params: dict[str, Any], why: str
) -> None:
    """Bounds on the signature, so FastAPI refuses before our code runs.

    Every one of these is a value a client can send by accident. The ones that
    matter most are the unbounded ones — `limit=10000` is a full table scan
    serialised to JSON, available to anyone with a URL bar.
    """
    response = await api_client.get("/api/v1/search", params={"q": "Anjuna", **params})
    assert response.status_code == 422, f"{why}: {response.text[:200]}"


async def test_a_city_with_nothing_in_it_is_an_empty_list_not_an_error(
    api_client: Any,
) -> None:
    """No results is a normal answer. A 404 here would make the client render
    an error page for a search that simply matched nothing."""
    response = await api_client.get("/api/v1/search", params={"q": "Zzyzx" + "q" * 12})

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_paging_is_stable_across_requests(api_client: Any, db: Any) -> None:
    """Two pages must not show the same property twice.

    An unstable sort — one that ties on a non-unique column with no tiebreak —
    silently duplicates rows across pages and drops others entirely.
    """
    # A city nothing else uses, so the two pages contain only these five.
    city = f"Paging{uuid.uuid4().hex[:8]}"
    for _ in range(5):
        await seed_listing(db, city=city)

    first = await api_client.get("/api/v1/search", params={"q": city, "limit": 2})
    assert first.status_code == 200, first.text
    page_one = first.json()
    cursor = page_one["next_cursor"]
    assert cursor, "five listings and a limit of two must offer a next page"

    second = await api_client.get(
        "/api/v1/search", params={"q": city, "limit": 2, "cursor": cursor}
    )
    assert second.status_code == 200, second.text

    ids_a = {item["id"] for item in page_one["items"]}
    ids_b = {item["id"] for item in second.json()["items"]}
    assert ids_a and ids_b
    assert not (ids_a & ids_b), "a property appeared on two pages"


async def test_a_forged_cursor_is_refused_rather_than_crashing(api_client: Any) -> None:
    """A cursor is an opaque token the client round-trips. Anyone can edit it,
    and a decoder that trusts it turns a query string into a way to reach the
    repository's internals."""
    for cursor in ("not-base64", "', 1)--", "eyJib2d1cyI6dHJ1ZX0=", "x" * 400):
        response = await api_client.get("/api/v1/search", params={"q": "Anjuna", "cursor": cursor})
        assert response.status_code in (200, 400, 422), (
            f"a forged cursor must not 500: {cursor!r} -> {response.status_code}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Property detail
# ══════════════════════════════════════════════════════════════════════════


async def test_a_property_can_be_fetched_by_slug(api_client: Any, listing: Listing) -> None:
    response = await api_client.get(f"/api/v1/properties/{listing.slug}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(listing.property_id)
    assert body["room_types"], "a bookable listing must expose its rooms"


async def test_a_property_can_be_fetched_by_id(api_client: Any, listing: Listing) -> None:
    """Both forms are in use — the web app links by slug, the mobile app holds
    ids from a previous response."""
    response = await api_client.get(f"/api/v1/properties/{listing.property_id}")
    assert response.status_code == 200


async def test_an_unpublished_property_is_404_not_403(api_client: Any, db: Any) -> None:
    """403 would confirm it exists.

    A host who takes a listing down has usually done so for a reason, and an
    endpoint that distinguishes "never existed" from "withdrawn" is an endpoint
    that reports on them.
    """
    draft = await seed_listing(db, status="draft")

    by_slug = await api_client.get(f"/api/v1/properties/{draft.slug}")
    by_id = await api_client.get(f"/api/v1/properties/{draft.property_id}")

    assert by_slug.status_code == 404
    assert by_id.status_code == 404


async def test_an_unknown_property_is_404(api_client: Any) -> None:
    response = await api_client.get("/api/v1/properties/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_the_public_view_hides_the_full_address(api_client: Any, listing: Listing) -> None:
    """The street address is released on confirmation, not on browsing.

    Publishing it would let anyone enumerate the exact location of every
    property on the platform, which matters most for the hosts letting a room
    in the house they live in.
    """
    body = (await api_client.get(f"/api/v1/properties/{listing.slug}")).json()

    assert "1 Test Lane" not in (body.get("address") or ""), "exact address leaked"


# ══════════════════════════════════════════════════════════════════════════
# Availability and quotes
# ══════════════════════════════════════════════════════════════════════════


async def test_availability_reports_open_dates(api_client: Any, listing: Listing) -> None:
    from datetime import UTC, datetime, timedelta

    start = (datetime.now(UTC) + timedelta(days=10)).date()
    response = await api_client.get(
        f"/api/v1/properties/{listing.property_id}/availability",
        params={"from_date": start.isoformat(), "to_date": (start + timedelta(days=3)).isoformat()},
    )

    assert response.status_code == 200, response.text


async def test_a_quote_prices_a_real_stay(api_client: Any, listing: Listing) -> None:
    """The number here is the number the guest is charged.

    Quoted server-side and re-checked at booking, so a client that recomputes
    it — or tampers with it — cannot change what is taken.
    """
    from datetime import UTC, datetime, timedelta

    check_in = (datetime.now(UTC) + timedelta(days=14)).date()
    response = await api_client.post(
        f"/api/v1/properties/{listing.property_id}/quote",
        json={
            "room_type_id": str(listing.room_type_id),
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=2)).isoformat(),
            "adults": 2,
            "children": 0,
            "rooms": 1,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_minor"] > 0
    # Integer minor units end to end. A float here is a rounding error that
    # eventually disagrees with the invoice.
    assert isinstance(body["total_minor"], int)


async def test_a_quote_for_a_backwards_stay_is_refused(api_client: Any, listing: Listing) -> None:
    from datetime import UTC, datetime, timedelta

    check_in = (datetime.now(UTC) + timedelta(days=14)).date()
    response = await api_client.post(
        f"/api/v1/properties/{listing.property_id}/quote",
        json={
            "room_type_id": str(listing.room_type_id),
            "check_in": check_in.isoformat(),
            "check_out": (check_in - timedelta(days=1)).isoformat(),
            "adults": 2,
            "children": 0,
            "rooms": 1,
        },
    )

    assert response.status_code in (400, 409, 422), response.text


async def test_a_quote_for_the_past_is_refused(api_client: Any, listing: Listing) -> None:
    from datetime import UTC, datetime, timedelta

    past = (datetime.now(UTC) - timedelta(days=5)).date()
    response = await api_client.post(
        f"/api/v1/properties/{listing.property_id}/quote",
        json={
            "room_type_id": str(listing.room_type_id),
            "check_in": past.isoformat(),
            "check_out": (past + timedelta(days=2)).isoformat(),
            "adults": 2,
            "children": 0,
            "rooms": 1,
        },
    )

    assert response.status_code in (400, 409, 422), response.text
