"""Aggregate → view mapping.

One place, because the *same* rule about what an unbooked guest may see has to
hold on the detail page, in a share preview and in a vendor's own view of their
listing. Written three times, one copy eventually leaks the street address.

The rule: ``include_private`` is true only for the owning vendor, an admin, or
a guest with a confirmed booking. Everyone else gets the city-level
approximation.
"""

from __future__ import annotations

from app.modules.property.application.dto import ImageView, PropertyView, RoomTypeView
from app.modules.property.application.ports import ImageUrlBuilder
from app.modules.property.domain.entities import Property, RoomType


def to_room_view(room: RoomType) -> RoomTypeView:
    return RoomTypeView(
        id=room.id,
        name=room.name,
        description=room.description,
        bed_type=room.bed_type.value,
        max_adults=room.max_occupancy.adults,
        max_children=room.max_occupancy.children,
        total_units=room.total_units,
        size_sqft=room.size_sqft,
        amenity_codes=sorted(room.amenity_codes),
        base_rate_minor=room.rate.base_rate.amount_minor,
        currency=room.rate.currency,
        min_nights=room.rate.min_nights,
    )


def to_property_view(
    prop: Property, *, urls: ImageUrlBuilder, include_private: bool
) -> PropertyView:
    location = prop.location
    if location is not None and not include_private:
        # ~1 km precision. Enough for "is this near the beach?", not enough to
        # stand outside an occupied private home.
        location = location.obfuscated

    return PropertyView(
        id=prop.id,
        slug=prop.slug,
        name=prop.name,
        property_type=prop.property_type.value,
        status=prop.status.value,
        description=prop.description,
        address=prop.address.single_line() if include_private else prop.address.approximate(),
        city=prop.address.city,
        state=prop.address.state,
        country_code=prop.address.country_code,
        latitude=location.latitude if location else None,
        longitude=location.longitude if location else None,
        location_is_approximate=not include_private,
        amenity_codes=sorted(prop.amenity_codes),
        images=[
            ImageView(
                id=img.id,
                url=urls.public_url(img.storage_key),
                position=img.position,
                is_cover=img.is_cover,
                alt_text=img.alt_text,
                caption=img.caption,
            )
            for img in sorted(prop.images, key=lambda i: i.position)
        ],
        room_types=[to_room_view(rt) for rt in prop.room_types],
        cancellation_policy=prop.cancellation_policy.value,
        check_in_from=prop.check_in_from,
        check_out_by=prop.check_out_by,
        house_rules=list(prop.house_rules),
        instant_booking=prop.instant_booking,
        review_average=prop.review_average,
        review_count=prop.review_count,
        currency=prop.currency,
        vendor_id=prop.vendor_id,
        published_at=prop.published_at,
        # Only the vendor needs the to-do list, and only they can act on it.
        missing_for_publication=prop.missing_for_publication() if include_private else None,
        rejection_reason=prop.rejection_reason if include_private else None,
    )
