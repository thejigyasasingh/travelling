"""The vendor aggregate.

A vendor is the legal party the platform pays. That is why it is a first-class
entity rather than a role flag on a user: money moves to a *bank account*
belonging to a *registered business*, and both the approval that authorises
those payouts and the evidence behind it have to live somewhere auditable.

**Approval is a gate on money, not on visibility.** An unapproved vendor may
draft listings; nothing they own can be published, booked or paid out until a
human has seen their documents. Getting that backwards means paying an
unverified stranger.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Final

from app.modules.vendor.domain import errors
from app.modules.vendor.domain.events import (
    VendorApproved,
    VendorRegistered,
    VendorRejected,
    VendorSuspended,
)
from app.modules.vendor.domain.value_objects import VendorStatus
from app.shared.domain.entity import AggregateRoot

#: Legal transitions. Anything absent is refused — an approved vendor cannot
#: silently return to "pending" and quietly keep its payout authorisation.
_TRANSITIONS: Final[dict[VendorStatus, frozenset[VendorStatus]]] = {
    VendorStatus.PENDING: frozenset(
        {VendorStatus.UNDER_REVIEW, VendorStatus.APPROVED, VendorStatus.REJECTED}
    ),
    VendorStatus.UNDER_REVIEW: frozenset({VendorStatus.APPROVED, VendorStatus.REJECTED}),
    VendorStatus.APPROVED: frozenset({VendorStatus.SUSPENDED}),
    VendorStatus.SUSPENDED: frozenset({VendorStatus.APPROVED, VendorStatus.REJECTED}),
    # Terminal. A rejected applicant registers again rather than being revived,
    # so the rejection stays on the record.
    VendorStatus.REJECTED: frozenset(),
}

#: 15 characters: 2 state + 10 PAN + 1 entity + 1 'Z' + 1 check digit.
_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
_PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

#: The platform's cut, in basis points. A default rather than a constant
#: because it is negotiated per vendor for volume.
DEFAULT_COMMISSION_BPS: Final = 1500  # 15%
MAX_COMMISSION_BPS: Final = 3000


class Vendor(AggregateRoot):
    """A business that lists properties on the platform."""

    __slots__ = (
        "approved_at",
        "approved_by",
        "bank_account_last4",
        "bank_ifsc",
        "commission_bps",
        "contact_email",
        "contact_phone",
        "display_name",
        "gstin",
        "legal_name",
        "owner_user_id",
        "pan",
        "rejection_reason",
        "status",
        "suspension_reason",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        owner_user_id: uuid.UUID,
        legal_name: str,
        display_name: str,
        contact_email: str,
        contact_phone: str,
        status: VendorStatus = VendorStatus.PENDING,
        gstin: str | None = None,
        pan: str | None = None,
        bank_account_last4: str | None = None,
        bank_ifsc: str | None = None,
        commission_bps: int = DEFAULT_COMMISSION_BPS,
        approved_at: datetime | None = None,
        approved_by: uuid.UUID | None = None,
        rejection_reason: str | None = None,
        suspension_reason: str | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version)
        self.owner_user_id = owner_user_id
        self.legal_name = legal_name
        self.display_name = display_name
        self.contact_email = contact_email
        self.contact_phone = contact_phone
        self.status = status
        self.gstin = gstin
        self.pan = pan
        self.bank_account_last4 = bank_account_last4
        self.bank_ifsc = bank_ifsc
        self.commission_bps = commission_bps
        self.approved_at = approved_at
        self.approved_by = approved_by
        self.rejection_reason = rejection_reason
        self.suspension_reason = suspension_reason

    @classmethod
    def register(
        cls,
        *,
        owner_user_id: uuid.UUID,
        legal_name: str,
        display_name: str,
        contact_email: str,
        contact_phone: str,
        gstin: str | None = None,
        pan: str | None = None,
    ) -> Vendor:
        """Start an application.

        Documents are validated for *shape* here and for authenticity by a
        human later. Rejecting a malformed GSTIN at the door saves a reviewer
        from a queue of typos; accepting a well-formed but fictitious one is
        what the review step is for.
        """
        if len(legal_name.strip()) < 3:
            raise errors.InvalidVendorDetailsError("legal_name", "is too short")
        if gstin is not None and not _GSTIN.match(gstin):
            raise errors.InvalidVendorDetailsError("gstin", "is not a valid GSTIN")
        if pan is not None and not _PAN.match(pan):
            raise errors.InvalidVendorDetailsError("pan", "is not a valid PAN")

        vendor = cls(
            owner_user_id=owner_user_id,
            legal_name=legal_name.strip(),
            display_name=display_name.strip() or legal_name.strip(),
            contact_email=contact_email.lower().strip(),
            contact_phone=contact_phone.strip(),
            gstin=gstin,
            pan=pan,
        )
        vendor.record(
            VendorRegistered(
                aggregate_id=vendor.id,
                owner_user_id=owner_user_id,
                legal_name=vendor.legal_name,
                contact_email=vendor.contact_email,
            )
        )
        return vendor

    # ── review ────────────────────────────────────────────────────────────

    def _transition(self, target: VendorStatus) -> None:
        if target not in _TRANSITIONS.get(self.status, frozenset()):
            raise errors.InvalidVendorTransitionError(self.status.value, target.value)
        self.status = target

    def begin_review(self) -> None:
        """Claimed by a reviewer, so two of them do not duplicate the work."""
        self._transition(VendorStatus.UNDER_REVIEW)

    def approve(self, *, by: uuid.UUID, now: datetime, commission_bps: int | None = None) -> None:
        """Authorise this vendor to publish and to be paid.

        Requires PAN on file: it is what the platform files TDS against, and
        approving without it creates a payable the finance team cannot legally
        settle at year end.
        """
        if self.pan is None:
            raise errors.MissingVendorDocumentError("pan")

        if commission_bps is not None:
            self.set_commission(commission_bps)

        self._transition(VendorStatus.APPROVED)
        self.approved_at = now
        self.approved_by = by
        self.rejection_reason = None
        self.suspension_reason = None
        self.record(
            VendorApproved(
                aggregate_id=self.id,
                owner_user_id=self.owner_user_id,
                legal_name=self.legal_name,
                contact_email=self.contact_email,
                commission_bps=self.commission_bps,
                approved_by=by,
            )
        )

    def reject(self, *, by: uuid.UUID, reason: str) -> None:
        if not reason.strip():
            # A rejection with no reason is one the applicant cannot act on,
            # and one support cannot defend three months later.
            raise errors.InvalidVendorDetailsError("reason", "is required to reject")
        self._transition(VendorStatus.REJECTED)
        self.rejection_reason = reason.strip()
        self.record(
            VendorRejected(
                aggregate_id=self.id,
                owner_user_id=self.owner_user_id,
                contact_email=self.contact_email,
                reason=self.rejection_reason,
                rejected_by=by,
            )
        )

    def suspend(self, *, by: uuid.UUID, reason: str) -> None:
        """Stop new bookings and hold payouts.

        Deliberately does **not** cancel existing bookings. Guests with a
        confirmed stay have a contract, and voiding it because the host is
        under investigation punishes the wrong party; those are unwound
        individually if it comes to that.
        """
        if not reason.strip():
            raise errors.InvalidVendorDetailsError("reason", "is required to suspend")
        self._transition(VendorStatus.SUSPENDED)
        self.suspension_reason = reason.strip()
        self.record(
            VendorSuspended(
                aggregate_id=self.id,
                owner_user_id=self.owner_user_id,
                reason=self.suspension_reason,
                suspended_by=by,
            )
        )

    def set_commission(self, bps: int) -> None:
        if not 0 <= bps <= MAX_COMMISSION_BPS:
            raise errors.InvalidVendorDetailsError(
                "commission_bps", f"must be between 0 and {MAX_COMMISSION_BPS}"
            )
        self.commission_bps = bps

    def update_bank(self, *, last4: str, ifsc: str) -> None:
        """Only the last four digits are ever stored.

        The full account number is never sent to this service — it goes to the
        payout provider directly. Storing it would put the platform in the
        business of guarding bank credentials, which is not a business worth
        being in.
        """
        if len(last4) != 4 or not last4.isdigit():
            raise errors.InvalidVendorDetailsError("bank_account_last4", "must be four digits")
        self.bank_account_last4 = last4
        self.bank_ifsc = ifsc.upper().strip()

    # ── rules other modules ask about ─────────────────────────────────────

    @property
    def can_publish(self) -> bool:
        """Approved vendors only. Checked by the property module before a
        listing goes live."""
        return self.status is VendorStatus.APPROVED

    @property
    def can_receive_payouts(self) -> bool:
        return self.status is VendorStatus.APPROVED and self.bank_account_last4 is not None

    def commission_on(self, amount_minor: int) -> int:
        """The platform's cut, rounded **down** to the paisa.

        Rounding down is deliberate: the remainder goes to the vendor. A
        platform that rounds its own fee up on every booking collects a
        fraction it never agreed to, and vendors do check.
        """
        return amount_minor * self.commission_bps // 10_000

    def as_audit(self) -> dict[str, Any]:
        return {
            "vendor_id": str(self.id),
            "legal_name": self.legal_name,
            "status": self.status.value,
            "commission_bps": self.commission_bps,
        }
