"""Review events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

from app.shared.domain.events import DomainEvent

AGGREGATE = "review"


@dataclass(frozen=True, kw_only=True)
class ReviewPublished(DomainEvent):
    """A new review. The property's rating is recomputed from this."""

    event_type: ClassVar[str] = "review.published"
    aggregate_type: ClassVar[str] = AGGREGATE

    property_id: uuid.UUID
    vendor_id: uuid.UUID
    booking_id: uuid.UUID
    rating: int
    author_name: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "review_id": str(self.aggregate_id),
            "property_id": str(self.property_id),
            "vendor_id": str(self.vendor_id),
            "booking_id": str(self.booking_id),
            "rating": self.rating,
            "author_name": self.author_name,
        }


@dataclass(frozen=True, kw_only=True)
class ReviewEdited(DomainEvent):
    """The guest changed what they wrote.

    Carries no content. Consumers that care re-read the review, which keeps
    the outbox row small and — more importantly — keeps review text out of a
    table that is replicated to a queue and retained for redelivery.
    """

    event_type: ClassVar[str] = "review.edited"
    aggregate_type: ClassVar[str] = AGGREGATE

    property_id: uuid.UUID
    rating: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "review_id": str(self.aggregate_id),
            "property_id": str(self.property_id),
            "rating": self.rating,
        }


@dataclass(frozen=True, kw_only=True)
class HostReplied(DomainEvent):
    """Carries a preview only — the full text stays in the database.

    An event travels through the outbox, the broker and every consumer's logs,
    and a host's reply can contain whatever they chose to type about a guest.
    """

    event_type: ClassVar[str] = "review.host_replied"
    aggregate_type: ClassVar[str] = AGGREGATE

    property_id: uuid.UUID
    vendor_id: uuid.UUID
    author_id: uuid.UUID
    preview: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "review_id": str(self.aggregate_id),
            "property_id": str(self.property_id),
            "vendor_id": str(self.vendor_id),
            "author_id": str(self.author_id),
            "preview": self.preview,
        }


@dataclass(frozen=True, kw_only=True)
class ReviewRemoved(DomainEvent):
    event_type: ClassVar[str] = "review.removed"
    aggregate_type: ClassVar[str] = AGGREGATE

    property_id: uuid.UUID
    rating: int
    reason: str
    removed_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "review_id": str(self.aggregate_id),
            "property_id": str(self.property_id),
            "rating": self.rating,
            "reason": self.reason,
            "removed_at": self.removed_at.isoformat(),
        }
