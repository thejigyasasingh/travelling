"""Property HTTP endpoints.

Three audiences, three route groups, and the split is deliberate:

* ``/properties`` and ``/search`` — **public**. Published listings only, exact
  addresses withheld, heavily cached.
* ``/vendor/properties`` — the vendor's own inventory, in any status. Every
  handler is scoped by the vendor id in the caller's token, never by one in
  the request body.
* ``/admin/properties`` — the review queue and suspensions.

Keeping them apart means the public routes cannot accidentally acquire a code
path that returns a draft, and a vendor route cannot accidentally serve
another vendor's data — the scoping is structural rather than a check that
someone has to remember on each new endpoint.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.core.serialization import dto_dict
from app.core.types.date_range import DateRange
from app.core.types.pagination import Cursor
from app.interface.api.deps import ActorDep, OptionalActorDep
from app.modules.auth.domain.rbac import Permission
from app.modules.auth.interface.permissions import RequirePermission
from app.modules.property.application import dto
from app.modules.property.application.use_cases.calendar import (
    GetCalendarUseCase,
    GetPublicAvailabilityUseCase,
    SetAvailabilityUseCase,
    SetRatesUseCase,
)
from app.modules.property.application.use_cases.manage import (
    ChangeVisibilityUseCase,
    CreatePropertyUseCase,
    DeletePropertyUseCase,
    GetPropertyUseCase,
    GetVendorPropertyUseCase,
    ReviewPropertyUseCase,
    SubmitForReviewUseCase,
    UpdatePropertyUseCase,
)
from app.modules.property.application.use_cases.media import (
    ConfirmImagesUseCase,
    DeleteImageUseCase,
    ReorderImagesUseCase,
    RequestImageUploadUseCase,
)
from app.modules.property.application.use_cases.quote import QuoteStayUseCase
from app.modules.property.application.use_cases.rooms import (
    AddRoomTypeUseCase,
    RemoveRoomTypeUseCase,
    UpdateRoomTypeUseCase,
)
from app.modules.property.application.use_cases.search import (
    SearchPropertiesUseCase,
    SuggestUseCase,
)
from app.modules.property.application.views import to_property_view
from app.modules.property.domain.value_objects import (
    CancellationPolicy,
    GeoPoint,
    Occupancy,
    PropertyType,
)
from app.modules.property.interface import deps
from app.modules.property.interface.schemas import (
    AmenityResponse,
    CalendarDayResponse,
    CalendarResponse,
    ConfirmImagesRequest,
    CreatePropertyRequest,
    CreateRoomTypeRequest,
    ImageResponse,
    ImageUploadRequest,
    PropertyResponse,
    PublishChecklistResponse,
    QuoteNightResponse,
    QuoteRequest,
    QuoteResponse,
    ReorderImagesRequest,
    ReviewRequest,
    RoomTypeResponse,
    SearchItemResponse,
    SearchResponse,
    SetAvailabilityRequest,
    SetRatesRequest,
    SuggestionResponse,
    SuspendRequest,
    UpdatePropertyRequest,
    UpdateRoomTypeRequest,
    VendorPropertyListResponse,
    VisibilityRequest,
)

public_router = APIRouter(tags=["properties"])
vendor_router = APIRouter(prefix="/vendor/properties", tags=["vendor: properties"])
admin_router = APIRouter(prefix="/admin/properties", tags=["admin: properties"])

CanManage = Depends(RequirePermission(Permission.PROPERTY_UPDATE_VENDOR))
CanCreate = Depends(RequirePermission(Permission.PROPERTY_CREATE_VENDOR))
CanDelete = Depends(RequirePermission(Permission.PROPERTY_DELETE_VENDOR))
CanPublish = Depends(RequirePermission(Permission.PROPERTY_PUBLISH_ANY))


def _to_property_response(view: dto.PropertyView) -> PropertyResponse:
    """Map a property view, nested objects included.

    ``dto_dict`` is deliberately shallow — it must not recurse, or nested views
    would arrive as anonymous dicts and lose their types. So the nested lists
    are mapped here, explicitly. Handing Pydantic the raw dataclasses instead
    would need ``from_attributes`` on every nested model, which turns a
    validation error into silent structural coercion.
    """
    return PropertyResponse(
        **dto_dict(view, exclude=frozenset({"images", "room_types"})),
        images=[ImageResponse(**dto_dict(image)) for image in view.images],
        room_types=[RoomTypeResponse(**dto_dict(room)) for room in view.room_types],
    )


# ══════════════════════════════════════════════════════════════════════════
# Public — search
# ══════════════════════════════════════════════════════════════════════════


@public_router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search properties",
    responses={422: {"description": "Invalid dates, filters or cursor"}},
)
async def search(
    use_case: Annotated[SearchPropertiesUseCase, Depends(deps.search_uc)],
    urls: deps.UrlsDep,
    actor: OptionalActorDep,
    q: Annotated[str | None, Query(max_length=120, description="Free text")] = None,
    city_id: uuid.UUID | None = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_m: Annotated[int, Query(ge=100, le=100_000)] = dto.DEFAULT_SEARCH_RADIUS_M,
    sw_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    sw_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    ne_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    ne_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    check_in: date | None = None,
    check_out: date | None = None,
    adults: Annotated[int, Query(ge=1, le=30)] = 1,
    children: Annotated[int, Query(ge=0, le=30)] = 0,
    infants: Annotated[int, Query(ge=0, le=30)] = 0,
    rooms: Annotated[int, Query(ge=1, le=8)] = 1,
    property_type: Annotated[list[PropertyType] | None, Query()] = None,
    amenity: Annotated[list[str] | None, Query()] = None,
    min_price: Annotated[int | None, Query(ge=0)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
    instant_booking: bool = False,
    cancellation: Annotated[list[CancellationPolicy] | None, Query()] = None,
    sort: dto.SearchSort = dto.SearchSort.RELEVANCE,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> SearchResponse:
    """Find bookable properties.

    **The enum parameters are typed on the signature, deliberately.** Taking
    them as `str` and calling `SearchSort(value)` in the body raises a
    `ValueError` that escapes to the ASGI layer, where no response is ever
    written — the client then waits until it times out, and enough such
    requests exhaust the worker. A typed parameter is rejected by FastAPI with
    a 422 before the handler runs, which is both the correct status and a
    response that actually gets sent.

    **Pagination is cursor-based.** Pass `meta.next_cursor` back as `cursor`.
    Offset paging would make the last page of a large result set a table scan.

    **`amenity` is AND, not OR** — a guest who ticks pool and pet-friendly
    wants both.

    **Coordinates are approximate** (~1 km) until a booking is confirmed.

    Supplying `check_in`/`check_out` filters to properties actually available
    for every night of the stay, and respects each property's minimum-stay
    rule so results are never dead ends.
    """
    stay = DateRange(check_in, check_out) if check_in and check_out else None
    bounds = None
    if None not in (sw_lat, sw_lng, ne_lat, ne_lng):
        bounds = (GeoPoint(sw_lat, sw_lng), GeoPoint(ne_lat, ne_lng))  # type: ignore[arg-type]

    criteria = dto.SearchCriteria(
        query=q,
        city_id=city_id,
        near=GeoPoint(lat, lng) if lat is not None and lng is not None else None,
        radius_m=radius_m,
        bounds=bounds,
        stay=stay,
        occupancy=Occupancy(adults=adults, children=children, infants=infants),
        rooms=rooms,
        property_types=frozenset(property_type or []),
        amenity_codes=frozenset(amenity or []),
        min_price_minor=min_price,
        max_price_minor=max_price,
        min_rating=Decimal(str(min_rating)) if min_rating is not None else None,
        instant_booking_only=instant_booking,
        cancellation_policies=frozenset(cancellation or []),
        sort=sort,
        limit=limit,
        cursor=Cursor.decode(cursor) if cursor else None,
    )

    results = await use_case.execute(criteria, actor)
    return SearchResponse(
        items=[
            SearchItemResponse(
                **dto_dict(item, exclude=frozenset({"cover_image_key"})),
                cover_image_url=(
                    urls.public_url(item.cover_image_key) if item.cover_image_key else None
                ),
            )
            for item in results.items
        ],
        next_cursor=results.next_cursor,
        total_estimate=results.total_estimate,
        applied_radius_m=results.applied_radius_m,
    )


@public_router.get(
    "/search/suggest",
    response_model=list[SuggestionResponse],
    summary="Type-ahead for the search box",
)
async def suggest(
    use_case: Annotated[SuggestUseCase, Depends(deps.suggest_uc)],
    actor: OptionalActorDep,
    q: Annotated[str, Query(min_length=1, max_length=80)] = "",
) -> list[SuggestionResponse]:
    """Cities rank above properties — someone typing "goa" means the
    destination, not a hotel that happens to be named after it."""
    rows = await use_case.execute(q, actor)
    return [SuggestionResponse(**row) for row in rows]


@public_router.get(
    "/amenities", response_model=list[AmenityResponse], summary="The amenity catalogue"
)
async def list_amenities(
    catalog: Annotated[Any, Depends(deps.amenity_catalog)],
    filterable_only: bool = False,
) -> list[AmenityResponse]:
    """Codes are the contract; labels and icons are presentation and may
    change or be translated."""
    codes = await catalog.known_codes()
    described = await catalog.describe(sorted(codes))
    items = [AmenityResponse(**row) for row in described]
    return [a for a in items if a.is_filterable] if filterable_only else items


# ══════════════════════════════════════════════════════════════════════════
# Public — detail
# ══════════════════════════════════════════════════════════════════════════


@public_router.get(
    "/properties/{identifier}",
    response_model=PropertyResponse,
    summary="Property detail",
    responses={404: {"description": "No published property with that id or slug"}},
)
async def get_property(
    identifier: str,
    use_case: Annotated[GetPropertyUseCase, Depends(deps.get_property_uc)],
    actor: OptionalActorDep,
) -> PropertyResponse:
    """Accepts an id **or** a slug.

    The slug is the shareable, indexable form; the id always resolves even
    after a rename, because the slug deliberately does not follow one.

    Unpublished listings are 404 here — a vendor views their own through the
    vendor route.
    """
    return _to_property_response(await use_case.execute(identifier, actor))


@public_router.get(
    "/properties/{property_id}/availability",
    response_model=CalendarResponse,
    summary="Nightly availability and prices",
)
async def public_availability(
    property_id: uuid.UUID,
    from_date: date,
    to_date: date,
    use_case: Annotated[GetPublicAvailabilityUseCase, Depends(deps.public_availability_uc)],
    actor: OptionalActorDep,
) -> CalendarResponse:
    """Drives the date picker.

    Unit counts are deliberately **not** returned — "only 1 left!" is a
    pressure tactic that also tells a competitor exactly how full a property
    is. A boolean is all a guest needs.
    """
    view = await use_case.execute((property_id, from_date, to_date), actor)
    return _calendar_response(view)


@public_router.post(
    "/properties/{property_id}/quote",
    response_model=QuoteResponse,
    summary="Price a specific stay",
    responses={422: {"description": "Stay too short/long, or party too large"}},
)
async def quote(
    property_id: uuid.UUID,
    body: QuoteRequest,
    use_case: Annotated[QuoteStayUseCase, Depends(deps.quote_uc)],
    actor: OptionalActorDep,
    room_type_id: uuid.UUID | None = None,
) -> QuoteResponse:
    """Full per-night breakdown, so "why ₹47,000?" is answerable from the
    response.

    Returns a price **and** availability rather than refusing when sold out —
    the blocking dates come back too, so the UI can offer adjacent nights
    instead of a dead end.

    The booking endpoint re-computes this server-side before charging; a quote
    is a snapshot, and rates or availability can move between seeing it and
    paying.
    """
    stay = DateRange(body.check_in, body.check_out)
    occupancy = Occupancy(adults=body.adults, children=body.children, infants=body.infants)
    result = await use_case.execute((property_id, room_type_id, stay, occupancy, body.rooms), actor)
    q = result.quote
    return QuoteResponse(
        room_type_id=result.room_type_id,
        nights=[
            QuoteNightResponse(
                date=n.stay_date, amount_minor=n.amount.amount_minor, source=n.source
            )
            for n in q.nights
        ],
        accommodation_minor=q.accommodation.amount_minor,
        extra_guest_minor=q.extra_guest_total.amount_minor,
        cleaning_fee_minor=q.cleaning_fee.amount_minor,
        tax_minor=q.tax.amount_minor,
        total_minor=q.total.amount_minor,
        average_nightly_minor=q.average_nightly.amount_minor,
        currency=q.currency,
        is_available=result.is_available,
        unavailable_dates=list(result.unavailable_dates),
    )


# ══════════════════════════════════════════════════════════════════════════
# Vendor — listings
# ══════════════════════════════════════════════════════════════════════════


@vendor_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PropertyResponse,
    dependencies=[CanCreate],
    summary="Create a draft listing",
)
async def create_property(
    body: CreatePropertyRequest,
    use_case: Annotated[CreatePropertyUseCase, Depends(deps.create_property_uc)],
    actor: ActorDep,
) -> PropertyResponse:
    """Starts as a draft with almost nothing required.

    Completeness is demanded at submission, not here — asking for photos,
    coordinates and a 120-character description on the first screen is where
    vendor onboarding dies.
    """
    view = await use_case.execute(dto.CreatePropertyInput(**body.model_dump()), actor)
    return _to_property_response(view)


@vendor_router.get("", response_model=VendorPropertyListResponse, summary="Your listings")
async def list_vendor_properties(
    uow: deps.PropUow,
    urls: deps.UrlsDep,
    actor: ActorDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> VendorPropertyListResponse:
    """Offset paging, unlike search: this is one vendor's portfolio — small,
    bounded, and page numbers are what a dashboard wants."""
    if actor.vendor_id is None:
        return VendorPropertyListResponse(items=[], total=0, page=page, size=size)

    items, total = await uow.properties.list_for_vendor(
        actor.vendor_id, status=status_filter, limit=size, offset=(page - 1) * size
    )
    return VendorPropertyListResponse(
        items=[
            _to_property_response(to_property_view(p, urls=urls, include_private=True))
            for p in items
        ],
        total=total,
        page=page,
        size=size,
    )


@vendor_router.get(
    "/{property_id}", response_model=PropertyResponse, summary="Your listing, any status"
)
async def get_vendor_property(
    property_id: uuid.UUID,
    use_case: Annotated[GetVendorPropertyUseCase, Depends(deps.get_vendor_property_uc)],
    actor: ActorDep,
) -> PropertyResponse:
    """Includes the exact address and `missing_for_publication`. Another
    vendor's id is 404, never 403 — a 403 would confirm it exists."""
    return _to_property_response(await use_case.execute(property_id, actor))


