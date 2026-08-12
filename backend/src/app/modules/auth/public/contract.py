"""What the auth module lets other modules do.

Deliberately one operation. Auth owns identity, and identity is the thing you
least want other modules reaching into: a module that can write ``users`` can
grant itself roles. So the boundary is not "here is the user table", it is
"here is the one state change another module is entitled to ask for".

:class:`VendorAccess` exists because becoming a vendor is a fact that starts in
the vendor module and has to land on the identity: the access token carries
``vendor_id`` and ``roles``, and every vendor endpoint authorises against those
two. Before this contract existed, a vendor could register, be approved, and
still get ``404 VENDOR_NOT_FOUND`` from their own dashboard for the rest of
time — the two halves of the fact were never joined.
"""

from __future__ import annotations

import uuid
from typing import Protocol


class VendorOwnershipConflictError(Exception):
    """The user is already the owner of a *different* vendor.

    Never expected. It means two vendor rows claim the same person, which the
    ``uq_vendors_owner`` constraint should have prevented — so this raises
    rather than overwriting, because silently moving someone's identity from
    one business to another hands them another vendor's bookings and payouts.
    """


class VendorAccess(Protocol):
    """Join a vendor to the identity that owns it."""

    async def grant(self, *, user_id: uuid.UUID, vendor_id: uuid.UUID) -> None:
        """Stamp ``vendor_id`` on the user and give them the vendor role.

        Idempotent: registering twice, or replaying the same event, is a no-op
        rather than a duplicate-key error.

        Runs in the caller's transaction. If vendor registration rolls back,
        so does the grant — a user holding the vendor role with no vendor row
        behind it would fail every lookup in a way nothing reports.

        The change reaches the client on their next token refresh, not
        instantly: the access token they are holding was minted before the
        grant. That is the honest behaviour for a stateless token, and the
        refresh is at most a few minutes away.
        """
        ...
