"""Fixtures for API tests.

These tests drive the **real application** — real router, real middleware, real
database, real Redis — over an in-process ASGI transport. No mocks anywhere.

That matters because of what this suite exists to catch. Every serious bug found
in this codebase so far lived in code the unit suite never executed: `vars()` on
a slotted dataclass broke every response-returning endpoint; an unvalidated
`sort` parameter escaped as a `ValueError` and wedged a worker; a query selected
`reviews_awaiting` and the handler forgot to return it; a rating upsert 409'd on
every decrease. All four were in routers and repositories sitting at 0%
coverage, and all four were found by a human running curl. A unit test of a use
case cannot find any of them.

**Isolation is by data, not by transaction.** The obvious approach — wrap each
test in a transaction and roll back — does not work here: the application opens
its own sessions through the container, so a rollback in the test would not
touch what the request committed. Instead every factory generates unique
identifiers, so tests neither see nor disturb each other's rows. Slower to
reason about than a rollback, and the only thing that actually works against a
real app.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text

pytestmark = pytest.mark.integration

#: Long enough to satisfy the password policy, and the same everywhere so a
#: failed login in a test is never about the password.
PASSWORD = "a-very-long-test-passphrase-2026"


def unique(prefix: str) -> str:
    """A value no other test will produce.

    `uuid4().hex` rather than a counter: tests run in any order, and under
    `-p xdist` in more than one process.
    """
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def unique_pan() -> str:
    """A syntactically valid Indian PAN, unique per call.

    Five letters, four digits, one letter — and `uq_vendors_pan` means a
    constant would collide the moment a second vendor is seeded, which is any
    test that involves two hosts.
    """
    body = uuid.uuid4().hex
    letters = "".join(chr(ord("A") + int(c, 16) % 26) for c in body[:5])
    digits = f"{int(body[5:9], 16) % 10000:04d}"
    return f"{letters}{digits}{chr(ord('A') + int(body[9], 16) % 26)}"


#: `example.com` rather than the reserved `.test` TLD. `EmailStr` validates
#: against the public suffix list and rejects `.test`, which is exactly the
#: sort of thing that turns a fixture into a twenty-minute detour.
EMAIL_DOMAIN = "example.com"


# ══════════════════════════════════════════════════════════════════════════
# Actors
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class Actor:
    """A signed-in user, and the header that proves it."""

    id: uuid.UUID
    email: str
    token: str

    @property
    def auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


async def register_and_login(client: Any, email: str | None = None) -> Actor:
    """Create an account through the real endpoints.

    Registration returns 202 with no tokens — the account exists but is
    unverified — so a separate login follows. Doing this through the API rather
    than by inserting a row is deliberate: it exercises password hashing, the
    session record and the token issuance that every other test depends on, so
    a break there fails loudly here rather than mysteriously everywhere.
    """
    address = email or f"{unique('guest')}@example.com"

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": address, "password": PASSWORD, "full_name": "Test Guest"},
    )
    assert response.status_code in (200, 201, 202), response.text

    response = await client.post(
        "/api/v1/auth/login", json={"email": address, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return Actor(
        id=uuid.UUID(body["user"]["id"]),
        email=address,
        token=body["tokens"]["access_token"],
    )


@pytest_asyncio.fixture
async def guest(api_client: Any) -> Actor:
    return await register_and_login(api_client)


@pytest_asyncio.fixture
async def other_guest(api_client: Any) -> Actor:
    """A second, unrelated account.

    Every authorisation test needs one. "Can A see B's data" is not a question
    a single-user fixture can ask, and it is the question that matters.
    """
    return await register_and_login(api_client)


@pytest_asyncio.fixture
async def staff(api_client: Any, db: Any) -> Actor:
    """An account with the roles that reach the admin surface.

    Roles are granted by inserting into `user_roles`; the trigger from
    migration 0002 mirrors them onto `users.roles`, which is what login reads
    into the token. Granting them before logging in is therefore required —
    a token minted first would not carry them.
    """
    email = f"{unique('staff')}@example.com"
    response = await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Test Staff"},
    )
    assert response.status_code in (200, 201, 202), response.text

    user_id = (
        await db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email})
    ).scalar_one()
    for role in ("admin", "superadmin", "support"):
        await db.execute(
            text(
                "INSERT INTO user_roles (id, user_id, role_name, granted_at) "
                "VALUES (gen_random_uuid(), :u, :r, now()) "
                "ON CONFLICT ON CONSTRAINT uq_user_roles_user_role DO NOTHING"
            ),
            {"u": user_id, "r": role},
        )
    await db.commit()

    login = await api_client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return Actor(id=user_id, email=email, token=login.json()["tokens"]["access_token"])


# ══════════════════════════════════════════════════════════════════════════
# Catalogue
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class Listing:
    property_id: uuid.UUID
    vendor_id: uuid.UUID
    owner_id: uuid.UUID
    room_type_id: uuid.UUID
    slug: str
    city: str
    name: str


@pytest_asyncio.fixture
async def db(integration_settings: Any) -> AsyncIterator[Any]:
    """A session for seeding and for asserting on what the API wrote.

    Committed, not rolled back. The application runs in the same process but
    opens its own sessions, so anything this fixture leaves uncommitted is
    invisible to the request under test.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.database.session import Database

    database = Database(integration_settings)
    async with AsyncSession(database.write_engine, expire_on_commit=False) as session:
        yield session
    await database.dispose()