@vendor_router.patch(
    "/{property_id}",
    response_model=PropertyResponse,
    dependencies=[CanManage],
    summary="Update a listing",
)
async def update_property(
    property_id: uuid.UUID,
    body: UpdatePropertyRequest,
    use_case: Annotated[UpdatePropertyUseCase, Depends(deps.update_property_uc)],
    actor: ActorDep,
) -> PropertyResponse:
    """Partial. Address fields are merged with the current address, so sending
    only `postal_code` does not blank the street."""
    view = await use_case.execute(
        dto.UpdatePropertyInput(property_id=property_id, **body.model_dump()), actor
    )
    return _to_property_response(view)


@vendor_router.get(
    "/{property_id}/checklist",
    response_model=PublishChecklistResponse,
    summary="What is still missing before publishing",
)
async def publish_checklist(
    property_id: uuid.UUID,
    use_case: Annotated[GetVendorPropertyUseCase, Depends(deps.get_vendor_property_uc)],
    actor: ActorDep,
) -> PublishChecklistResponse:
    """Everything at once, not one item at a time — a vendor fixing one thing
    and discovering the next is how listings get abandoned."""
    view = await use_case.execute(property_id, actor)
    missing = view.missing_for_publication or []
    return PublishChecklistResponse(ready=not missing, missing=missing)


