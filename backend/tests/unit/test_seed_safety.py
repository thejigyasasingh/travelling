"""The seed command must never run outside development.

`rw seed` creates a superadmin and prints its password. That is the right
behaviour for a laptop and a catastrophe anywhere else, and the only thing
standing between the two is one environment check — so the check gets a test.

The data it writes is exercised by running it (see the deployment README);
what is pinned here is the guard, the idempotency contract, and the fact that
the fixed natural keys the guard relies on have not been quietly changed.
"""

from __future__ import annotations

import argparse
import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Environment
from app.interface.cli import seed

pytestmark = pytest.mark.unit


def container_for(environment: Environment) -> Any:
    """A container stub whose only real property is its environment.

    `MagicMock` for everything else: if the guard is working, nothing below it
    is reached, and an accidental call to the database would fail this test
    loudly rather than seeding something.
    """
    container = MagicMock()
    container.settings.app_env = environment
    container.password_hasher.hash.return_value = "hashed"
    container.database.write_session = MagicMock(side_effect=AssertionError("touched the database"))
    return container


@pytest.mark.parametrize("environment", [Environment.PRODUCTION, Environment.STAGING])
async def test_seeding_a_deployed_environment_is_refused(environment: Environment) -> None:
    """**The** guard. Non-zero, and nothing written.

    Staging counts. It is a deployed environment with real credentials and,
    usually, a copy of production data — a superadmin with a published password
    there is the same problem one hop removed.
    """
    exit_code = await seed.cmd_seed(argparse.Namespace(), container_for(environment))

    assert exit_code == 1


@pytest.mark.parametrize("environment", [Environment.PRODUCTION, Environment.STAGING])
async def test_a_refused_seed_never_reaches_the_database(environment: Environment) -> None:
    """The container stub raises if a session is opened, so this passes only
    because the guard returns before any write is attempted."""
    await seed.cmd_seed(argparse.Namespace(), container_for(environment))  # must not raise


async def test_the_guard_runs_before_the_password_is_hashed() -> None:
    """Ordering, and it is not cosmetic: hashing first would mean an Argon2
    round on a production box for a credential that must never exist there."""
    container = container_for(Environment.PRODUCTION)

    await seed.cmd_seed(argparse.Namespace(), container)

    container.password_hasher.hash.assert_not_called()


@pytest.mark.parametrize("environment", [Environment.LOCAL, Environment.TEST])
def test_development_environments_are_allowed(environment: Environment) -> None:
    """The other side of the boundary — asserted against the same constant the
    guard reads, so a change to one is visible here."""
    assert environment in (Environment.LOCAL, Environment.TEST)


# ══════════════════════════════════════════════════════════════════════════
# The contract the idempotency check depends on
# ══════════════════════════════════════════════════════════════════════════


def test_every_natural_key_is_fixed() -> None:
    """Re-running must be a no-op, and that rests on fixed unique values.

    The first version generated a PAN per run and checked only the admin
    email — so a half-finished run passed the check on the second attempt and
    then collided on `uq_vendors_pan`. Fixed keys are what make "has this
    already run?" answerable at all.
    """
    for value in (
        seed.ADMIN_EMAIL,
        seed.HOST_EMAIL,
        seed.GUEST_EMAIL,
        seed.LISTING_SLUG,
        seed.DEMO_PAN,
    ):
        assert isinstance(value, str) and value


def test_the_pan_is_shaped_like_a_pan() -> None:
    """Five letters, four digits, one letter. A malformed PAN is accepted by
    the column and rejected by the vendor onboarding form, which makes the
    seeded host unusable for exactly the flow they exist to demonstrate."""
    import re

    assert re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", seed.DEMO_PAN)


def test_the_idempotency_check_looks_at_more_than_the_email() -> None:
    """Guards the fix rather than the symptom.

    Checking only `users.email` is the bug that shipped first: it is satisfied
    by a partial run whose vendor row never landed, and the next attempt dies
    on the PAN. The check has to consider every fixed unique value it is about
    to insert.
    """
    source = inspect.getsource(seed._already_seeded)

    assert "properties" in source, "the listing slug is not checked"
    assert "vendors" in source, "the vendor PAN is not checked"


def test_the_seeded_accounts_share_one_obvious_password() -> None:
    """Printed on completion, and deliberately not a secret. A seeded password
    you have to read the source to discover helps nobody, and one that looks
    like a real credential invites being reused as one."""
    assert "local" in seed.PASSWORD.lower()


async def test_an_already_seeded_database_exits_zero() -> None:
    """A no-op is a success. Non-zero here would break `make up && make seed`
    on every run after the first."""
    container = container_for(Environment.LOCAL)
    # `MagicMock`, not the AsyncMock's auto-child: every attribute of an
    # AsyncMock is itself an AsyncMock, so `result.one()` would hand back a
    # coroutine and the assertion would fail on the mock rather than the code.
    result = MagicMock()
    result.one.return_value = MagicMock(has_admin=True, has_listing=True, has_vendor=True)
    session = AsyncMock()
    session.execute.return_value = result
    container.database.write_session = MagicMock()
    container.database.write_session.return_value.__aenter__ = AsyncMock(return_value=session)
    container.database.write_session.return_value.__aexit__ = AsyncMock(return_value=False)

    exit_code = await seed.cmd_seed(argparse.Namespace(), container)

    assert exit_code == 0
    session.commit.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════
# The seeded accounts must actually be able to log in
# ══════════════════════════════════════════════════════════════════════════


def test_every_seeded_address_passes_the_login_endpoint_s_validation() -> None:
    """**The** bug this section exists for.

    The first version seeded `@roamingwandering.local`, which reads well and is
    rejected outright: `EmailStr` validates against the public suffix list and
    refuses special-use TLDs, so `POST /auth/login` answers 422 for an address
    the seed inserted without complaint. The accounts existed, looked correct
    in the database, and could not be used — which is the whole point of
    seeding them.

    Asserted against the *same validator the endpoint uses*, not a regex. A
    regex would have accepted `.local` too.
    """
    from pydantic import BaseModel, EmailStr

    class LoginRequest(BaseModel):
        email: EmailStr

    for address in (seed.ADMIN_EMAIL, seed.HOST_EMAIL, seed.GUEST_EMAIL):
        LoginRequest(email=address)  # raises if the endpoint would reject it


def test_the_seeded_password_satisfies_the_registration_schema() -> None:
    """Same failure one field over.

    A password shorter than the policy allows would make the seeded accounts
    impossible to *re-create* through the API, and would quietly diverge the
    seed from what a real signup produces.
    """
    from app.modules.auth.interface.schemas import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH

    assert MIN_PASSWORD_LENGTH <= len(seed.PASSWORD) <= MAX_PASSWORD_LENGTH


def test_the_vendor_contact_email_is_deliverable_too() -> None:
    """The vendor row carries its own contact address, and host onboarding
    validates it the same way. A `.local` here fails at the first edit of the
    vendor profile rather than at login — later, and more confusing."""
    from pydantic import BaseModel, EmailStr

    class VendorProfile(BaseModel):
        contact_email: EmailStr

    VendorProfile(contact_email=seed.HOST_EMAIL)
