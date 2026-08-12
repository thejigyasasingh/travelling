"""ORM ↔ domain translation for the property aggregate."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from geoalchemy2.shape import to_shape

from app.core.logging import get_logger
from app.core.types.money import Money
from app.modules.property.domain.entities import Property, PropertyImage, RoomType
from app.modules.property.domain.pricing import RateConfig
from app.modules.property.domain.value_objects import (
    Address,
    BedType,
    CancellationPolicy,
    GeoPoint,
    Occupancy,
    PropertyStatus,
    PropertyType,
)
from app.modules.property.infrastructure.models import (
    PropertyImageModel,
    PropertyModel,
    RoomTypeModel,
)

logger = get_logger(__name__)


def _to_point(value: Any) -> GeoPoint | None:
    """Decode PostGIS geography into a domain value.

    Returns ``None`` rather than raising on an unreadable geometry: one bad
    coordinate should hide a property from map search, not take the whole
    listing page down.

    **The narrow except is the point.** This began as `except Exception`, and it
    swallowed an ``ImportError`` — ``to_shape`` needs Shapely, which was not
    installed — so *every* property on the platform decoded to no coordinates.
    Nothing failed: map search runs through raw PostGIS and kept working, and
    the only visible symptom was that no listing could ever be published,
    because the publish checklist requires a map location. It looked like a
    product rule, not a missing package.

    A malformed geometry is data and is tolerated. A missing dependency is a
    broken deployment and must not be quietly absorbed as if it were data.
    """
    if value is None:
        return None
    try:
        shape = to_shape(value)
    except (ValueError, TypeError, AttributeError):
        # Genuinely unreadable geometry. Logged, because a property silently
        # absent from map search is otherwise invisible.
        logger.warning("geometry_decode_failed", value=repr(value)[:120])
        return None
    return GeoPoint(latitude=shape.y, longitude=shape.x)


def _money(minor: int | None, currency: str) -> Money | None:
    return Money(minor, currency) if minor is not None else None


# ══════════════════════════════════════════════════════════════════════════
# ORM → domain
# ══════════════════════════════════════════════════════════════════════════


def room_to_domain(row: RoomTypeModel, currency: str) -> RoomType:
    return RoomType(
        entity_id=row.id,
        name=row.name,
        rate=RateConfig(
            base_rate=Money(row.base_rate_minor, currency),
            weekend_rate=_money(row.weekend_rate_minor, currency),
            included_guests=row.included_guests,
            extra_guest_rate=_money(row.extra_guest_rate_minor, currency),
            min_nights=row.min_nights,
            max_nights=row.max_nights,
            tax_rate=Decimal(str(row.tax_rate)),
            cleaning_fee=_money(row.cleaning_fee_minor, currency),
        ),
        max_occupancy=Occupancy(adults=row.max_adults, children=row.max_children),
        total_units=row.total_units,
        bed_type=BedType(row.bed_type),
        description=row.description,
        size_sqft=row.size_sqft,
        amenity_codes=frozenset(row.amenity_codes or []),
    )


def image_to_domain(row: PropertyImageModel) -> PropertyImage:
    return PropertyImage(
        entity_id=row.id,
        storage_key=row.storage_key,
        position=row.position,
        is_cover=row.is_cover,
        alt_text=row.alt_text,
        caption=row.caption,
        width=row.width,
        height=row.height,
    )


def property_to_domain(row: PropertyModel) -> Property:
    return Property(
        entity_id=row.id,
        vendor_id=row.vendor_id,
        name=row.name,
        slug=row.slug,
        property_type=PropertyType(row.property_type),
        status=PropertyStatus(row.status),
        description=row.description,
        currency=row.currency,
        address=Address(
            line1=row.line1,
            line2=row.line2,
            city=row.city,
            state=row.state,
            country_code=row.country_code,
            postal_code=row.postal_code,
            landmark=row.landmark,
        ),
        location=_to_point(row.location),
        city_id=row.city_id,
        amenity_codes=frozenset(row.amenity_codes or []),
        # Soft-deleted rooms are filtered here rather than by the query, so
        # every caller gets the same view regardless of how it loaded the
        # aggregate.
        room_types=[
            room_to_domain(rt, row.currency) for rt in row.room_types if rt.deleted_at is None
        ],
        images=[image_to_domain(img) for img in row.images],
        cancellation_policy=CancellationPolicy(row.cancellation_policy),
        check_in_from=row.check_in_from,
        check_out_by=row.check_out_by,
        house_rules=list(row.house_rules or []),
        instant_booking=row.instant_booking,
        review_average=float(row.review_average),
        review_count=row.review_count,
        published_at=row.published_at,
        rejection_reason=row.rejection_reason,
        version=row.version,
    )


# ══════════════════════════════════════════════════════════════════════════
# Domain → ORM
# ══════════════════════════════════════════════════════════════════════════


def _wkt(point: GeoPoint | None) -> str | None:
    return f"SRID=4326;{point.to_wkt()}" if point else None


def property_to_model(prop: Property) -> PropertyModel:
    """New rows only. Existing ones go through :func:`apply_property_to_model`."""
    row = PropertyModel(
        id=prop.id,
        vendor_id=prop.vendor_id,
        name=prop.name,
        slug=prop.slug,
        property_type=prop.property_type.value,
        status=prop.status.value,
        description=prop.description,
        currency=prop.currency,
        line1=prop.address.line1,
        line2=prop.address.line2,
        city=prop.address.city,
        state=prop.address.state,
        country_code=prop.address.country_code,
        postal_code=prop.address.postal_code,
        landmark=prop.address.landmark,
        city_id=prop.city_id,
        location=_wkt(prop.location),
        cancellation_policy=prop.cancellation_policy.value,
        check_in_from=prop.check_in_from,
        check_out_by=prop.check_out_by,
        house_rules=list(prop.house_rules),
        instant_booking=prop.instant_booking,
        amenity_codes=sorted(prop.amenity_codes),
        published_at=prop.published_at,
        rejection_reason=prop.rejection_reason,
    )
    row.room_types = [room_to_model(rt, prop.id) for rt in prop.room_types]
    row.images = [image_to_model(img, prop.id) for img in prop.images]
    return row


def room_to_model(room: RoomType, property_id: Any) -> RoomTypeModel:
    return RoomTypeModel(
        id=room.id,
        property_id=property_id,
        name=room.name,
        description=room.description,
        bed_type=room.bed_type.value,
        max_adults=room.max_occupancy.adults,
        max_children=room.max_occupancy.children,
        total_units=room.total_units,
        size_sqft=room.size_sqft,
        amenity_codes=sorted(room.amenity_codes),
        base_rate_minor=room.rate.base_rate.amount_minor,
        weekend_rate_minor=(
            room.rate.weekend_rate.amount_minor if room.rate.weekend_rate else None
        ),
        extra_guest_rate_minor=(
            room.rate.extra_guest_rate.amount_minor if room.rate.extra_guest_rate else None
        ),
        included_guests=room.rate.included_guests,
        cleaning_fee_minor=(
            room.rate.cleaning_fee.amount_minor if room.rate.cleaning_fee else None
        ),
        min_nights=room.rate.min_nights,
        max_nights=room.rate.max_nights,
        tax_rate=room.rate.tax_rate,
    )


def image_to_model(image: PropertyImage, property_id: Any) -> PropertyImageModel:
    return PropertyImageModel(
        id=image.id,
        property_id=property_id,
        storage_key=image.storage_key,
        position=image.position,
        is_cover=image.is_cover,
        alt_text=image.alt_text,
        caption=image.caption,
        width=image.width,
        height=image.height,
    )


def apply_property_to_model(prop: Property, row: PropertyModel) -> None:
    """Copy mutable state back onto an attached row.

    Child collections are reconciled by id rather than replaced wholesale.
    Clearing and re-adding would delete and re-insert every room type on every
    save — new primary keys, orphaned inventory rows, and a cascade that
    silently destroys a property's entire calendar.
    """
    row.name = prop.name
    row.slug = prop.slug
    row.status = prop.status.value
    row.description = prop.description
    row.line1 = prop.address.line1
    row.line2 = prop.address.line2
    row.city = prop.address.city
    row.state = prop.address.state
    row.country_code = prop.address.country_code
    row.postal_code = prop.address.postal_code
    row.landmark = prop.address.landmark
    row.city_id = prop.city_id
    if prop.location is not None:
        row.location = _wkt(prop.location)
    row.cancellation_policy = prop.cancellation_policy.value
    row.check_in_from = prop.check_in_from
    row.check_out_by = prop.check_out_by
    row.house_rules = list(prop.house_rules)
    row.instant_booking = prop.instant_booking
    row.amenity_codes = sorted(prop.amenity_codes)
    row.published_at = prop.published_at
    row.rejection_reason = prop.rejection_reason

    _reconcile_rooms(prop, row)
    _reconcile_images(prop, row)


def _reconcile_rooms(prop: Property, row: PropertyModel) -> None:
    existing = {rt.id: rt for rt in row.room_types}
    wanted = {rt.id: rt for rt in prop.room_types}

    for room_id, room in wanted.items():
        if (current := existing.get(room_id)) is None:
            row.room_types.append(room_to_model(room, prop.id))
            continue
        current.name = room.name
        current.description = room.description
        current.bed_type = room.bed_type.value
        current.max_adults = room.max_occupancy.adults
        current.max_children = room.max_occupancy.children
        current.total_units = room.total_units
        current.size_sqft = room.size_sqft
        current.amenity_codes = sorted(room.amenity_codes)
        current.base_rate_minor = room.rate.base_rate.amount_minor
        current.weekend_rate_minor = (
            room.rate.weekend_rate.amount_minor if room.rate.weekend_rate else None
        )
        current.extra_guest_rate_minor = (
            room.rate.extra_guest_rate.amount_minor if room.rate.extra_guest_rate else None
        )
        current.included_guests = room.rate.included_guests
        current.cleaning_fee_minor = (
            room.rate.cleaning_fee.amount_minor if room.rate.cleaning_fee else None
        )
        current.min_nights = room.rate.min_nights
        current.max_nights = room.rate.max_nights
        current.tax_rate = room.rate.tax_rate  # type: ignore[assignment]  # Numeric column

    for room_id, current in existing.items():
        if room_id not in wanted and current.deleted_at is None:
            # Soft delete, not removal from the collection. A hard delete
            # cascades to room_inventory and destroys the booking history that
            # payouts and invoices are reconstructed from.
            from app.core.clock import utcnow

            current.deleted_at = utcnow()


def _reconcile_images(prop: Property, row: PropertyImageModel | PropertyModel) -> None:
    assert isinstance(row, PropertyModel)
    existing = {img.id: img for img in row.images}
    wanted = {img.id: img for img in prop.images}

    for image_id, image in wanted.items():
        if (current := existing.get(image_id)) is None:
            row.images.append(image_to_model(image, prop.id))
            continue
        current.position = image.position
        current.is_cover = image.is_cover
        current.alt_text = image.alt_text
        current.caption = image.caption

    for image_id, current in list(existing.items()):
        if image_id not in wanted:
            # Images ARE hard-deleted: nothing references them, and the S3
            # object is removed by the ImageRemoved consumer.
            row.images.remove(current)