async def seed_listing(
    db: Any,
    *,
    city: str = "Anjuna",
    rate_minor: int = 450_000,
    status: str = "published",
    instant: bool = True,
) -> Listing:
    """A published property with one bookable room type and inventory.

    Seeded in SQL rather than through the vendor API because that path is
    eleven requests long — register, apply, be approved by staff, create,
    add rooms, price them, open inventory, submit, be approved again — and a
    booking test that has to do all of it before it can start is a booking test
    nobody will add to.

    The vendor-facing endpoints are covered directly in `test_vendor_api.py`.
    """
    owner_id, vendor_id = uuid.uuid4(), uuid.uuid4()
    property_id, room_type_id = uuid.uuid4(), uuid.uuid4()
    slug = unique("stay")
    # A unique *name*, not just a unique id. The database persists across runs
    # and every seeded listing scores identically on relevance, so a search for
    # a shared name returns them tie-broken by id — and the one this test
    # created may be nowhere near the first page. Searching for something only
    # this listing has is the only stable assertion.
    name = f"Test House {slug[-8:]}"

    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, status) "
            "VALUES (:id, :email, 'x', 'active')"
        ),
        {"id": owner_id, "email": f"{unique('host')}@example.com"},
    )
    # `approved` requires BOTH a PAN and an `approved_at` —
    # `ck_vendors_approved_needs_evidence`. The constraint exists because an
    # approved vendor with no record of who approved them or when is a
    # compliance gap, and the fixture has to satisfy it like anything else.
    await db.execute(
        text(
            "INSERT INTO vendors (id, owner_user_id, legal_name, display_name, "
            "  contact_email, contact_phone, status, pan, approved_at, commission_bps) "
            "VALUES (:id, :owner, 'Test Stays LLP', 'Test Stays', "
            "  'host@example.com', :phone, 'approved', :pan, now(), 1200)"
        ),
        {
            "id": vendor_id,
            "owner": owner_id,
            "pan": unique_pan(),
            # Also unique. A shared phone number across two seeded vendors
            # trips `uq_vendors_contact_phone` on the second one.
            "phone": f"+9190{uuid.uuid4().int % 100000000:08d}",
        },
    )
    await db.execute(
        text("UPDATE users SET vendor_id = :v WHERE id = :u"),
        {"v": vendor_id, "u": owner_id},
    )
    await db.execute(
        text("""
            INSERT INTO properties
                (id, vendor_id, name, slug, property_type, status, description,
                 currency, line1, city, state, country_code, postal_code,
                 location, cancellation_policy, max_guests, min_rate_minor,
                 instant_booking, amenity_codes, room_type_count, published_at)
            VALUES
                (:id, :vendor, :name, :slug, 'villa', :status,
                 'A house that exists only for tests, described at sufficient length.',
                 'INR', '1 Test Lane', :city, 'Goa', 'IN', '403001',
                 ST_SetSRID(ST_MakePoint(73.74, 15.57), 4326)::geography,
                 'moderate', 6, :rate, :instant, ARRAY['wifi','pool'], 1,
                 -- Decided in Python. Reusing :status inside a CASE here made
                 -- asyncpg deduce two types for one placeholder (varchar as a
                 -- column value, text as a comparand) and refuse to prepare
                 -- the statement.
                 :published_at)
        """),
        {
            "id": property_id,
            "vendor": vendor_id,
            "slug": slug,
            "name": name,
            "city": city,
            "status": status,
            "rate": rate_minor,
            "instant": instant,
            "published_at": datetime.now(UTC) if status == "published" else None,
        },
    )
    await db.execute(
        text("""
            INSERT INTO room_types
                (id, property_id, name, description, max_adults, max_children,
                 total_units, base_rate_minor, included_guests, min_nights)
            VALUES (:id, :prop, 'Garden Room', 'A room.', 2, 2, 5, :rate, 2, 1)
        """),
        {"id": room_type_id, "prop": property_id, "rate": rate_minor},
    )
    # Inventory for the next ninety days. Without rows here every availability
    # query returns nothing and a booking test fails for a reason that has
    # nothing to do with booking.
    await db.execute(
        text("""
            INSERT INTO room_inventory (room_type_id, stay_date, units_total, units_booked)
            SELECT :rt, d::date, 5, 0
              FROM generate_series(CURRENT_DATE, CURRENT_DATE + 90, '1 day') AS d
            ON CONFLICT DO NOTHING
        """),
        {"rt": room_type_id},
    )
    await db.commit()

    return Listing(
        property_id=property_id,
        vendor_id=vendor_id,
        owner_id=owner_id,
        room_type_id=room_type_id,
        slug=slug,
        city=city,
        name=name,
    )


