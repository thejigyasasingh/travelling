"""Development seed data.

A fresh database has roles, permissions and amenities — and no people. So a
clone of this repository boots to a login screen nobody can get past, and the
first thing anyone evaluating it does is give up or write four hand-authored
`INSERT`s across three tables. That is the entire reason this file exists.

**It breaks the rule the rest of the CLI keeps, deliberately.** Every other
command drives the real use cases; this one writes SQL directly. It has to:
approving a vendor, granting an admin role and publishing a listing are all
staff actions guarded by permissions nobody holds yet, and the honest way
through that chicken-and-egg is to say so rather than to build a back door into
the application layer that then exists in production.

Which is why it **refuses to run outside local and test**. Not a warning — a
non-zero exit. A seed command that can run against production is one keystroke
from creating a superadmin with a published password in a real environment.

Idempotent. Running it twice does nothing the second time, so it is safe in a
`make up` chain and safe to re-run after a partial failure.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from typing import Any, Final

from sqlalchemy import text

from app.container import Container
from app.core.config import Environment
from app.core.logging import get_logger

logger = get_logger("cli.seed")

#: Long enough for the password policy, obvious enough that nobody mistakes it
#: for a real credential. Printed on completion — a seeded account whose
#: password you have to read the source to discover helps nobody.
# S105 suppressed on the line: this genuinely is a hardcoded credential, and
# that is the point. `cmd_seed` exits non-zero outside local and test, which
# is the control that makes it safe — not the absence of a literal here.
PASSWORD: Final = "DevPassword123!local"  # noqa: S105

#: `example.com`, not `.local` or `.test`.
#:
#: Both of those read better and **neither can log in**. `EmailStr` validates
#: against the public suffix list and rejects special-use TLDs, so the login
#: endpoint answers 422 for an address the seed happily inserted — the account
#: exists, looks correct in the database, and is unusable.
#:
#: `example.com` is reserved by RFC 2606 for exactly this, and it is what the
#: test fixtures already use for the same reason.
ADMIN_EMAIL: Final = "admin@example.com"
HOST_EMAIL: Final = "host@example.com"
GUEST_EMAIL: Final = "guest@example.com"

#: Slug of the demo listing. Stable, so the seeded URL can be linked from the
#: README and stays valid across re-seeds.
LISTING_SLUG: Final = "sea-breeze-villa-anjuna"

#: Fixed, and therefore unique-constrained. A generated PAN would make re-runs
#: trivially safe and the seeded data unrecognisable; a fixed one means
#: `uq_vendors_pan` is what tells us a previous run happened.
DEMO_PAN: Final = "AAAPZ1234C"


async def _already_seeded(session: Any) -> bool:
    """Whether a previous run left anything behind.

    Checks the **listing slug and the vendor PAN**, not just the admin email.
    Both are unique constraints with fixed values, so a half-finished earlier
    run — the admin created, the listing not — would otherwise pass an
    email-only check on the second attempt and then collide on
    `uq_vendors_pan`, which is exactly what happened the first time this ran.
    """
    row = (
        await session.execute(
            text(
                """
                SELECT
                  EXISTS (SELECT 1 FROM users WHERE email = :admin) AS has_admin,
                  EXISTS (SELECT 1 FROM properties WHERE slug = :slug) AS has_listing,
                  EXISTS (SELECT 1 FROM vendors WHERE pan = :pan) AS has_vendor
                """
            ),
            {"admin": ADMIN_EMAIL, "slug": LISTING_SLUG, "pan": DEMO_PAN},
        )
    ).one()
    return bool(row.has_admin or row.has_listing or row.has_vendor)


async def _create_user(
    session: Any,
    *,
    email: str,
    full_name: str,
    password_hash: str,
    roles: tuple[str, ...] = (),
) -> uuid.UUID:
    """A verified, active account.

    Verified on purpose: the point of seeding is to skip the parts a person
    evaluating the project does not need to perform. The verification flow
    itself has its own tests and its own Mailpit inbox.
    """
    user_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO users (id, email, full_name, password_hash, status,
                               email_verified_at, created_at)
            VALUES (:id, :email, :name, :hash, 'active', now(), now())
            """
        ),
        {"id": user_id, "email": email, "name": full_name, "hash": password_hash},
    )
    for role in roles:
        # The trigger from migration 0002 mirrors this onto `users.roles`,
        # which is what login reads into the token. Writing `users.roles`
        # directly would work until the next grant re-synced it away.
        await session.execute(
            text(
                "INSERT INTO user_roles (id, user_id, role_name, granted_at) "
                "VALUES (gen_random_uuid(), :user, :role, now()) "
                "ON CONFLICT ON CONSTRAINT uq_user_roles_user_role DO NOTHING"
            ),
            {"user": user_id, "role": role},
        )
    return user_id


