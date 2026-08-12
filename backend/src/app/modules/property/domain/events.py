"""Property domain events.

The consumers that matter, and why each event exists:

* **search** — reindexes on publish, edit and unpublish. This is what keeps the
  read model current without the property module knowing a search index
  exists.
* **media** — generates thumbnails and runs moderation on newly uploaded
  images.
* **notification** — tells a vendor their listing went live or was rejected.
* **analytics** — funnel from draft to first booking, which is the number that
  says whether onboarding works.

``PropertyPublished`` and ``PropertyUnpublished`` are separate events rather
than one ``PropertyStatusChanged`` carrying a string. A consumer that only
cares about removal should not have to parse a status field and guess — and the
outbox relay can route them to different queues.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from app.shared.domain.events import DomainEvent

AGGREGATE = "property"


@dataclass(frozen=True, kw_only=True)
class PropertyCreated(DomainEvent):
    event_type: ClassVar[str] = "property.created"
    aggregate_type: ClassVar[str] = AGGREGATE

    vendor_id: uuid.UUID
    name: str
    property_type: str
    city: str
    country_code: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "vendor_id": str(self.vendor_id),
            "name": self.name,
            "property_type": self.property_type,
            "city": self.city,
            "country_code": self.country_code,
        }


@dataclass(frozen=True, kw_only=True)
class PropertyUpdated(DomainEvent):
    """Carries which fields changed, not the new values.

    A consumer that needs the current state reads it; one that only needs to
    know whether to reindex checks the field list. Shipping the whole entity
    would put the full address — including the exact location we deliberately
    hide from unbooked guests — into the outbox, Redis and every worker log.
    """

    event_type: ClassVar[str] = "property.updated"
    aggregate_type: ClassVar[str] = AGGREGATE

    vendor_id: uuid.UUID
    changed_fields: list[str]
    requires_reindex: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "vendor_id": str(self.vendor_id),
            "changed_fields": self.changed_fields,
            "requires_reindex": self.requires_reindex,
        }


@dataclass(frozen=True, kw_only=True)
class PropertySubmittedForReview(DomainEvent):
    event_type: ClassVar[str] = "property.submitted_for_review"
    aggregate_type: ClassVar[str] = AGGREGATE

    vendor_id: uuid.UUID
    name: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "vendor_id": str(self.vendor_id),
            "name": self.name,
        }


@dataclass(frozen=True, kw_only=True)
class PropertyPublished(DomainEvent):
    """The listing is now sellable. The search index must reflect it promptly —
    a vendor who publishes and cannot find themselves in search assumes the
    platform is broken."""

    event_type: ClassVar[str] = "property.published"
    aggregate_type: ClassVar[str] = AGGREGATE

    vendor_id: uuid.UUID
    name: str
    city: str
    property_type: str
    published_by: uuid.UUID | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "vendor_id": str(self.vendor_id),
            "name": self.name,
            "city": self.city,
            "property_type": self.property_type,
            "published_by": str(self.published_by) if self.published_by else None,
        }


@dataclass(frozen=True, kw_only=True)
class PropertyUnpublished(DomainEvent):
    """Must be removed from search **immediately**.

    A guest booking a listing that was withdrawn ten minutes ago is a
    cancellation, a refund and an angry review. This event is routed to the
    critical queue for that reason.
    """

    event_type: ClassVar[str] = "property.unpublished"
    aggregate_type: ClassVar[str] = AGGREGATE

    vendor_id: uuid.UUID
    reason: str
    by_admin: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "vendor_id": str(self.vendor_id),
            "reason": self.reason,
            "by_admin": self.by_admin,
        }


@dataclass(frozen=True, kw_only=True)
class PropertyRejected(DomainEvent):
    event_type: ClassVar[str] = "property.rejected"
    aggregate_type: ClassVar[str] = AGGREGATE

    vendor_id: uuid.UUID
    reason: str
    reviewed_by: uuid.UUID | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "vendor_id": str(self.vendor_id),
            "reason": self.reason,
            "reviewed_by": str(self.reviewed_by) if self.reviewed_by else None,
        }


@dataclass(frozen=True, kw_only=True)
class RoomTypeAdded(DomainEvent):
    event_type: ClassVar[str] = "property.room_type.added"
    aggregate_type: ClassVar[str] = AGGREGATE

    room_type_id: uuid.UUID
    name: str
    base_rate_minor: int
    currency: str
    total_units: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "room_type_id": str(self.room_type_id),
            "name": self.name,
            "base_rate_minor": self.base_rate_minor,
            "currency": self.currency,
            "total_units": self.total_units,
        }


@dataclass(frozen=True, kw_only=True)
class RoomTypeRemoved(DomainEvent):
    event_type: ClassVar[str] = "property.room_type.removed"
    aggregate_type: ClassVar[str] = AGGREGATE

    room_type_id: uuid.UUID

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "room_type_id": str(self.room_type_id),
        }


@dataclass(frozen=True, kw_only=True)
class RatesChanged(DomainEvent):
    """Cached search results and any "from ₹X" figure are now stale."""

    event_type: ClassVar[str] = "property.rates.changed"
    aggregate_type: ClassVar[str] = AGGREGATE

    room_type_id: uuid.UUID
    from_date: str | None
    to_date: str | None
    dates_affected: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "room_type_id": str(self.room_type_id),
            "from_date": self.from_date,
            "to_date": self.to_date,
            "dates_affected": self.dates_affected,
        }


@dataclass(frozen=True, kw_only=True)
class AvailabilityChanged(DomainEvent):
    """A vendor opened or closed dates.

    Search caches keyed on those dates must be dropped; serving a cached
    "available" for a date the vendor just blocked produces a booking that
    cannot be honoured.
    """

    event_type: ClassVar[str] = "property.availability.changed"
    aggregate_type: ClassVar[str] = AGGREGATE

    room_type_id: uuid.UUID
    from_date: str
    to_date: str
    blocked: bool | None
    dates_affected: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "room_type_id": str(self.room_type_id),
            "from_date": self.from_date,
            "to_date": self.to_date,
            "blocked": self.blocked,
            "dates_affected": self.dates_affected,
        }


@dataclass(frozen=True, kw_only=True)
class ImagesUploaded(DomainEvent):
    """Triggers thumbnail generation and automated moderation.

    Moderation is not optional: uploaded photos are the single largest source
    of stolen content and of images that do not depict the property at all.
    """

    event_type: ClassVar[str] = "property.images.uploaded"
    aggregate_type: ClassVar[str] = AGGREGATE

    image_ids: list[str]
    storage_keys: list[str]

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "image_ids": self.image_ids,
            "storage_keys": self.storage_keys,
        }


@dataclass(frozen=True, kw_only=True)
class ImageRemoved(DomainEvent):
    """The object is deleted from S3 by the consumer, not inline.

    Deleting inline would put a network call inside the request's transaction —
    and if the transaction then rolled back, the object would be gone while the
    row survived.
    """

    event_type: ClassVar[str] = "property.image.removed"
    aggregate_type: ClassVar[str] = AGGREGATE

    image_id: uuid.UUID
    storage_key: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "property_id": str(self.aggregate_id),
            "image_id": str(self.image_id),
            "storage_key": self.storage_key,
        }