@vendor_router.post(
    "/{property_id}/submit",
    response_model=PropertyResponse,
    dependencies=[CanManage],
    summary="Submit for review",
    responses={409: {"description": "Listing is incomplete — see `details.missing`"}},
)
async def submit_for_review(
    property_id: uuid.UUID,
    use_case: Annotated[SubmitForReviewUseCase, Depends(deps.submit_for_review_uc)],
    actor: ActorDep,
) -> PropertyResponse:
    return _to_property_response(await use_case.execute(property_id, actor))


@vendor_router.post(
    "/{property_id}/visibility",
    response_model=PropertyResponse,
    dependencies=[CanManage],
    summary="Publish or unpublish",
)
async def change_visibility(
    property_id: uuid.UUID,
    body: VisibilityRequest,
    use_case: Annotated[ChangeVisibilityUseCase, Depends(deps.change_visibility_uc)],
    actor: ActorDep,
) -> PropertyResponse:
    """Unpublishing keeps everything — a hotel closing for monsoon season
    should not have to rebuild its listing in October.

    Republishing an already-vetted listing skips the review queue but still
    re-checks completeness, in case photos were deleted while it was down.
    """
    view = await use_case.execute((property_id, body.action, body.reason), actor)
    return _to_property_response(view)


@vendor_router.delete(
    "/{property_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[CanDelete],
    summary="Delete a listing",
    responses={409: {"description": "Unpublish it first"}},
)
async def delete_property(
    property_id: uuid.UUID,
    use_case: Annotated[DeletePropertyUseCase, Depends(deps.delete_property_uc)],
    actor: ActorDep,
) -> None:
    """Soft delete. Bookings, invoices and payouts reference this listing for
    years and must stay reconstructable, so the row leaves every view but not
    the database."""
    await use_case.execute(property_id, actor)


