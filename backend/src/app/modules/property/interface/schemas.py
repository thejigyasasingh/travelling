"""HTTP schemas for the property module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.property.domain.entities import MIN_DESCRIPTION_CHARS

PropertyTypeLiteral = Literal["hotel", "resort", "villa", "apartment", "homestay"]
CancellationLiteral = Literal["flexible", "moderate", "strict", "non_refundable"]
BedTypeLiteral = Literal["single", "double", "queen", "king", "bunk", "sofa_bed", "floor_mattress"]
SortLiteral = Literal[
    "relevance", "price_asc", "price_desc", "rating_desc", "distance_asc", "newest"
]

#: HH:MM, 24-hour. A free-text check-in time cannot be compared, sorted or
#: rendered in the guest's locale.
TimeStr = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
#: Minor units — paise, not rupees. See core/types/money.py.
MoneyMinor = Annotated[int, Field(ge=0, le=100_000_000_00)]


# ══════════════════════════════════════════════════════════════════════════
# Requests — listing
# ══════════════════════════════════════════════════════════════════════════


class CreatePropertyRequest(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    property_type: PropertyTypeLiteral
    line1: str = Field(min_length=3, max_length=200)
    city: str = Field(min_length=2, max_length=120)
    country_code: str = Field(min_length=2, max_length=2, description="ISO-3166 alpha-2")
    state: str | None = Field(default=None, max_length=120)
    line2: str | None = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=16)
    landmark: str | None = Field(default=None, max_length=200)
    description: str = Field(default="", max_length=10_000)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    currency: str = Field(default="INR", min_length=3, max_length=3)
    city_id: uuid.UUID | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Sea Breeze Villa",
                "property_type": "villa",
                "line1": "Plot 12, Anjuna Beach Road",
                "city": "Anjuna",
                "state": "Goa",
                "country_code": "IN",
                "postal_code": "403509",
                "latitude": 15.5736,
                "longitude": 73.7407,
            }
        }
    )

    @model_validator(mode="after")
    def _coordinates_come_in_pairs(self) -> CreatePropertyRequest:
        if (self.latitude is None) != (self.longitude is None):
            msg = "latitude and longitude must be provided together"
            raise ValueError(msg)
        return self

    @field_validator("country_code")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class UpdatePropertyRequest(BaseModel):
    """Every field optional — this is a PATCH.

    Address fields are merged against the current address server-side, so
    sending only ``postal_code`` does not blank the street.
    """

    name: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=16)
    landmark: str | None = Field(default=None, max_length=200)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    amenity_codes: list[str] | None = Field(default=None, max_length=100)
    cancellation_policy: CancellationLiteral | None = None
    check_in_from: TimeStr | None = None
    check_out_by: TimeStr | None = None
    house_rules: list[str] | None = Field(default=None, max_length=30)
    instant_booking: bool | None = None
    city_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _coordinates_come_in_pairs(self) -> UpdatePropertyRequest:
        if (self.latitude is None) != (self.longitude is None):
            msg = "latitude and longitude must be provided together"
            raise ValueError(msg)
        return self


class VisibilityRequest(BaseModel):
    action: Literal["publish", "unpublish"]
    reason: str | None = Field(default=None, max_length=500)


class SuspendRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ReviewRequest(BaseModel):
    approve: bool
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description=(
            "Required when rejecting. A rejection the vendor cannot act on "
            "is inventory permanently lost."
        ),
    )

    @model_validator(mode="after")
    def _rejection_needs_a_reason(self) -> ReviewRequest:
        if not self.approve and not (self.reason or "").strip():
            msg = "A reason is required when rejecting a listing"
            raise ValueError(msg)
        return self


# ══════════════════════════════════════════════════════════════════════════
# Requests — rooms, media, calendar
# ══════════════════════════════════════════════════════════════════════════


class CreateRoomTypeRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    base_rate_minor: MoneyMinor = Field(description="Nightly rate in minor units (paise).")
    max_adults: int = Field(default=2, ge=1, le=30)
    max_children: int = Field(default=0, ge=0, le=30)
    total_units: int = Field(default=1, ge=1, le=500)
    bed_type: BedTypeLiteral = "double"
    description: str | None = Field(default=None, max_length=2000)
    size_sqft: int | None = Field(default=None, ge=30, le=100_000)
    amenity_codes: list[str] = Field(default_factory=list, max_length=60)
    weekend_rate_minor: MoneyMinor | None = None
    extra_guest_rate_minor: MoneyMinor | None = None
    included_guests: int = Field(default=2, ge=1, le=30)
    min_nights: int = Field(default=1, ge=1, le=90)
    max_nights: int = Field(default=30, ge=1, le=90)
    cleaning_fee_minor: MoneyMinor | None = Field(
        default=None, description="Charged once per stay, not per night."
    )
    tax_rate: str = Field(default="0.12", description="Decimal string, e.g. 0.12 for 12% GST.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Deluxe Sea View",
                "base_rate_minor": 850000,
                "weekend_rate_minor": 1100000,
                "max_adults": 2,
                "total_units": 6,
                "min_nights": 2,
            }
        }
    )

    @model_validator(mode="after")
    def _nights_are_ordered(self) -> CreateRoomTypeRequest:
        if self.max_nights < self.min_nights:
            msg = "max_nights cannot be below min_nights"
            raise ValueError(msg)
        return self


class UpdateRoomTypeRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    base_rate_minor: MoneyMinor | None = None
    weekend_rate_minor: MoneyMinor | None = None
    extra_guest_rate_minor: MoneyMinor | None = None
    included_guests: int | None = Field(default=None, ge=1, le=30)
    max_adults: int | None = Field(default=None, ge=1, le=30)
    max_children: int | None = Field(default=None, ge=0, le=30)
    total_units: int | None = Field(default=None, ge=1, le=500)
    min_nights: int | None = Field(default=None, ge=1, le=90)
    max_nights: int | None = Field(default=None, ge=1, le=90)
    cleaning_fee_minor: MoneyMinor | None = None
    size_sqft: int | None = Field(default=None, ge=30, le=100_000)
    amenity_codes: list[str] | None = Field(default=None, max_length=60)


class ImageUploadRequest(BaseModel):
    files: list[ImageUploadFile] = Field(min_length=1, max_length=10)


class ImageUploadFile(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["image/jpeg", "image/png", "image/webp", "image/avif"]


class ConfirmImagesRequest(BaseModel):
    """Sent after the direct-to-S3 upload finishes.

    The server verifies each key with a HEAD before creating a row — a client
    that claims an upload it never made would otherwise leave a broken image
    that passes the publish check and renders as a grey box in search.
    """

    storage_keys: list[str] = Field(min_length=1, max_length=10)
    alt_texts: list[str | None] | None = None


class ReorderImagesRequest(BaseModel):
    ordered_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    cover_id: uuid.UUID | None = None


class SetRatesRequest(BaseModel):
    from_date: date
    to_date: date
    rate_minor: MoneyMinor | None = Field(
        default=None,
        description=(
            "Null clears the override, so the date falls back to the weekend or base rate. "
            "That is different from pinning it to the base value."
        ),
    )
    min_nights: int | None = Field(default=None, ge=1, le=90)
    weekdays: list[int] | None = Field(
        default=None,
        description="0=Monday. Restricts the edit, e.g. weekends in December in one call.",
    )

    @field_validator("weekdays")
    @classmethod
    def _valid_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value and any(d < 0 or d > 6 for d in value):
            msg = "weekdays must be between 0 (Monday) and 6 (Sunday)"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _range_is_ordered(self) -> SetRatesRequest:
        if self.to_date <= self.from_date:
            msg = "to_date must be after from_date"
            raise ValueError(msg)
        return self


class SetAvailabilityRequest(BaseModel):
    from_date: date
    to_date: date
    is_blocked: bool | None = None
    units_total: int | None = Field(default=None, ge=0, le=500)

    @model_validator(mode="after")
    def _something_to_do(self) -> SetAvailabilityRequest:
        if self.to_date <= self.from_date:
            msg = "to_date must be after from_date"
            raise ValueError(msg)
        if self.is_blocked is None and self.units_total is None:
            msg = "Provide is_blocked, units_total, or both"
            raise ValueError(msg)
        return self


# ══════════════════════════════════════════════════════════════════════════
# Responses
# ══════════════════════════════════════════════════════════════════════════


class ImageResponse(BaseModel):
    id: uuid.UUID
    url: str
    position: int
    is_cover: bool
    alt_text: str | None = None
    caption: str | None = None


class RoomTypeResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    bed_type: str
    max_adults: int
    max_children: int
    total_units: int
    size_sqft: int | None
    amenity_codes: list[str]
    base_rate_minor: int
    currency: str
    min_nights: int
    units_available: int | None = Field(
        default=None, description="Only when the request carried dates."
    )
    quote_total_minor: int | None = None
    quote_breakdown: dict[str, Any] | None = None


class PropertyResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    property_type: str
    status: str
    description: str
    address: str
    city: str
    state: str | None
    country_code: str
    latitude: float | None
    longitude: float | None
    location_is_approximate: bool = Field(
        description="True for unbooked guests — the pin is ~1 km, not the doorstep."
    )
    amenity_codes: list[str]
    images: list[ImageResponse]
    room_types: list[RoomTypeResponse]
    cancellation_policy: str
    check_in_from: str
    check_out_by: str
    house_rules: list[str]
    instant_booking: bool
    review_average: float
    review_count: int
    currency: str
    vendor_id: uuid.UUID
    published_at: datetime | None = None
    missing_for_publication: list[str] | None = Field(
        default=None, description="Vendor and admin views only."
    )
    rejection_reason: str | None = None


class SearchItemResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    property_type: str
    city: str
    country_code: str
    latitude: float | None
    longitude: float | None
    distance_m: float | None
    cover_image_url: str | None
    review_average: float
    review_count: int
    amenity_codes: list[str]
    instant_booking: bool
    cancellation_policy: str
    max_occupancy: int
    from_price_minor: int | None
    total_price_minor: int | None
    currency: str
    is_available: bool


class SearchResponse(BaseModel):
    items: list[SearchItemResponse]
    next_cursor: str | None = Field(
        default=None, description="Pass back as `cursor`. Opaque — do not construct one."
    )
    total_estimate: int | None = Field(
        default=None, description="Capped at 200; render as '200+' above that."
    )
    applied_radius_m: int | None = None


class CalendarDayResponse(BaseModel):
    date: date
    units_total: int
    units_booked: int
    units_available: int
    is_blocked: bool
    rate_minor: int
    rate_source: Literal["override", "weekend", "base"]
    min_nights: int
    is_default: bool = Field(
        description="True when no row exists and these are the room-type defaults."
    )


class CalendarResponse(BaseModel):
    room_type_id: uuid.UUID
    room_type_name: str
    currency: str
    from_date: date
    to_date: date
    days: list[CalendarDayResponse]


class VendorPropertyListResponse(BaseModel):
    items: list[PropertyResponse]
    total: int
    page: int
    size: int


class AmenityResponse(BaseModel):
    code: str
    label: str
    category: str
    icon: str | None = None
    is_filterable: bool = False


class SuggestionResponse(BaseModel):
    kind: Literal["city", "property"]
    id: str
    label: str
    sublabel: str | None = None
    slug: str


class PublishChecklistResponse(BaseModel):
    """What still stands between a draft and a live listing."""

    ready: bool
    missing: list[str]
    min_description_chars: int = MIN_DESCRIPTION_CHARS


# Deferred model resolution: ImageUploadRequest references ImageUploadFile
# before it is defined.
ImageUploadRequest.model_rebuild()


class QuoteRequest(BaseModel):
    check_in: date
    check_out: date
    adults: int = Field(default=1, ge=1, le=30)
    children: int = Field(default=0, ge=0, le=30)
    infants: int = Field(default=0, ge=0, le=30)
    rooms: int = Field(default=1, ge=1, le=8)

    @model_validator(mode="after")
    def _dates_are_ordered(self) -> QuoteRequest:
        if self.check_out <= self.check_in:
            msg = "check_out must be after check_in"
            raise ValueError(msg)
        return self


class QuoteNightResponse(BaseModel):
    date: date
    amount_minor: int
    source: str


class QuoteResponse(BaseModel):
    room_type_id: uuid.UUID
    nights: list[QuoteNightResponse]
    accommodation_minor: int
    extra_guest_minor: int
    cleaning_fee_minor: int
    tax_minor: int
    total_minor: int
    average_nightly_minor: int
    currency: str
    is_available: bool
    unavailable_dates: list[date] = Field(
        default_factory=list,
        description="Which nights blocked the stay, so the UI can offer alternatives.",
    )