async def _create_listing(session: Any, *, owner_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """An approved vendor with one published, bookable property.

    Every value here is chosen to satisfy a constraint rather than to look
    plausible:

    * `ck_vendors_approved_needs_evidence` — an approved vendor must carry both
      a PAN and an `approved_at`, because an approval with no record of when is
      a compliance gap.
    * `location` is a real point in Anjuna, because publishing requires a map
      location and distance search needs a `geography`.
    * inventory rows for ninety days, because without them every availability
      query returns nothing and the listing looks sold out.
    """
    vendor_id, property_id, room_type_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    await session.execute(
        text(
            """
            INSERT INTO vendors (id, owner_user_id, legal_name, display_name,
                                 contact_email, contact_phone, status, pan,
                                 approved_at, commission_bps)
            VALUES (:id, :owner, 'Sea Breeze Hospitality LLP', 'Sea Breeze Stays',
                    :email, '+919876500001', 'approved', :pan, now(), 1200)
            """
        ),
        {"id": vendor_id, "owner": owner_id, "email": HOST_EMAIL, "pan": DEMO_PAN},
    )
    await session.execute(
        text("UPDATE users SET vendor_id = :v WHERE id = :u"),
        {"v": vendor_id, "u": owner_id},
    )
    await session.execute(
        text(
            """
            INSERT INTO properties
                (id, vendor_id, name, slug, property_type, status, description,
                 currency, line1, city, state, country_code, postal_code,
                 location, cancellation_policy, max_guests, min_rate_minor,
                 instant_booking, amenity_codes, room_type_count, published_at)
            VALUES
                (:id, :vendor, 'Sea Breeze Villa', :slug, 'villa', 'published',
                 'A four-bedroom villa two minutes from Anjuna beach, with a '
                 'private pool, an outdoor kitchen and enough hammocks for '
                 'everyone. Seeded demo data.',
                 'INR', '1 Beach Road', 'Anjuna', 'Goa', 'IN', '403509',
                 ST_SetSRID(ST_MakePoint(73.74, 15.57), 4326)::geography,
                 'moderate', 8, 450000, true,
                 ARRAY['wifi','pool','kitchen','parking'], 2, now())
            """
        ),
        {"id": property_id, "vendor": vendor_id, "slug": LISTING_SLUG},
    )

    # Two room types, not one: a single-room property never exercises the
    # room picker, and the picker is where the pricing bugs live.
    for name, rate, units, room_id in (
        ("Garden Room", 450_000, 3, room_type_id),
        ("Pool Suite", 780_000, 1, uuid.uuid4()),
    ):
        await session.execute(
            text(
                """
                INSERT INTO room_types
                    (id, property_id, name, description, max_adults, max_children,
                     total_units, base_rate_minor, included_guests, min_nights)
                VALUES (:id, :prop, :name, 'A comfortable room.', 2, 2,
                        :units, :rate, 2, 1)
                """
            ),
            {"id": room_id, "prop": property_id, "name": name, "rate": rate, "units": units},
        )
        await session.execute(
            text(
                """
                INSERT INTO room_inventory (room_type_id, stay_date, units_total, units_booked)
                SELECT :rt, d::date, :units, 0
                  FROM generate_series(CURRENT_DATE, CURRENT_DATE + 180, '1 day') AS d
                ON CONFLICT DO NOTHING
                """
            ),
            {"rt": room_id, "units": units},
        )

    return vendor_id, property_id


async def cmd_seed(args: argparse.Namespace, container: Container) -> int:
    """Create the three accounts and one listing needed to see the product."""
    settings = container.settings

    if settings.app_env not in (Environment.LOCAL, Environment.TEST):
        # Loud, and non-zero. This command grants superadmin and prints the
        # password; the guard is the only thing between that and a real
        # environment.
        sys.stderr.write(
            f"refusing to seed: APP_ENV is {settings.app_env.value!r}.\n"
            "Seeding is for local and test only — it creates a superadmin "
            "with a published password.\n"
        )
        return 1

    hashed = container.password_hasher.hash(PASSWORD)

    async with container.database.write_session() as session:
        if await _already_seeded(session):
            # Not `--force`. Every natural key here is fixed — the PAN, the
            # slug, the phone — so "seed again anyway" can only ever collide.
            # A clean slate is `make clean`, which drops the volumes; that is
            # one documented path instead of two half-working ones.
            sys.stdout.write(
                "Already seeded — nothing to do.\n"
                "For a clean slate: make clean && make up && make seed\n"
            )
            _print_credentials()
            return 0

        await _create_user(
            session,
            email=ADMIN_EMAIL,
            full_name="Platform Admin",
            password_hash=hashed,
            roles=("support", "admin", "superadmin"),
        )
        host_id = await _create_user(
            session,
            email=HOST_EMAIL,
            full_name="Priya Nair",
            password_hash=hashed,
            roles=("vendor",),
        )
        await _create_user(
            session, email=GUEST_EMAIL, full_name="Sam Traveller", password_hash=hashed
        )
        await _create_listing(session, owner_id=host_id)
        await session.commit()

    logger.info("seeded", listing=LISTING_SLUG)
    _print_credentials()
    return 0


def _print_credentials() -> None:
    sys.stdout.write(
        f"""
Seeded. One password for all three accounts: {PASSWORD}

  Admin panel    http://localhost:5174   {ADMIN_EMAIL}
  Vendor portal  http://localhost:5175   {HOST_EMAIL}
  Customer site  http://localhost:5173   {GUEST_EMAIL}

  Demo listing   http://localhost:5173/stays/{LISTING_SLUG}
                 Two room types, 180 days of inventory, instant booking on.
"""
    )