# ══════════════════════════════════════════════════════════════════════════
# Vendor — room types
# ══════════════════════════════════════════════════════════════════════════


@vendor_router.post(
    "/{property_id}/room-types",
    status_code=status.HTTP_201_CREATED,
    response_model=RoomTypeResponse,
    dependencies=[CanManage],
    summary="Add a room type",
    responses={409: {"description": "Duplicate name, or a whole-unit property already has one"}},
)
async def add_room_type(
    property_id: uuid.UUID,
    body: CreateRoomTypeRequest,
    use_case: Annotated[AddRoomTypeUseCase, Depends(deps.add_room_uc)],
    actor: ActorDep,
) -> RoomTypeResponse:
    """A villa or apartment is one bookable unit and may have only one room
    type; hotels and resorts may have many."""
    view = await use_case.execute(
        dto.CreateRoomTypeInput(property_id=property_id, **body.model_dump()), actor
    )
    return RoomTypeResponse(**dto_dict(view))


@vendor_router.patch(
    "/{property_id}/room-types/{room_type_id}",
    response_model=RoomTypeResponse,
    dependencies=[CanManage],
    summary="Update a room type",
    responses={409: {"description": "Reducing units below what is already booked"}},
)
async def update_room_type(
    property_id: uuid.UUID,
    room_type_id: uuid.UUID,
    body: UpdateRoomTypeRequest,
    use_case: Annotated[UpdateRoomTypeUseCase, Depends(deps.update_room_uc)],
    actor: ActorDep,
) -> RoomTypeResponse:
    """Reducing `total_units` is checked against the whole booking horizon:
    dropping from five to two when three are booked in December is an
    overbooking, and it is refused with the offending date."""
    view = await use_case.execute(
        dto.UpdateRoomTypeInput(
            property_id=property_id, room_type_id=room_type_id, **body.model_dump()
        ),
        actor,
    )
    return RoomTypeResponse(**dto_dict(view))


