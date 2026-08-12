"""property: cities, amenities, listings, rooms, images, sparse inventory

Revision ID: 0003_property
Revises: 0002_auth
Created: 2026-08-06 16:00:00+00:00

Reviewer notes:

* **``room_inventory`` is sparse.** One row per room type per date, and only
  where the date deviates from the room-type defaults. The dense alternative is
  ~2 billion rows at a million properties. Readers apply
  ``COALESCE(row, default)``; see ``domain/availability.py``.
* **``properties.min_rate_minor`` / ``max_guests`` are trigger-maintained
  copies** of aggregates over ``room_types``. Search sorts and filters on
  price, and a sort must be satisfiable before the LIMIT — computing "cheapest
  room" per candidate would run over every match, not just the page returned.
* **Every search index is partial on ``published`` + not-deleted.** Drafts are
  the majority of rows in a marketplace and search never reads them; indexing
  them would double the index for no benefit.
* **PostGIS ``geography``, not two float columns.** Only geography gives
  metre-accurate distance on a spheroid and a GIST index that ``ST_DWithin``
  can actually use.

Additive only — no existing table is touched, so this is safe to apply before
the new code is deployed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0003_property"
down_revision: str | None = "0002_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Keeps the denormalised search columns in step with room_types. A trigger and
# not application code: a bulk import, an admin SQL fix or a second service
# would all bypass the application, and a stale min_rate is a listing that
# silently vanishes from every price filter.
SYNC_SEARCH_COLUMNS = """
CREATE OR REPLACE FUNCTION sync_property_search_columns()
RETURNS TRIGGER AS $$
DECLARE
    target uuid;
BEGIN
    target := COALESCE(NEW.property_id, OLD.property_id);
    UPDATE properties p
       SET min_rate_minor = sub.min_rate,
           max_guests     = COALESCE(sub.max_guests, 0),
           room_type_count = COALESCE(sub.cnt, 0)
      FROM (
            SELECT MIN(base_rate_minor)              AS min_rate,
                   MAX(max_adults + max_children)    AS max_guests,
                   COUNT(*)                          AS cnt
              FROM room_types
             WHERE property_id = target AND deleted_at IS NULL
           ) sub
     WHERE p.id = target;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""

AMENITIES = [
    # code, label, category, icon, filterable
    ("wifi", "Free Wi-Fi", "essentials", "wifi", True),
    ("air_conditioning", "Air conditioning", "essentials", "snowflake", True),
    ("heating", "Heating", "essentials", "flame", False),
    ("hot_water", "Hot water", "essentials", "droplet", False),
    ("power_backup", "Power backup", "essentials", "battery", True),
    ("kitchen", "Kitchen", "essentials", "chef-hat", True),
    ("washing_machine", "Washing machine", "essentials", "washing-machine", False),
    ("workspace", "Dedicated workspace", "essentials", "laptop", True),
    ("tv", "TV", "entertainment", "tv", False),
    ("pool", "Swimming pool", "outdoor", "waves", True),
    ("private_pool", "Private pool", "outdoor", "waves", True),
    ("beach_access", "Beach access", "outdoor", "umbrella", True),
    ("garden", "Garden", "outdoor", "trees", False),
    ("bbq", "Barbecue area", "outdoor", "flame", False),
    ("balcony", "Balcony", "outdoor", "door-open", False),
    ("parking", "Free parking", "facilities", "car", True),
    ("ev_charging", "EV charging", "facilities", "zap", True),
    ("gym", "Gym", "facilities", "dumbbell", True),
    ("spa", "Spa", "facilities", "sparkles", True),
    ("restaurant", "Restaurant", "facilities", "utensils", True),
    ("bar", "Bar", "facilities", "wine", False),
    ("elevator", "Lift", "facilities", "move-vertical", False),
    ("room_service", "Room service", "services", "concierge-bell", False),
    ("breakfast", "Breakfast included", "services", "croissant", True),
    ("airport_shuttle", "Airport shuttle", "services", "plane", True),
    ("housekeeping", "Daily housekeeping", "services", "brush", False),
    ("front_desk_24h", "24-hour front desk", "services", "clock", False),
    ("pet_friendly", "Pet friendly", "policies", "dog", True),
    ("smoking_allowed", "Smoking allowed", "policies", "cigarette", False),
    ("events_allowed", "Events allowed", "policies", "party-popper", False),
    ("family_friendly", "Family friendly", "policies", "baby", True),
    ("wheelchair_accessible", "Wheelchair accessible", "accessibility", "accessibility", True),
    ("step_free_access", "Step-free access", "accessibility", "footprints", False),
    ("security_cameras", "Security cameras", "safety", "cctv", False),
    ("smoke_alarm", "Smoke alarm", "safety", "alarm-smoke", False),
    ("first_aid_kit", "First aid kit", "safety", "first-aid", False),
    ("mountain_view", "Mountain view", "views", "mountain", True),
    ("sea_view", "Sea view", "views", "waves", True),
    ("lake_view", "Lake view", "views", "waves", False),
    ("city_view", "City view", "views", "building", False),
]


