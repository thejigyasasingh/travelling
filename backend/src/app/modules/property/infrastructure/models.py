"""Property persistence models.

Two denormalisations here are deliberate and load-bearing; everything else is
straightforward.

**``properties.min_rate_minor`` and ``max_guests``** are copies of aggregates
over ``room_types``, maintained by a trigger. They exist because search sorts
and filters on price, and a sort must be satisfiable *before* the LIMIT — a
lateral subquery over room types per candidate row would run for every match,
not just the twenty returned. As indexed columns they cost one trigger on an
infrequent write and turn "cheapest first across 200,000 matches" into an index
scan.

**``properties.amenity_codes``** is a ``text[]`` with a GIN index rather than a
join table. The only query anyone runs is containment — "has all of these" —
which ``@>`` answers from the index directly. A join table would need a
group-by-and-having per candidate property.

The ``amenities`` table still exists, as the catalogue that validates those
codes and supplies labels and icons.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import (
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    VersionMixin,
)


class CityModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Destinations. The primary entry point into search.

    A real table rather than a string on the property because "Goa" must mean
    one place: one landing page, one set of SEO metadata, one centroid to
    search around. Free-text city names give "Goa", "goa", "GOA" and "North
    Goa" as four destinations.
    """

    __tablename__ = "cities"

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    # The centroid a city search radiates from.
    # spatial_index=False — the index is declared explicitly in __table_args__
    # (and partially, for properties). geoalchemy2 would otherwise attach a
    # second identical GIST index.
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(50), server_default=text("'Asia/Kolkata'"))
    #: Default radius for "properties in Goa". Bigger for a state-sized
    #: destination than for a walled city.
    search_radius_m: Mapped[int] = mapped_column(Integer, server_default=text("25000"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    #: Maintained by a nightly job. Lets the destinations page rank by
    #: inventory without counting properties on every page load.
    property_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("slug", name="uq_cities_slug"),
        Index("ix_cities_country", "country_code", "is_active"),
        Index("ix_cities_location", "location", postgresql_using="gist"),
        # Type-ahead: "goa" should match "Goa" and "Old Goa" as you type.
        Index(
            "ix_cities_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class AmenityModel(Base):
    """The amenity catalogue.

    Codes are the contract. Labels and icons change (and get translated); the
    code a property stores and a guest filters on does not.
    """

    __tablename__ = "amenities"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(60))
    #: Shown in the search filter panel. Most amenities are detail-page only —
    #: a filter list of 80 checkboxes is a filter list nobody uses.
    is_filterable: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(SmallInteger, server_default=text("100"))

    __table_args__ = (Index("ix_amenities_category", "category", "sort_order"),)


class PropertyModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    __tablename__ = "properties"

    vendor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    property_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"))

    # ── location ──────────────────────────────────────────────────────────
    line1: Mapped[str] = mapped_column(String(200), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(16))
    landmark: Mapped[str | None] = mapped_column(String(200))
    city_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cities.id", ondelete="SET NULL")
    )
    # geography, not geometry: distance in metres on a spheroid, and a GIST
    # index that actually works for "within 25 km".
    location: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )

    # ── policies ──────────────────────────────────────────────────────────
    cancellation_policy: Mapped[str] = mapped_column(String(20), server_default=text("'moderate'"))
    check_in_from: Mapped[str] = mapped_column(String(5), server_default=text("'14:00'"))
    check_out_by: Mapped[str] = mapped_column(String(5), server_default=text("'11:00'"))
    house_rules: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    instant_booking: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    # ── search projections ────────────────────────────────────────────────
    # See the module docstring: these are trigger-maintained copies that make
    # price sorting and amenity filtering index-only.
    amenity_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, server_default=text("ARRAY[]::varchar[]")
    )
    min_rate_minor: Mapped[int | None] = mapped_column(Integer)
    max_guests: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    room_type_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))

    # ── reputation ────────────────────────────────────────────────────────
    # Denormalised from the reviews module for the same reason as price: search
    # sorts on it.
    review_average: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0")
    )
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    room_types: Mapped[list[RoomTypeModel]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        # selectin, not joined: a joined load multiplies the property row by
        # rooms x images and makes the driver de-duplicate a cartesian product.
        lazy="selectin",
        order_by="RoomTypeModel.created_at",
    )
    images: Mapped[list[PropertyImageModel]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PropertyImageModel.position",
    )

    __mapper_args__ = {"version_id_col": VersionMixin.version}  # noqa: RUF012

    __table_args__ = (
        Index(
            "uq_properties_slug",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "property_type IN ('hotel','resort','villa','apartment','homestay')",
            name="type_valid",
        ),
        CheckConstraint(
            "status IN ('draft','pending_review','published','unpublished','rejected','suspended')",
            name="status_valid",
        ),
        CheckConstraint("review_average >= 0 AND review_average <= 5", name="rating_range"),
        CheckConstraint("min_rate_minor IS NULL OR min_rate_minor > 0", name="rate_positive"),
        # ── search indexes ────────────────────────────────────────────────
        # Every one of these is partial on published+not-deleted. Search only
        # ever looks at live listings, and drafts are the majority of rows in a
        # marketplace — indexing them would double the index for no reads.
        Index(
            "ix_properties_live_location",
            "location",
            postgresql_using="gist",
            postgresql_where=text("status = 'published' AND deleted_at IS NULL"),
        ),
        Index(
            "ix_properties_live_city_rate",
            "city_id",
            "min_rate_minor",
            postgresql_where=text("status = 'published' AND deleted_at IS NULL"),
        ),
        Index(
            "ix_properties_live_rating",
            text("review_average DESC"),
            text("review_count DESC"),
            postgresql_where=text("status = 'published' AND deleted_at IS NULL"),
        ),
        Index(
            "ix_properties_live_amenities",
            "amenity_codes",
            postgresql_using="gin",
            postgresql_where=text("status = 'published' AND deleted_at IS NULL"),
        ),
        Index(
            "ix_properties_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
            postgresql_where=text("status = 'published' AND deleted_at IS NULL"),
        ),
        # The vendor dashboard.
        Index("ix_properties_vendor", "vendor_id", "status", "created_at"),
        # The admin review queue.
        Index(
            "ix_properties_review_queue",
            "created_at",
            postgresql_where=text("status = 'pending_review'"),
        ),
    )


class RoomTypeModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "room_types"

    property_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    bed_type: Mapped[str] = mapped_column(String(20), server_default=text("'double'"))
    max_adults: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("2"))
    max_children: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    total_units: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    size_sqft: Mapped[int | None] = mapped_column(Integer)
    amenity_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, server_default=text("ARRAY[]::varchar[]")
    )

    # ── rate configuration ────────────────────────────────────────────────
    # Integer minor units throughout. See core/types/money.py for why a float
    # here would break payout reconciliation.
    base_rate_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    weekend_rate_minor: Mapped[int | None] = mapped_column(Integer)
    extra_guest_rate_minor: Mapped[int | None] = mapped_column(Integer)
    included_guests: Mapped[int] = mapped_column(SmallInteger, server_default=text("2"))
    cleaning_fee_minor: Mapped[int | None] = mapped_column(Integer)
    min_nights: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    max_nights: Mapped[int] = mapped_column(SmallInteger, server_default=text("30"))
    tax_rate: Mapped[float] = mapped_column(Numeric(4, 3), server_default=text("0.120"))

    property: Mapped[PropertyModel] = relationship(back_populates="room_types", lazy="raise_on_sql")

    __table_args__ = (
        # Case-insensitive, because "Deluxe Room" and "deluxe room" on one
        # listing make the booking screen a coin flip for the guest.
        Index(
            "uq_room_types_property_name",
            "property_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("base_rate_minor > 0", name="base_rate_positive"),
        CheckConstraint("total_units > 0", name="units_positive"),
        CheckConstraint("max_nights >= min_nights", name="nights_range"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 0.5", name="tax_range"),
        Index("ix_room_types_property", "property_id", postgresql_where=text("deleted_at IS NULL")),
    )


class PropertyImageModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "property_images"

    property_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    alt_text: Mapped[str | None] = mapped_column(String(200))
    caption: Mapped[str | None] = mapped_column(String(300))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    #: Set by the moderation consumer. A listing with a rejected cover is
    #: pulled from search until the vendor replaces it.
    moderation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )

    property: Mapped[PropertyModel] = relationship(back_populates="images", lazy="raise_on_sql")

    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_property_images_key"),
        # At most one cover per property, enforced by the database. Two covers
        # means search renders whichever row comes back first, which changes
        # between page loads.
        Index(
            "uq_property_images_cover",
            "property_id",
            unique=True,
            postgresql_where=text("is_cover"),
        ),
        Index("ix_property_images_property", "property_id", "position"),
        CheckConstraint(
            "moderation_status IN ('pending','approved','rejected')", name="moderation_valid"
        ),
    )


class RoomInventoryModel(Base):
    """The sparse calendar. One row per room type per date — **only** where the
    date deviates from the room-type defaults.

    See the module docstring of ``domain/availability.py`` for why this is not
    pre-materialised: the dense version is ~2 billion rows that mostly say
    "nothing has happened here".
    """

    __tablename__ = "room_inventory"

    room_type_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("room_types.id", ondelete="CASCADE"), primary_key=True
    )
    stay_date: Mapped[date] = mapped_column(Date, primary_key=True)

    units_total: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    units_booked: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    rate_override_minor: Mapped[int | None] = mapped_column(Integer)
    min_nights_override: Mapped[int | None] = mapped_column(SmallInteger)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    #: Set when a channel manager (Booking.com, Airbnb) pushed this row, so a
    #: two-way sync can tell its own writes from a vendor's.
    source: Mapped[str] = mapped_column(String(20), server_default=text("'internal'"))
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        # THE overbooking guard. Application code cannot enforce this — a
        # check-then-act race between two concurrent bookings always has a
        # window. The database has no window.
        CheckConstraint("units_booked <= units_total", name="no_overbooking"),
        CheckConstraint("units_booked >= 0", name="booked_non_negative"),
        CheckConstraint("units_total >= 0", name="total_non_negative"),
        CheckConstraint(
            "rate_override_minor IS NULL OR rate_override_minor > 0", name="rate_positive"
        ),
        # Search's availability subquery: given a room type and a date range,
        # find the rows that block it. The PK already covers (room_type_id,
        # stay_date); this partial index covers only the rows that can *fail* a
        # search, which is a tiny fraction of them.
        Index(
            "ix_room_inventory_unavailable",
            "room_type_id",
            "stay_date",
            postgresql_where=text("is_blocked OR units_booked >= units_total"),
        ),
        # Drives the nightly purge of past dates.
        Index("ix_room_inventory_purge", "stay_date"),
    )