@vendor_router.delete(
    "/{property_id}/room-types/{room_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[CanManage],
    summary="Remove a room type",
)
async def remove_room_type(
    property_id: uuid.UUID,
    room_type_id: uuid.UUID,
    use_case: Annotated[RemoveRoomTypeUseCase, Depends(deps.remove_room_uc)],
    actor: ActorDep,
) -> None:
    """A published listing must keep at least one — otherwise it renders as a
    live page nobody can book."""
    await use_case.execute((property_id, room_type_id), actor)


# ══════════════════════════════════════════════════════════════════════════
# Vendor — images
# ══════════════════════════════════════════════════════════════════════════


@vendor_router.post(
    "/{property_id}/images/upload-url",
    dependencies=[CanManage],
    summary="Get presigned upload URLs",
)
async def request_image_upload(
    property_id: uuid.UUID,
    body: ImageUploadRequest,
    use_case: Annotated[RequestImageUploadUseCase, Depends(deps.request_upload_uc)],
    actor: ActorDep,
) -> list[dict[str, Any]]:
    """Step 1 of 2. Upload the bytes **directly to S3** with the returned
    policy, then call `POST /images` with the keys.

    The API never receives image bytes — proxying a 20 MB photo would occupy a
    worker for the length of a mobile upload. The key is server-generated, and
    the policy pins the content type and a size ceiling that S3 enforces.
    """
    return await use_case.execute(
        dto.RequestImageUploadInput(
            property_id=property_id,
            filenames=[f.filename for f in body.files],
            content_types=[f.content_type for f in body.files],
        ),
        actor,
    )