def upgrade() -> None:
    # PostGIS. Declared here rather than in the baseline because this is the
    # first migration that needs it, and because a deployment that never runs
    # the property module should not be forced to install it.
    #
    # It is NOT enough to run the postgis Docker image: that image enables the
    # extension in `template1`, so a database created before the image's init
    # script ran — or one created with `CREATE DATABASE ... TEMPLATE template0`
    # — will not have it. Without this line the migration fails on
    # `type "geography" does not exist`, which is what a fresh managed-Postgres
    # deploy looks like.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # ── cities ────────────────────────────────────────────────────────────
    op.create_table(
        "cities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=120)),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        # spatial_index=False: we declare our own below. geoalchemy2 would
        # otherwise attach a second, identical GIST index.
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "timezone",
            sa.String(length=50),
            server_default=sa.text("'Asia/Kolkata'"),
            nullable=False,
        ),
        sa.Column("search_radius_m", sa.Integer(), server_default=sa.text("25000"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("property_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cities")),
        sa.UniqueConstraint("slug", name="uq_cities_slug"),
    )
    op.create_index("ix_cities_country", "cities", ["country_code", "is_active"])
    op.create_index("ix_cities_location", "cities", ["location"], postgresql_using="gist")
    op.create_index(
        "ix_cities_name_trgm",
        "cities",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index("ix_cities_created_at", "cities", ["created_at"])

    # ── amenity catalogue ─────────────────────────────────────────────────
    op.create_table(
        "amenities",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("icon", sa.String(length=60)),
        sa.Column("is_filterable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), server_default=sa.text("100"), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_amenities")),
    )
    op.create_index("ix_amenities_category", "amenities", ["category", "sort_order"])

    op.get_bind().execute(
        sa.text(
            "INSERT INTO amenities (code, label, category, icon, is_filterable, sort_order) "
            "VALUES (:code, :label, :category, :icon, :is_filterable, :sort_order)"
        ),
        [
            {
                "code": c,
                "label": label,
                "category": cat,
                "icon": icon,
                "is_filterable": filt,
                "sort_order": i * 10,
            }
            for i, (c, label, cat, icon, filt) in enumerate(AMENITIES)
        ],
    )

    # ── properties ────────────────────────────────────────────────────────
    op.create_table(
        "properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("property_type", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'INR'"), nullable=False),
        sa.Column("line1", sa.String(length=200), nullable=False),
        sa.Column("line2", sa.String(length=200)),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=120)),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("postal_code", sa.String(length=16)),
        sa.Column("landmark", sa.String(length=200)),
        sa.Column("city_id", postgresql.UUID(as_uuid=True)),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326, spatial_index=False)),
        sa.Column(
            "cancellation_policy",
            sa.String(length=20),
            server_default=sa.text("'moderate'"),
            nullable=False,
        ),
        sa.Column(
            "check_in_from", sa.String(length=5), server_default=sa.text("'14:00'"), nullable=False
        ),
        sa.Column(
            "check_out_by", sa.String(length=5), server_default=sa.text("'11:00'"), nullable=False
        ),
        sa.Column(
            "house_rules",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("ARRAY[]::text[]"),
            nullable=False,
        ),
        sa.Column("instant_booking", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "amenity_codes",
            postgresql.ARRAY(sa.String(length=50)),
            server_default=sa.text("ARRAY[]::varchar[]"),
            nullable=False,
        ),
        sa.Column("min_rate_minor", sa.Integer()),
        sa.Column("max_guests", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "room_type_count", sa.SmallInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("review_average", sa.Numeric(3, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("review_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_properties")),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
            name=op.f("fk_properties_city_id_cities"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "property_type IN ('hotel','resort','villa','apartment','homestay')",
            name=op.f("ck_properties_type_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('draft','pending_review','published','unpublished','rejected','suspended')",
            name=op.f("ck_properties_status_valid"),
        ),
        sa.CheckConstraint(
            "review_average >= 0 AND review_average <= 5", name=op.f("ck_properties_rating_range")
        ),
        sa.CheckConstraint(
            "min_rate_minor IS NULL OR min_rate_minor > 0",
            name=op.f("ck_properties_rate_positive"),
        ),
    )

    op.create_index(
        "uq_properties_slug",
        "properties",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_properties_created_at", "properties", ["created_at"])
    op.create_index("ix_properties_deleted_at", "properties", ["deleted_at"])
    op.create_index("ix_properties_vendor", "properties", ["vendor_id", "status", "created_at"])
    op.create_index(
        "ix_properties_review_queue",
        "properties",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending_review'"),
    )

    live = sa.text("status = 'published' AND deleted_at IS NULL")
    op.create_index(
        "ix_properties_live_location",
        "properties",
        ["location"],
        postgresql_using="gist",
        postgresql_where=live,
    )
    op.create_index(
        "ix_properties_live_city_rate",
        "properties",
        ["city_id", "min_rate_minor"],
        postgresql_where=live,
    )
    op.execute(
        "CREATE INDEX ix_properties_live_rating ON properties "
        "(review_average DESC, review_count DESC) "
        "WHERE status = 'published' AND deleted_at IS NULL"
    )
    op.create_index(
        "ix_properties_live_amenities",
        "properties",
        ["amenity_codes"],
        postgresql_using="gin",
        postgresql_where=live,
    )
    op.create_index(
        "ix_properties_name_trgm",
        "properties",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
        postgresql_where=live,
    )

    op.execute(
        "CREATE TRIGGER trg_properties_updated_at BEFORE UPDATE ON properties "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ── room types ────────────────────────────────────────────────────────
    op.create_table(
        "room_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "bed_type", sa.String(length=20), server_default=sa.text("'double'"), nullable=False
        ),
        sa.Column("max_adults", sa.SmallInteger(), server_default=sa.text("2"), nullable=False),
        sa.Column("max_children", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_units", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("size_sqft", sa.Integer()),
        sa.Column(
            "amenity_codes",
            postgresql.ARRAY(sa.String(length=50)),
            server_default=sa.text("ARRAY[]::varchar[]"),
            nullable=False,
        ),
        sa.Column("base_rate_minor", sa.Integer(), nullable=False),
        sa.Column("weekend_rate_minor", sa.Integer()),
        sa.Column("extra_guest_rate_minor", sa.Integer()),
        sa.Column(
            "included_guests", sa.SmallInteger(), server_default=sa.text("2"), nullable=False
        ),
        sa.Column("cleaning_fee_minor", sa.Integer()),
        sa.Column("min_nights", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("max_nights", sa.SmallInteger(), server_default=sa.text("30"), nullable=False),
        sa.Column("tax_rate", sa.Numeric(4, 3), server_default=sa.text("0.120"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_room_types")),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_room_types_property_id_properties"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("base_rate_minor > 0", name=op.f("ck_room_types_base_rate_positive")),
        sa.CheckConstraint("total_units > 0", name=op.f("ck_room_types_units_positive")),
        sa.CheckConstraint("max_nights >= min_nights", name=op.f("ck_room_types_nights_range")),
        sa.CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 0.5", name=op.f("ck_room_types_tax_range")
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_room_types_property_name ON room_types "
        "(property_id, lower(name)) WHERE deleted_at IS NULL"
    )
    op.create_index(
        "ix_room_types_property",
        "room_types",
        ["property_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_room_types_created_at", "room_types", ["created_at"])
    op.create_index("ix_room_types_deleted_at", "room_types", ["deleted_at"])

    op.execute(
        "CREATE TRIGGER trg_room_types_updated_at BEFORE UPDATE ON room_types "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )
    op.execute(SYNC_SEARCH_COLUMNS)
    op.execute(
        "CREATE TRIGGER trg_room_types_sync_search "
        "AFTER INSERT OR UPDATE OR DELETE ON room_types "
        "FOR EACH ROW EXECUTE FUNCTION sync_property_search_columns()"
    )

    # ── images ────────────────────────────────────────────────────────────
    op.create_table(
        "property_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("position", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_cover", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("alt_text", sa.String(length=200)),
        sa.Column("caption", sa.String(length=300)),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column(
            "moderation_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_images")),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_property_images_property_id_properties"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("storage_key", name="uq_property_images_key"),
        sa.CheckConstraint(
            "moderation_status IN ('pending','approved','rejected')",
            name=op.f("ck_property_images_moderation_valid"),
        ),
    )
    # One cover per property, enforced by the database — two covers means
    # search renders whichever row comes back first, which changes per request.
    op.create_index(
        "uq_property_images_cover",
        "property_images",
        ["property_id"],
        unique=True,
        postgresql_where=sa.text("is_cover"),
    )
    op.create_index("ix_property_images_property", "property_images", ["property_id", "position"])
    op.create_index("ix_property_images_created_at", "property_images", ["created_at"])

    # ── sparse inventory ──────────────────────────────────────────────────
    op.create_table(
        "room_inventory",
        sa.Column("room_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stay_date", sa.Date(), nullable=False),
        sa.Column("units_total", sa.SmallInteger(), nullable=False),
        sa.Column("units_booked", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("rate_override_minor", sa.Integer()),
        sa.Column("min_nights_override", sa.SmallInteger()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "source", sa.String(length=20), server_default=sa.text("'internal'"), nullable=False
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("room_type_id", "stay_date", name=op.f("pk_room_inventory")),
        sa.ForeignKeyConstraint(
            ["room_type_id"],
            ["room_types.id"],
            name=op.f("fk_room_inventory_room_type_id_room_types"),
            ondelete="CASCADE",
        ),
        # THE overbooking guard. Application code cannot enforce this — a
        # check-then-act race between two concurrent bookings always has a
        # window. The database has none.
        sa.CheckConstraint(
            "units_booked <= units_total", name=op.f("ck_room_inventory_no_overbooking")
        ),
        sa.CheckConstraint("units_booked >= 0", name=op.f("ck_room_inventory_booked_non_negative")),
        sa.CheckConstraint("units_total >= 0", name=op.f("ck_room_inventory_total_non_negative")),
        sa.CheckConstraint(
            "rate_override_minor IS NULL OR rate_override_minor > 0",
            name=op.f("ck_room_inventory_rate_positive"),
        ),
    )
    # Covers only the rows that can *fail* a search — a tiny fraction of the
    # calendar, since sparse means "no row" already implies available.
    op.create_index(
        "ix_room_inventory_unavailable",
        "room_inventory",
        ["room_type_id", "stay_date"],
        postgresql_where=sa.text("is_blocked OR units_booked >= units_total"),
    )
    op.create_index("ix_room_inventory_purge", "room_inventory", ["stay_date"])


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_room_types_sync_search ON room_types")
    op.execute("DROP FUNCTION IF EXISTS sync_property_search_columns()")
    op.execute("DROP TRIGGER IF EXISTS trg_room_types_updated_at ON room_types")
    op.execute("DROP TRIGGER IF EXISTS trg_properties_updated_at ON properties")

    op.drop_table("room_inventory")
    op.drop_table("property_images")
    op.drop_table("room_types")
    op.drop_table("properties")
    op.drop_table("amenities")
    op.drop_table("cities")