@pytest_asyncio.fixture
async def listing(db: Any) -> Listing:
    return await seed_listing(db)


@pytest_asyncio.fixture
async def host(api_client: Any, db: Any, listing: Listing) -> Actor:
    """The vendor who owns `listing`, signed in.

    Their password is set through the API so the hash is real; the account was
    created by `seed_listing` with a placeholder. Logging in requires the
    `vendor` role and `users.vendor_id`, both of which the seed sets — the
    portal authorises on the token, not on the vendors table.
    """
    email = (
        await db.execute(text("SELECT email FROM users WHERE id = :u"), {"u": listing.owner_id})
    ).scalar_one()

    from app.core.config import get_settings
    from app.core.security.password import PasswordHasherService

    hashed = PasswordHasherService(get_settings().security).hash(PASSWORD)
    await db.execute(
        text("UPDATE users SET password_hash = :h, status = 'active' WHERE id = :u"),
        {"h": hashed, "u": listing.owner_id},
    )
    await db.execute(
        text(
            "INSERT INTO user_roles (id, user_id, role_name, granted_at) "
            "VALUES (gen_random_uuid(), :u, 'vendor', now()) "
            "ON CONFLICT ON CONSTRAINT uq_user_roles_user_role DO NOTHING"
        ),
        {"u": listing.owner_id},
    )
    await db.commit()

    login = await api_client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return Actor(id=listing.owner_id, email=email, token=login.json()["tokens"]["access_token"])


# ══════════════════════════════════════════════════════════════════════════
# Bookings
# ══════════════════════════════════════════════════════════════════════════


async def seed_booking(
    db: Any,
    *,
    listing: Listing,
    guest_id: uuid.UUID,
    status: str = "completed",
    days_ago: int = 7,
    nights: int = 2,
) -> uuid.UUID:
    """A booking in a chosen state.

    Seeded rather than driven through checkout because most tests need a
    *completed* stay in the past — to write a review, to appear in earnings —
    and there is no way to reach that state through the API without waiting.

    `stay_range` is maintained alongside `check_in`/`check_out` because the
    overlap exclusion constraint is defined on it; leaving it null makes the
    row invisible to every availability query.
    """
    booking_id = uuid.uuid4()
    check_in = (datetime.now(UTC) - timedelta(days=days_ago)).date()
    check_out = check_in + timedelta(days=nights)
    # `RW-YY-XXXXXXXX`, matching `_REF_RE` in the booking domain. A reference
    # in any other shape is stored happily and then rejected by the mapper on
    # the way *out*, so the row exists and every read of it 500s.
    year = datetime.now(UTC).strftime("%y")
    reference = f"RW-{year}-{uuid.uuid4().hex[:8].upper()}"

    # `ck_bookings_confirmed_needs_payment`: a booking with `confirmed_at` set
    # must also name a payment, so a booking can never be confirmed without
    # money having moved.
    #
    # `payment_id` is a *varchar* holding the gateway's own id (`pay_...`),
    # not a foreign key to our `payments` table — which is why this is one
    # statement and not three.
    confirmed = status in ("confirmed", "in_stay", "completed", "no_show")

    await db.execute(
        text("""
            INSERT INTO bookings
                (id, reference, status, guest_id, property_id, vendor_id, room_type_id,
                 property_name, room_type_name, cancellation_policy,
                 check_in, check_out, stay_range, timezone,
                 adults, children, infants, rooms,
                 guest_name, guest_email, guest_phone,
                 accommodation_minor, extra_guest_minor, cleaning_fee_minor,
                 tax_minor, platform_fee_minor, total_minor, currency,
                 nightly_rates, source, payment_id, confirmed_at)
            VALUES
                (:id, :ref, :status, :guest, :prop, :vendor, :rt,
                 'The Test House', 'Garden Room', 'moderate',
                 :check_in, :check_out,
                 daterange(:check_in, :check_out, '[)'),
                 'Asia/Kolkata',
                 2, 0, 0, 1,
                 'Test Guest', 'guest@example.com', '+919876500000',
                 -- `ck_bookings_total_is_sum_of_parts`: the total is
                 -- accommodation + extra guests + cleaning + tax + platform
                 -- fee. 900000 + 0 + 0 + 108000 + 108000 = 1116000.
                 900000, 0, 0, 108000, 108000, 1116000, 'INR',
                 '[]'::jsonb, 'web', :payment_id, :confirmed_at)
        """),
        {
            "id": booking_id,
            "ref": reference,
            "payment_id": f"pay_{uuid.uuid4().hex[:18]}" if confirmed else None,
            "confirmed_at": datetime.now(UTC) if confirmed else None,
            "status": status,
            "guest": guest_id,
            "prop": listing.property_id,
            "vendor": listing.vendor_id,
            "rt": listing.room_type_id,
            # Computed here rather than as `CURRENT_DATE - :days` in SQL:
            # asyncpg types a bare parameter as `unknown`, and Postgres then
            # cannot resolve which `daterange(...)` overload is meant.
            "check_in": check_in,
            "check_out": check_out,
        },
    )
    await db.commit()
    return booking_id