@vendor_router.post(
    "/{property_id}/images",
    status_code=status.HTTP_201_CREATED,
    response_model=list[ImageResponse],
    dependencies=[CanManage],
    summary="Confirm uploaded images",
    responses={422: {"description": "The upload was not found, or is too small"}},
)
async def confirm_images(
    property_id: uuid.UUID,
    body: ConfirmImagesRequest,
    use_case: Annotated[ConfirmImagesUseCase, Depends(deps.confirm_images_uc)],
    actor: ActorDep,
) -> list[ImageResponse]:
    """Step 2 of 2. Each key is verified with a HEAD against S3 before a row
    is created — a client claiming an upload it never made would otherwise
    leave a broken image that passes the publish check."""
    views = await use_case.execute(
        dto.ConfirmImageInput(
            property_id=property_id, storage_keys=body.storage_keys, alt_texts=body.alt_texts
        ),
        actor,
    )
    return [ImageResponse(**dto_dict(v)) for v in views]


@vendor_router.patch(
    "/{property_id}/images",
    response_model=list[ImageResponse],
    dependencies=[CanManage],
    summary="Reorder images or set the cover",
)
async def reorder_images(
    property_id: uuid.UUID,
    body: ReorderImagesRequest,
    use_case: Annotated[ReorderImagesUseCase, Depends(deps.reorder_images_uc)],
    actor: ActorDep,
) -> list[ImageResponse]:
    views = await use_case.execute((property_id, body.ordered_ids, body.cover_id), actor)
    return [ImageResponse(**dto_dict(v)) for v in views]


@vendor_router.delete(
    "/{property_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[CanManage],
    summary="Remove an image",
    responses={409: {"description": "Set another cover image first"}},
)
async def delete_image(
    property_id: uuid.UUID,
    image_id: uuid.UUID,
    use_case: Annotated[DeleteImageUseCase, Depends(deps.delete_image_uc)],
    actor: ActorDep,
) -> None:
    """The S3 object is deleted asynchronously by the `ImageRemoved` consumer —
    an inline delete inside the transaction would lose the object if the
    transaction then rolled back."""
    await use_case.execute((property_id, image_id), actor)


# ══════════════════════════════════════════════════════════════════════════
# Vendor — calendar
# ══════════════════════════════════════════════════════════════════════════


@vendor_router.get(
    "/{property_id}/room-types/{room_type_id}/calendar",
    response_model=CalendarResponse,
    summary="Rates and availability, day by day",
)
async def get_calendar(
    property_id: uuid.UUID,
    room_type_id: uuid.UUID,
    from_date: date,
    to_date: date,
    use_case: Annotated[GetCalendarUseCase, Depends(deps.get_calendar_uc)],
    actor: ActorDep,
) -> CalendarResponse:
    """Every day is returned, including ones with no stored row — a calendar
    with gaps is unreadable. `is_default` marks the inherited ones."""
    view = await use_case.execute((property_id, room_type_id, from_date, to_date), actor)
    return _calendar_response(view)


