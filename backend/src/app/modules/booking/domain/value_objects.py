"""Booking value objects."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import ClassVar, Final, Self

#: Human-readable booking reference. Guests read these over the phone to
#: support agents, so the alphabet excludes characters that are misheard or
#: mistyped: 0/O, 1/I/L, 5/S, 8/B.
_ALPHABET: Final = "ACDEFGHJKMNPQRTUVWXY234679"
_REF_RE: Final = re.compile(r"^RW-\d{2}-[A-Z0-9]{8}$")


class BookingStatus(StrEnum):
    """Where a booking is in its life.

    ``PENDING_PAYMENT`` and ``PENDING_APPROVAL`` are both *holding inventory* —
    that is the whole point of them. A guest who has started checkout must not
    lose the room to someone else while entering their card details, and a
    vendor asked to approve a request must not have the dates sold from under
    them while they think.

    The cost is that abandoned checkouts sit on inventory until they expire,
    which is why the hold window is short and the expiry job runs often.
    """

    PENDING_PAYMENT = "pending_payment"
    PENDING_APPROVAL = "pending_approval"
    CONFIRMED = "confirmed"
    #: Guest arrived and the stay is underway. Set by a scheduled job on the
    #: check-in date; distinguishes "will happen" from "is happening" for
    #: cancellation rules and payouts.
    IN_STAY = "in_stay"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    #: The hold timed out. Distinct from `cancelled` because nobody chose it —
    #: it must not appear in a guest's cancellation history or count against
    #: them in fraud scoring.
    EXPIRED = "expired"
    REJECTED = "rejected"
    NO_SHOW = "no_show"

    @property
    def holds_inventory(self) -> bool:
        """True while this booking occupies units.

        The single source of truth for "should releasing inventory do
        anything?". Getting it wrong in either direction is severe: too narrow
        and inventory leaks, too broad and a double release creates phantom
        rooms.
        """
        return self in (
            BookingStatus.PENDING_PAYMENT,
            BookingStatus.PENDING_APPROVAL,
            BookingStatus.CONFIRMED,
            BookingStatus.IN_STAY,
            BookingStatus.NO_SHOW,  # the room was held; the guest simply never came
        )

    @property
    def is_terminal(self) -> bool:
        return self in (
            BookingStatus.COMPLETED,
            BookingStatus.CANCELLED,
            BookingStatus.EXPIRED,
            BookingStatus.REJECTED,
            BookingStatus.NO_SHOW,
        )

    @property
    def is_cancellable_by_guest(self) -> bool:
        return self in (
            BookingStatus.PENDING_PAYMENT,
            BookingStatus.PENDING_APPROVAL,
            BookingStatus.CONFIRMED,
        )


class CancelledBy(StrEnum):
    GUEST = "guest"
    VENDOR = "vendor"
    #: Fraud, a safety report, or a property removed from the platform.
    ADMIN = "admin"
    #: The hold expired, or payment failed. No human decided it, so it carries
    #: no penalty for either party.
    SYSTEM = "system"


class RefundStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class BookingReference:
    """``RW-26-K7M3QP2X``.

    Not the primary key. The id is a UUIDv7 the guest never sees; this is what
    goes in the confirmation email, on the invoice and into a support call.

    Random rather than sequential on purpose: a sequential reference tells a
    competitor exactly how many bookings the platform takes per day, and lets
    anyone enumerate other people's bookings by incrementing.
    """

    value: str

    def __post_init__(self) -> None:
        if not _REF_RE.match(self.value):
            msg = f"Malformed booking reference: {self.value!r}"
            raise ValueError(msg)

    @classmethod
    def generate(cls, when: date) -> Self:
        """~28^8 is about 3.8e11 combinations per year. Collisions are handled by a unique
        constraint and a retry rather than by hoping."""
        body = "".join(secrets.choice(_ALPHABET) for _ in range(8))
        return cls(f"RW-{when.strftime('%y')}-{body}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class GuestDetails:
    """Who is staying, as given at booking time.

    Captured on the booking rather than read from the user account, because
    people book for other people — a parent booking for a child, an assistant
    for an executive — and because the account's name may change afterwards
    while the invoice must not.
    """

    full_name: str
    email: str
    phone: str
    special_requests: str | None = None
    #: For a group booking; the lead guest is the account holder.
    additional_guests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.full_name.strip():
            msg = "Guest name is required"
            raise ValueError(msg)
        if "@" not in self.email:
            msg = "A valid guest email is required"
            raise ValueError(msg)
        if len(self.special_requests or "") > 1000:
            msg = "Special requests must be at most 1000 characters"
            raise ValueError(msg)

    @property
    def masked_email(self) -> str:
        local, _, domain = self.email.partition("@")
        return f"{local[0]}{'*' * max(len(local) - 1, 1)}@{domain}"


@dataclass(frozen=True, slots=True)
class StayWindow:
    """Check-in and check-out as *instants*, not dates.

    The refund engine needs "how long until check-in?" and a date alone cannot
    answer that — a booking checking in tomorrow at 14:00 is 30 hours away at
    08:00 today, not "1 day". Under a 24-hour flexible policy that is the
    difference between a full refund and none.

    The times come from the property and are stored on the booking, so a vendor
    later moving check-in from 14:00 to 15:00 cannot retroactively change what
    an existing guest is owed.
    """

    check_in_date: date
    check_out_date: date
    check_in_time: time
    check_out_time: time
    #: IANA zone of the property. A Goa property's 14:00 is not UTC 14:00, and
    #: refund deadlines computed in the wrong zone are off by hours in the
    #: direction that generates complaints.
    timezone: str = "Asia/Kolkata"

    def __post_init__(self) -> None:
        if self.check_out_date <= self.check_in_date:
            msg = "Check-out must be after check-in"
            raise ValueError(msg)

    @property
    def nights(self) -> int:
        return (self.check_out_date - self.check_in_date).days

    def check_in_at(self) -> datetime:
        """Naive local time at the property. Converted to UTC by the caller,
        which knows the zone database."""
        return datetime.combine(self.check_in_date, self.check_in_time)

    def hours_until_check_in(self, now_local: datetime) -> float:
        delta = self.check_in_at() - now_local
        return delta.total_seconds() / 3600

    def has_started(self, today: date) -> bool:
        return today >= self.check_in_date

    def has_ended(self, today: date) -> bool:
        return today >= self.check_out_date


@dataclass(frozen=True, slots=True)
class HoldWindow:
    """How long a booking may sit on inventory before paying.

    15 minutes is a deliberate compromise. Shorter and a guest fetching their
    card, or working through a bank's 3-D Secure flow on a slow connection,
    loses the room mid-checkout. Longer and a handful of abandoned carts can
    keep a small property's peak dates off the market for an hour.
    """

    # ClassVar, not a field: a bare annotation inside a dataclass becomes an
    # instance field with a default, which then makes `expires_at` a
    # non-default argument following a default one — a TypeError at import.
    DEFAULT_MINUTES: ClassVar[int] = 15
    #: Vendor approval is a human step measured in hours, not minutes.
    APPROVAL_HOURS: ClassVar[int] = 24

    expires_at: datetime

    @classmethod
    def for_payment(cls, now: datetime, minutes: int = DEFAULT_MINUTES) -> Self:
        return cls(now + timedelta(minutes=minutes))

    @classmethod
    def for_approval(cls, now: datetime, hours: int = APPROVAL_HOURS) -> Self:
        return cls(now + timedelta(hours=hours))

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def seconds_remaining(self, now: datetime) -> int:
        return max(0, int((self.expires_at - now).total_seconds()))
