"""Support and vendor rules.

Two properties dominate: an internal note must never reach the guest it is
about, and approving a vendor authorises payouts to a real bank account.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.support.domain import errors as support_errors
from app.modules.support.domain.entities import Ticket
from app.modules.support.domain.value_objects import (
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.modules.vendor.domain import errors as vendor_errors
from app.modules.vendor.domain.entities import Vendor
from app.modules.vendor.domain.value_objects import VendorStatus

pytestmark = pytest.mark.unit

NOW = datetime.now(UTC).replace(microsecond=0)
AGENT = uuid.uuid4()
GUEST = uuid.uuid4()


def open_ticket(**overrides: object) -> Ticket:
    defaults: dict[str, object] = {
        "reference": "SUP-ABC234",
        "requester_id": GUEST,
        "requester_name": "Priya Sharma",
        "requester_email": "priya@example.com",
        "subject": "Cannot get into the villa",
        "body": "The door code does not work and I am standing outside.",
        "category": TicketCategory.CHECK_IN,
        "now": NOW,
    }
    return Ticket.open(**(defaults | overrides))  # type: ignore[arg-type]


class TestInternalNotes:
    def test_a_guest_never_sees_an_internal_note(self) -> None:
        """The single most important property in the module.

        An internal note reads "guest is lying, see previous refund". Rendering
        one to the guest it is about is unrecoverable.
        """
        ticket = open_ticket()
        ticket.add_message(
            author_id=AGENT,
            author_name="Support",
            body="Guest already refunded twice — watch for abuse.",
            now=NOW,
            from_staff=True,
            is_internal=True,
        )

        visible = ticket.visible_messages(include_internal=False)
        assert len(visible) == 1
        assert all("abuse" not in m.body for m in visible)
        assert len(ticket.visible_messages(include_internal=True)) == 2

    def test_a_guest_cannot_author_an_internal_note(self) -> None:
        ticket = open_ticket()
        message = ticket.add_message(
            author_id=GUEST,
            author_name="Priya",
            body="Please hurry",
            now=NOW,
            from_staff=False,
            is_internal=True,  # requested, and ignored
        )
        assert message.is_internal is False

    def test_an_internal_note_does_not_stop_the_sla_clock(self) -> None:
        """Otherwise a team looks compliant while nobody has actually replied."""
        ticket = open_ticket()
        ticket.add_message(
            author_id=AGENT,
            author_name="Support",
            body="Checking the lock log.",
            now=NOW,
            from_staff=True,
            is_internal=True,
        )
        assert ticket.first_responded_at is None
        assert ticket.status is TicketStatus.OPEN

        ticket.add_message(
            author_id=AGENT,
            author_name="Support",
            body="New code is 4417.",
            now=NOW + timedelta(minutes=5),
            from_staff=True,
        )
        assert ticket.first_responded_at == NOW + timedelta(minutes=5)
        assert ticket.status is TicketStatus.WAITING_ON_GUEST


class TestTicketFlow:
    def test_priority_is_derived_from_the_category(self) -> None:
        """Everything would be urgent if guests set it themselves — and then
        nothing would be."""
        assert open_ticket().priority is TicketPriority.URGENT
        assert open_ticket(category=TicketCategory.OTHER).priority is TicketPriority.LOW

    def test_a_guest_reply_reopens_a_resolved_ticket(self) -> None:
        ticket = open_ticket()
        ticket.resolve(resolution="Door code reissued.", now=NOW)
        assert ticket.status is TicketStatus.RESOLVED

        ticket.add_message(
            author_id=GUEST,
            author_name="Priya",
            body="Still not working.",
            now=NOW + timedelta(hours=1),
            from_staff=False,
        )
        # A resolved ticket the guest replies to is not resolved, whatever the
        # queue would prefer.
        assert ticket.status is TicketStatus.IN_PROGRESS
        assert ticket.resolved_at is None

    def test_resolving_requires_a_note(self) -> None:
        with pytest.raises(support_errors.InvalidTicketError):
            open_ticket().resolve(resolution="   ", now=NOW)

    def test_a_closed_ticket_takes_no_more_messages(self) -> None:
        ticket = open_ticket()
        ticket.resolve(resolution="Fixed.", now=NOW)
        ticket.close(now=NOW)
        with pytest.raises(support_errors.TicketClosedError):
            ticket.add_message(
                author_id=GUEST,
                author_name="Priya",
                body="hello",
                now=NOW,
                from_staff=False,
            )

    def test_breach_is_measured_from_the_priority_target(self) -> None:
        ticket = open_ticket()  # urgent → one hour
        assert not ticket.is_breaching(NOW + timedelta(minutes=30))
        assert ticket.is_breaching(NOW + timedelta(hours=2))

        ticket.add_message(
            author_id=AGENT,
            author_name="Support",
            body="On it.",
            now=NOW + timedelta(minutes=10),
            from_staff=True,
        )
        # Answered, so it can no longer breach however long it stays open.
        assert not ticket.is_breaching(NOW + timedelta(days=3))


class TestVendorApproval:
    def make(self, **overrides: object) -> Vendor:
        defaults: dict[str, object] = {
            "owner_user_id": uuid.uuid4(),
            "legal_name": "Anjuna Stays Private Limited",
            "display_name": "Anjuna Stays",
            "contact_email": "host@example.com",
            "contact_phone": "+919876500001",
            "pan": "ABCDE1234F",
        }
        return Vendor.register(**(defaults | overrides))  # type: ignore[arg-type]

    def test_approval_requires_a_pan(self) -> None:
        """It is what TDS is filed against; approving without it creates a
        payable finance cannot legally settle."""
        vendor = self.make(pan=None)
        with pytest.raises(vendor_errors.MissingVendorDocumentError):
            vendor.approve(by=AGENT, now=NOW)

    def test_approval_authorises_publishing(self) -> None:
        vendor = self.make()
        assert not vendor.can_publish
        vendor.approve(by=AGENT, now=NOW)
        assert vendor.can_publish
        assert vendor.status is VendorStatus.APPROVED

    def test_payouts_need_a_bank_account_as_well(self) -> None:
        vendor = self.make()
        vendor.approve(by=AGENT, now=NOW)
        assert not vendor.can_receive_payouts
        vendor.update_bank(last4="4417", ifsc="HDFC0001234")
        assert vendor.can_receive_payouts

    def test_only_the_last_four_digits_are_kept(self) -> None:
        vendor = self.make()
        with pytest.raises(vendor_errors.InvalidVendorDetailsError):
            vendor.update_bank(last4="123456789012", ifsc="HDFC0001234")

    def test_rejection_requires_a_reason(self) -> None:
        with pytest.raises(vendor_errors.InvalidVendorDetailsError):
            self.make().reject(by=AGENT, reason="  ")

    def test_a_rejected_vendor_is_terminal(self) -> None:
        """They apply again rather than being revived, so the rejection stays
        on the record."""
        vendor = self.make()
        vendor.reject(by=AGENT, reason="Documents did not match.")
        with pytest.raises(vendor_errors.InvalidVendorTransitionError):
            vendor.approve(by=AGENT, now=NOW)

    def test_commission_rounds_down_to_the_vendor(self) -> None:
        """A platform that rounds its own fee up on every booking collects a
        fraction it never agreed to, and vendors do check."""
        vendor = self.make()
        vendor.set_commission(1500)
        # 15% of ₹1,000.07 = ₹150.0105 → 15001 paise, not 15002.
        assert vendor.commission_on(100_007) == 15_001

    def test_commission_is_bounded(self) -> None:
        vendor = self.make()
        with pytest.raises(vendor_errors.InvalidVendorDetailsError):
            vendor.set_commission(5000)

    def test_a_malformed_gstin_is_refused_at_the_door(self) -> None:
        with pytest.raises(vendor_errors.InvalidVendorDetailsError):
            self.make(gstin="NOTAGSTIN")

    def test_suspension_requires_a_reason_and_holds_payouts(self) -> None:
        vendor = self.make()
        vendor.approve(by=AGENT, now=NOW)
        vendor.update_bank(last4="4417", ifsc="HDFC0001234")

        with pytest.raises(vendor_errors.InvalidVendorDetailsError):
            vendor.suspend(by=AGENT, reason="")

        vendor.suspend(by=AGENT, reason="Under investigation.")
        assert not vendor.can_publish
        assert not vendor.can_receive_payouts