@vendor_router.put(
    "/{property_id}/room-types/{room_type_id}/rates",
    dependencies=[CanManage],
    summary="Set or clear rates over a range",
)
async def set_rates(
    property_id: uuid.UUID,
    room_type_id: uuid.UUID,
    body: SetRatesRequest,
    use_case: Annotated[SetRatesUseCase, Depends(deps.set_rates_uc)],
    actor: ActorDep,
) -> dict[str, int]:
    """Ranged, because that is how vendors think — "₹15,000 for all of
    December". `weekdays` narrows it further.

    `rate_minor: null` **clears** the override so the date falls back to the
    weekend or base rate — deliberately different from pinning it to the same
    number, which would stop following future base-rate changes.
    """
    affected = await use_case.execute(
        dto.SetRatesInput(property_id=property_id, room_type_id=room_type_id, **body.model_dump()),
        actor,
    )
    return {"dates_updated": affected}


@vendor_router.put(
    "/{property_id}/room-types/{room_type_id}/availability",
    dependencies=[CanManage],
    summary="Block dates or change unit counts",
    responses={409: {"description": "Those dates already have confirmed bookings"}},
)
async def set_availability(
    property_id: uuid.UUID,
    room_type_id: uuid.UUID,
    body: SetAvailabilityRequest,
    use_case: Annotated[SetAvailabilityUseCase, Depends(deps.set_availability_uc)],
    actor: ActorDep,
) -> dict[str, int]:
    """Refuses to block a date that already has a booking, or to reduce units
    below what is booked — either would silently invalidate a reservation the
    guest would only discover at the door."""
    affected = await use_case.execute(
        dto.SetAvailabilityInput(
            property_id=property_id, room_type_id=room_type_id, **body.model_dump()
        ),
        actor,
    )
    return {"dates_updated": affected}


# ══════════════════════════════════════════════════════════════════════════
# Admin
# ══════════════════════════════════════════════════════════════════════════


@admin_router.post(
    "/{property_id}/review",
    response_model=PropertyResponse,
    dependencies=[CanPublish],
    summary="Approve or reject a submitted listing",
)
async def review_property(
    property_id: uuid.UUID,
    body: ReviewRequest,
    use_case: Annotated[ReviewPropertyUseCase, Depends(deps.review_property_uc)],
    actor: ActorDep,
) -> PropertyResponse:
    """Approval re-checks completeness: the listing stays editable while it
    sits in the queue, so what passed at submission may no longer hold.

    A rejection requires a reason — one the vendor cannot act on is inventory
    permanently lost.
    """
    view = await use_case.execute(
        dto.ReviewPropertyInput(property_id=property_id, approve=body.approve, reason=body.reason),
        actor,
    )
    return _to_property_response(view)


@admin_router.post(
    "/{property_id}/suspend",
    response_model=PropertyResponse,
    dependencies=[CanPublish],
    summary="Suspend a live listing",
)
async def suspend_property(
    property_id: uuid.UUID,
    body: SuspendRequest,
    use_case: Annotated[ChangeVisibilityUseCase, Depends(deps.change_visibility_uc)],
    actor: ActorDep,
) -> PropertyResponse:
    """For fraud or a guest-safety complaint. Unlike unpublishing, the vendor
    cannot reverse it — only an admin can, and only back to *unpublished*, so
    the vendor must then republish deliberately."""
    view = await use_case.execute((property_id, "suspend", body.reason), actor)
    return _to_property_response(view)


# ══════════════════════════════════════════════════════════════════════════


def _calendar_response(view: dto.CalendarView) -> CalendarResponse:
    return CalendarResponse(
        room_type_id=view.room_type_id,
        room_type_name=view.room_type_name,
        currency=view.currency,
        from_date=view.from_date,
        to_date=view.to_date,
        days=[
            CalendarDayResponse(
                date=day.stay_date,
                units_total=day.units_total,
                units_booked=day.units_booked,
                units_available=day.units_available,
                is_blocked=day.is_blocked,
                rate_minor=day.rate_minor,
                rate_source=day.rate_source,
                min_nights=day.min_nights,
                is_default=day.is_default,
            )
            for day in view.days
        ],
    )
