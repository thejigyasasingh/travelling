"""The Property aggregate.

**Aggregate boundary.** ``Property`` owns its room types, its images and its
amenity set — those are edited together, must be consistent together
("published listings have at least one room type and a cover image"), and are
small and bounded.

It deliberately does **not** own its calendar. Inventory and rate overrides are
one row per room type per date; a two-year window across five room types is
~3,600 rows. Loading all of that to rename a property would be absurd, and
every booking would contend with every listing edit. The calendar is reached
through its own repository and guarded by its own rules in ``availability.py``.

The test for an aggregate boundary is "what must be transactionally consistent
with what". A property's name and its December rates do not need to change
together; a property's status and its room-type count do.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Final

from app.core.types.money import Money
from app.modules.property.domain import errors
from app.modules.property.domain.events import (
    ImageRemoved,
    ImagesUploaded,
    PropertyCreated,
    PropertyPublished,
    PropertyRejected,
    PropertySubmittedForReview,
    PropertyUnpublished,
    PropertyUpdated,
    RoomTypeAdded,
    RoomTypeRemoved,
)
from app.modules.property.domain.pricing import RateConfig
from app.modules.property.domain.value_objects import (
    Address,
    BedType,
    CancellationPolicy,
    GeoPoint,
    Occupancy,
    PropertyStatus,
    PropertyType,
    slugify,
)
from app.shared.domain.entity import AggregateRoot, Entity

MIN_IMAGES_TO_PUBLISH: Final = 3
MAX_IMAGES: Final = 50
MIN_DESCRIPTION_CHARS: Final = 120
MAX_ROOM_TYPES: Final = 30

#: Legal status moves. Anything absent is refused — see
#: :class:`InvalidStatusTransitionError` for why this is modelled explicitly.
_TRANSITIONS: Final[dict[PropertyStatus, frozenset[PropertyStatus]]] = {
    PropertyStatus.DRAFT: frozenset({PropertyStatus.PENDING_REVIEW}),
    PropertyStatus.PENDING_REVIEW: frozenset(
        {PropertyStatus.PUBLISHED, PropertyStatus.REJECTED, PropertyStatus.DRAFT}
    ),
    PropertyStatus.PUBLISHED: frozenset({PropertyStatus.UNPUBLISHED, PropertyStatus.SUSPENDED}),
    PropertyStatus.UNPUBLISHED: frozenset(
        {PropertyStatus.PUBLISHED, PropertyStatus.SUSPENDED, PropertyStatus.DRAFT}
    ),
    PropertyStatus.REJECTED: frozenset({PropertyStatus.PENDING_REVIEW, PropertyStatus.DRAFT}),
    # Only an admin lifts a suspension, and only back to unpublished — the
    # vendor then has to publish deliberately rather than being surprised by
    # their listing reappearing.
    PropertyStatus.SUSPENDED: frozenset({PropertyStatus.UNPUBLISHED}),
}


class RoomType(Entity):
    """A sellable unit class: "Deluxe Sea View", or the villa itself.

    An entity, not a value object: it has identity that survives a rename, and
    bookings and inventory rows reference it by id.
    """

    __slots__ = (
        "amenity_codes",
        "bed_type",
        "description",
        "max_occupancy",
        "name",
        "rate",
        "size_sqft",
        "total_units",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        name: str,
        rate: RateConfig,
        max_occupancy: Occupancy,
        total_units: int = 1,
        bed_type: BedType = BedType.DOUBLE,
        description: str | None = None,
        size_sqft: int | None = None,
        amenity_codes: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__(entity_id)
        if not name.strip():
            msg = "Room type name is required"
            raise ValueError(msg)
        if total_units < 1:
            msg = "A room type must have at least one unit"
            raise ValueError(msg)
        self.name = name.strip()
        self.rate = rate
        self.max_occupancy = max_occupancy
        self.total_units = total_units
        self.bed_type = bed_type
        self.description = description
        self.size_sqft = size_sqft
        self.amenity_codes = amenity_codes

    def accommodates(self, occupancy: Occupancy) -> bool:
        """Compared on billable guests only — infants do not count against the
        limit, which is what a family booking a room for two adults and a baby
        expects."""
        return occupancy.billable_guests <= self.max_occupancy.billable_guests

    @property
    def is_priced(self) -> bool:
        return self.rate.base_rate.is_positive


class PropertyImage(Entity):
    """One photo. The object itself lives in S3; this is the metadata.

    ``storage_key`` is server-generated (see ``infrastructure/storage/s3.py``)
    so a client cannot supply a path that traverses into another vendor's
    prefix.
    """

    __slots__ = ("alt_text", "caption", "height", "is_cover", "position", "storage_key", "width")

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        storage_key: str,
        position: int = 0,
        is_cover: bool = False,
        alt_text: str | None = None,
        caption: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        super().__init__(entity_id)
        self.storage_key = storage_key
        self.position = position
        self.is_cover = is_cover
        self.alt_text = alt_text
        self.caption = caption
        self.width = width
        self.height = height


class Property(AggregateRoot):
    """A listing."""

    __slots__ = (
        "address",
        "amenity_codes",
        "cancellation_policy",
        "check_in_from",
        "check_out_by",
        "city_id",
        "currency",
        "description",
        "house_rules",
        "images",
        "instant_booking",
        "location",
        "name",
        "property_type",
        "published_at",
        "rejection_reason",
        "review_average",
        "review_count",
        "room_types",
        "slug",
        "status",
        "vendor_id",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        vendor_id: uuid.UUID,
        name: str,
        property_type: PropertyType,
        address: Address,
        location: GeoPoint | None = None,
        description: str = "",
        currency: str = "INR",
        status: PropertyStatus = PropertyStatus.DRAFT,
        slug: str | None = None,
        city_id: uuid.UUID | None = None,
        amenity_codes: frozenset[str] = frozenset(),
        room_types: list[RoomType] | None = None,
        images: list[PropertyImage] | None = None,
        cancellation_policy: CancellationPolicy = CancellationPolicy.MODERATE,
        check_in_from: str = "14:00",
        check_out_by: str = "11:00",
        house_rules: list[str] | None = None,
        instant_booking: bool = True,
        review_average: float = 0.0,
        review_count: int = 0,
        published_at: datetime | None = None,
        rejection_reason: str | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version)
        self.vendor_id = vendor_id
        self.name = name.strip()
        self.property_type = property_type
        self.address = address
        self.location = location
        self.description = description
        self.currency = currency
        self.status = status
        self.slug = slug or slugify(name)
        self.city_id = city_id
        self.amenity_codes = amenity_codes
        self.room_types = room_types or []
        self.images = images or []
        self.cancellation_policy = cancellation_policy
        self.check_in_from = check_in_from
        self.check_out_by = check_out_by
        self.house_rules = house_rules or []
        self.instant_booking = instant_booking
        self.review_average = review_average
        self.review_count = review_count
        self.published_at = published_at
        self.rejection_reason = rejection_reason

    # ── creation ──────────────────────────────────────────────────────────

    @classmethod
    def draft(
        cls,
        *,
        vendor_id: uuid.UUID,
        name: str,
        property_type: PropertyType,
        address: Address,
        currency: str = "INR",
        description: str = "",
        location: GeoPoint | None = None,
        city_id: uuid.UUID | None = None,
    ) -> Property:
        """Start a listing.

        Created as a draft with almost nothing required. Demanding a complete
        listing up front is how vendor onboarding dies at step one — the
        completeness rules apply at :meth:`submit_for_review`, when the vendor
        is asking for something.
        """
        prop = cls(
            vendor_id=vendor_id,
            name=name,
            property_type=property_type,
            address=address,
            location=location,
            description=description,
            currency=currency,
            city_id=city_id,
        )
        prop.record(
            PropertyCreated(
                aggregate_id=prop.id,
                vendor_id=vendor_id,
                name=prop.name,
                property_type=property_type.value,
                city=address.city,
                country_code=address.country_code,
            )
        )
        return prop

    # ── access control ────────────────────────────────────────────────────

    def assert_owned_by(self, vendor_id: uuid.UUID | None) -> None:
        """Multi-tenant isolation, enforced in the domain.

        The repository also scopes its queries by vendor, and the route checks
        the permission. This is the third layer, and it is the one that still
        holds when a future caller loads the aggregate some other way.
        """
        if vendor_id is None or self.vendor_id != vendor_id:
            raise errors.VendorScopeError

    def assert_editable(self) -> None:
        if not self.status.is_editable_by_vendor:
            raise errors.PropertyNotEditableError(self.status.value)

    # ── mutation ──────────────────────────────────────────────────────────

    def update_details(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        address: Address | None = None,
        location: GeoPoint | None = None,
        amenity_codes: frozenset[str] | None = None,
        cancellation_policy: CancellationPolicy | None = None,
        check_in_from: str | None = None,
        check_out_by: str | None = None,
        house_rules: list[str] | None = None,
        instant_booking: bool | None = None,
        city_id: uuid.UUID | None = None,
    ) -> list[str]:
        """Apply a partial update, returning the fields that actually changed.

        Returning the diff rather than recording every call is what makes the
        ``PropertyUpdated`` event meaningful: a save that changed nothing does
        not trigger a search reindex, and a caller can tell whether their edit
        landed.
        """
        self.assert_editable()
        changed: list[str] = []

        if name is not None and name.strip() and name.strip() != self.name:
            self.name = name.strip()
            # The slug deliberately does NOT follow a rename. Every existing
            # link, every share, every indexed search result points at the old
            # one; the id in the URL is what resolves it anyway.
            changed.append("name")
        if description is not None and description != self.description:
            self.description = description
            changed.append("description")
        if address is not None and address != self.address:
            self.address = address
            changed.append("address")
        if location is not None and location != self.location:
            self.location = location
            changed.append("location")
        if amenity_codes is not None and amenity_codes != self.amenity_codes:
            self.amenity_codes = amenity_codes
            changed.append("amenities")
        if cancellation_policy is not None and cancellation_policy != self.cancellation_policy:
            self.cancellation_policy = cancellation_policy
            changed.append("cancellation_policy")
        if check_in_from is not None and check_in_from != self.check_in_from:
            self.check_in_from = check_in_from
            changed.append("check_in_from")
        if check_out_by is not None and check_out_by != self.check_out_by:
            self.check_out_by = check_out_by
            changed.append("check_out_by")
        if house_rules is not None and house_rules != self.house_rules:
            self.house_rules = house_rules
            changed.append("house_rules")
        if instant_booking is not None and instant_booking != self.instant_booking:
            self.instant_booking = instant_booking
            changed.append("instant_booking")
        if city_id is not None and city_id != self.city_id:
            self.city_id = city_id
            changed.append("city_id")

        if changed:
            self.record(
                PropertyUpdated(
                    aggregate_id=self.id,
                    vendor_id=self.vendor_id,
                    changed_fields=changed,
                    # Only fields that appear in search results or filters need
                    # a reindex. Reindexing on a house-rules edit would mean
                    # rebuilding documents for no visible change.
                    requires_reindex=bool(
                        {"name", "description", "address", "location", "amenities", "city_id"}
                        & set(changed)
                    ),
                )
            )
        return changed

    # ── room types ────────────────────────────────────────────────────────

    def add_room_type(self, room: RoomType) -> None:
        self.assert_editable()

        if self.property_type.is_whole_unit and self.room_types:
            raise errors.WholeUnitRoomLimitError(self.property_type.value)
        if len(self.room_types) >= MAX_ROOM_TYPES:
            msg = f"A listing may have at most {MAX_ROOM_TYPES} room types"
            raise errors.DuplicateRoomTypeError(msg)
        if any(rt.name.casefold() == room.name.casefold() for rt in self.room_types):
            # Two "Deluxe Room" entries make the booking screen a coin flip for
            # the guest and the availability calendar unreadable for the vendor.
            raise errors.DuplicateRoomTypeError(room.name)
        if room.rate.currency != self.currency:
            msg = f"Room rate currency {room.rate.currency} does not match listing currency"
            raise ValueError(msg)

        self.room_types.append(room)
        self.record(
            RoomTypeAdded(
                aggregate_id=self.id,
                room_type_id=room.id,
                name=room.name,
                base_rate_minor=room.rate.base_rate.amount_minor,
                currency=room.rate.currency,
                total_units=room.total_units,
            )
        )

    def room_type(self, room_type_id: uuid.UUID) -> RoomType:
        for room in self.room_types:
            if room.id == room_type_id:
                return room
        raise errors.RoomTypeNotFoundError(room_type_id)

    def remove_room_type(self, room_type_id: uuid.UUID) -> None:
        self.assert_editable()
        room = self.room_type(room_type_id)

        if self.status is PropertyStatus.PUBLISHED and len(self.room_types) == 1:
            raise errors.LastRoomTypeError

        self.room_types.remove(room)
        self.record(RoomTypeRemoved(aggregate_id=self.id, room_type_id=room.id))

    @property
    def cheapest_rate(self) -> Money | None:
        """The "from ₹X" on a search card."""
        priced = [rt.rate.base_rate for rt in self.room_types if rt.is_priced]
        return min(priced, key=lambda m: m.amount_minor) if priced else None

    @property
    def max_occupancy(self) -> int:
        """The largest party the property can take in a single room type.

        Not the sum across room types: a guest searching for six cannot be
        assumed to accept three separate rooms, and offering it as a match
        produces a booking that gets cancelled.
        """
        return max((rt.max_occupancy.billable_guests for rt in self.room_types), default=0)

    # ── images ────────────────────────────────────────────────────────────

    def add_images(self, images: list[PropertyImage]) -> None:
        self.assert_editable()
        if len(self.images) + len(images) > MAX_IMAGES:
            raise errors.ImageLimitError(MAX_IMAGES)

        next_position = max((img.position for img in self.images), default=-1) + 1
        for offset, image in enumerate(images):
            image.position = next_position + offset
            self.images.append(image)

        # The first image uploaded becomes the cover automatically. A vendor
        # who never sets one explicitly still gets a listing that renders.
        if self.images and not any(img.is_cover for img in self.images):
            self.images[0].is_cover = True

        self.record(
            ImagesUploaded(
                aggregate_id=self.id,
                image_ids=[str(i.id) for i in images],
                storage_keys=[i.storage_key for i in images],
            )
        )

    def remove_image(self, image_id: uuid.UUID) -> None:
        self.assert_editable()
        image = next((i for i in self.images if i.id == image_id), None)
        if image is None:
            raise errors.ImageNotFoundError

        if image.is_cover and len(self.images) > 1:
            raise errors.CoverImageRequiredError

        self.images.remove(image)
        self.record(
            ImageRemoved(aggregate_id=self.id, image_id=image.id, storage_key=image.storage_key)
        )

    def set_cover_image(self, image_id: uuid.UUID) -> None:
        self.assert_editable()
        if not any(i.id == image_id for i in self.images):
            raise errors.ImageNotFoundError
        for image in self.images:
            image.is_cover = image.id == image_id

    def reorder_images(self, ordered_ids: list[uuid.UUID]) -> None:
        """Apply an explicit order.

        Ids not mentioned keep their relative position at the end, so a client
        working from a stale list cannot silently drop images from the gallery.
        """
        self.assert_editable()
        known = {i.id: i for i in self.images}
        unknown = [i for i in ordered_ids if i not in known]
        if unknown:
            raise errors.ImageNotFoundError

        for position, image_id in enumerate(ordered_ids):
            known[image_id].position = position
        trailing = position + 1 if ordered_ids else 0
        for image in sorted(self.images, key=lambda i: i.position):
            if image.id not in set(ordered_ids):
                image.position = trailing
                trailing += 1

    @property
    def cover_image(self) -> PropertyImage | None:
        return next((i for i in self.images if i.is_cover), None)

    # ── lifecycle ─────────────────────────────────────────────────────────

    def missing_for_publication(self) -> list[str]:
        """Everything standing between this draft and a live listing.

        Returned as a list so the vendor sees all of it at once — see
        :class:`PropertyNotPublishableError`.
        """
        missing: list[str] = []
        if len(self.description) < MIN_DESCRIPTION_CHARS:
            missing.append(f"description_min_{MIN_DESCRIPTION_CHARS}_chars")
        if not self.address.is_complete:
            missing.append("complete_address")
        if self.location is None:
            # Without coordinates the property cannot appear in any map or
            # radius search, which is how most guests find anything.
            missing.append("map_location")
        if len(self.images) < MIN_IMAGES_TO_PUBLISH:
            missing.append(f"at_least_{MIN_IMAGES_TO_PUBLISH}_images")
        if self.cover_image is None:
            missing.append("cover_image")
        if not self.room_types:
            missing.append("at_least_one_room_type")
        if any(not rt.is_priced for rt in self.room_types):
            missing.append("all_room_types_priced")
        if not self.amenity_codes:
            missing.append("at_least_one_amenity")
        return missing

    def _transition(self, target: PropertyStatus) -> None:
        if target not in _TRANSITIONS.get(self.status, frozenset()):
            raise errors.InvalidStatusTransitionError(self.status.value, target.value)
        self.status = target

    def submit_for_review(self) -> None:
        missing = self.missing_for_publication()
        if missing:
            raise errors.PropertyNotPublishableError(missing)
        self._transition(PropertyStatus.PENDING_REVIEW)
        self.rejection_reason = None
        self.record(
            PropertySubmittedForReview(
                aggregate_id=self.id, vendor_id=self.vendor_id, name=self.name
            )
        )

    def approve(self, *, now: datetime, by: uuid.UUID | None) -> None:
        """Admin approval. Re-checks completeness.

        A listing can be edited while it sits in the review queue, so the
        checks that passed at submission may no longer hold — approving
        without re-checking is how an incomplete listing reaches search.
        """
        missing = self.missing_for_publication()
        if missing:
            raise errors.PropertyNotPublishableError(missing)
        self._transition(PropertyStatus.PUBLISHED)
        self.published_at = self.published_at or now
        self.rejection_reason = None
        self.record(
            PropertyPublished(
                aggregate_id=self.id,
                vendor_id=self.vendor_id,
                name=self.name,
                city=self.address.city,
                property_type=self.property_type.value,
                published_by=by,
            )
        )

    def reject(self, *, reason: str, by: uuid.UUID | None) -> None:
        self._transition(PropertyStatus.REJECTED)
        self.rejection_reason = reason
        self.record(
            PropertyRejected(
                aggregate_id=self.id, vendor_id=self.vendor_id, reason=reason, reviewed_by=by
            )
        )

    def unpublish(self, *, reason: str = "vendor_request") -> None:
        self._transition(PropertyStatus.UNPUBLISHED)
        self.record(
            PropertyUnpublished(
                aggregate_id=self.id, vendor_id=self.vendor_id, reason=reason, by_admin=False
            )
        )

    def republish(self) -> None:
        """Back to live without another review.

        Already vetted once, and the data has not changed in a way that needs
        re-checking — but completeness is re-verified, because the vendor may
        have deleted photos while it was down.
        """
        missing = self.missing_for_publication()
        if missing:
            raise errors.PropertyNotPublishableError(missing)
        self._transition(PropertyStatus.PUBLISHED)
        self.record(
            PropertyPublished(
                aggregate_id=self.id,
                vendor_id=self.vendor_id,
                name=self.name,
                city=self.address.city,
                property_type=self.property_type.value,
                published_by=None,
            )
        )

    def suspend(self, *, reason: str, by: uuid.UUID | None) -> None:
        """Admin action for fraud or a guest-safety complaint.

        Deliberately not reversible by the vendor: the transition table allows
        `suspended → unpublished` only, and only an admin route reaches it.
        """
        self._transition(PropertyStatus.SUSPENDED)
        self.rejection_reason = reason
        self.record(
            PropertyUnpublished(
                aggregate_id=self.id, vendor_id=self.vendor_id, reason=reason, by_admin=True
            )
        )

    @property
    def is_bookable(self) -> bool:
        return self.status.is_visible and bool(self.room_types)
