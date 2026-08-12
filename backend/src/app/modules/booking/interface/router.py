"""Booking HTTP endpoints.

``POST /bookings`` **requires an ``Idempotency-Key``**, unlike every other
endpoint where it is optional. Mobile networks retry, users double-tap, and
load balancers replay requests whose response was lost — and each of those,
without a key, is a second room held and a second card charged. It is the one
place where refusing the request outright is safer than guessing.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.errors import ValidationError
from app.core.serialization import dto_dict
from app.infrastructure.cache.idempotency import StoredResponse
from app.interface.api.deps import ActorDep, IdempotencyDep
from app.modules.auth.domain.rbac import Permission
from app.modules.auth.interface.permissions import RequirePermission
from app.modules.booking.application import dto
from app.modules.booking.application.use_cases.cancel import (
    CancelBookingUseCase,
    PreviewRefundUseCase,
)
from app.modules.booking.application.use_cases.create import CreateBookingUseCase
from app.modules.booking.application.use_cases.lifecycle import (
    ApproveBookingUseCase,
    ConfirmBookingUseCase,
    RejectBookingUseCase,
)
from app.modules.booking.application.use_cases.query import (
    GetBookingUseCase,
    GetInvoiceUseCase,
    ListGuestBookingsUseCase,
    ListVendorBookingsUseCase,
)
from app.modules.booking.interface import deps
from app.modules.booking.interface.schemas import (
    BookingListResponse,
    BookingResponse,
    CancelBookingRequest,
    ConfirmBookingRequest,
    CreateBookingRequest,
    InvoiceResponse,
    RefundPreviewResponse,
    RejectBookingRequest,
)

guest_router = APIRouter(prefix="/bookings", tags=["bookings"])
vendor_router = APIRouter(prefix="/vendor/bookings", tags=["vendor: bookings"])
internal_router = APIRouter(prefix="/internal/bookings", tags=["internal"])

CanBook = Depends(RequirePermission(Permission.BOOKING_CREATE_OWN))
CanReadVendor = Depends(RequirePermission(Permission.BOOKING_READ_VENDOR))
CanCancelVendor = Depends(RequirePermission(Permission.BOOKING_CANCEL_VENDOR))


def _to_response(view: dto.BookingView) -> BookingResponse:
    payload = dto_dict(view) | {
        "nightly_rates": [dto_dict(n) for n in view.nightly_rates],
        "refund": dto_dict(view.refund) if view.refund else None,
    }
    return BookingResponse(**payload)


# ══════════════════════════════════════════════════════════════════════════
# Guest
# ══════════════════════════════════════════════════════════════════════════


@guest_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BookingResponse,
    dependencies=[CanBook],
    summary="Reserve a room (takes the hold)",
    responses={
        409: {
            "description": (
                "`BOOKING_DATES_UNAVAILABLE` — someone else took the last room; "
                "`BOOKING_PRICE_CHANGED` — the price moved since your quote."
            )
        },
        422: {"description": "Invalid dates, party size, or a stay below the minimum"},
    },
)
async def create_booking(
    body: CreateBookingRequest,
    actor: ActorDep,
    store: IdempotencyDep,
    use_case: Annotated[CreateBookingUseCase, Depends(deps.create_booking_uc)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> BookingResponse:
    """Take the rooms and start the payment clock.

    On success the inventory is **already held** — no other guest can take
    those nights — and `hold_expires_in` counts down the seconds to pay. The
    hold and the booking row are written in one transaction, so a booking never
    exists without the inventory behind it.

    The server re-prices from the property's own engine and returns **409
    BOOKING_PRICE_CHANGED** rather than charging a different amount than the
    one shown.

    **`Idempotency-Key` is required here.** Without it a retried request holds
    a second set of rooms and charges a second time.
    """
    if not idempotency_key or len(idempotency_key) < 8:
        raise ValidationError(
            "An Idempotency-Key header is required when creating a booking.",
            details={"header": "Idempotency-Key", "min_length": 8},
        )

    # The key is *honoured*, not merely demanded. Requiring the header and then
    # ignoring it is worse than not requiring it: the client believes its retry
    # is safe and it is not.
    #
    # The fingerprint covers the actor and the body, so replaying a key with a
    # different stay is a conflict rather than a silent return of the wrong
    # booking, and one guest cannot replay another's key.
    actor_id = str(actor.user_id)
    fingerprint = store.fingerprint("POST", "/bookings", body.model_dump_json().encode(), actor_id)

    replayed = await store.begin(idempotency_key, fingerprint, actor_id)
    if replayed is not None:
        # The first attempt already succeeded; this is the retry.
        return BookingResponse.model_validate(replayed.body)

    try:
        view = await use_case.execute(dto.CreateBookingInput(**body.model_dump()), actor)
    except Exception:
        # Release the key so the client's next attempt can succeed. Only a
        # successful response is worth replaying — pinning a failed key for
        # twenty-four hours would block the very retry that should work.
        await store.abandon(idempotency_key, actor_id)
        raise

    response = _to_response(view)
    await store.complete(
        idempotency_key,
        actor_id,
        fingerprint,
        StoredResponse(
            status_code=status.HTTP_201_CREATED,
            body=response.model_dump(mode="json"),
            headers={},
        ),
    )
    return response


@guest_router.get("", response_model=BookingListResponse, summary="Your booking history")
async def list_bookings(
    actor: ActorDep,
    use_case: Annotated[ListGuestBookingsUseCase, Depends(deps.list_guest_bookings_uc)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    upcoming: bool = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> BookingListResponse:
    """Newest first, cursor-paged.

    A frequent traveller's history is unbounded, and a new booking arriving
    mid-scroll would shift every offset page below it.
    """
    view = await use_case.execute((status_filter, upcoming, limit, cursor), actor)
    return BookingListResponse(
        items=[_to_response(v) for v in view.items], next_cursor=view.next_cursor
    )


@guest_router.get(
    "/{identifier}",
    response_model=BookingResponse,
    summary="Booking detail",
    responses={404: {"description": "No booking with that id or reference that you may see"}},
)
async def get_booking(
    identifier: str,
    actor: ActorDep,
    use_case: Annotated[GetBookingUseCase, Depends(deps.get_booking_uc)],
) -> BookingResponse:
    """Accepts an id **or** the reference a guest reads out to support.

    Someone else's booking is **404**, never 403 — a 403 would confirm the
    reference exists and make this endpoint an oracle for guessing them.

    The property's exact address appears only once the booking is confirmed.
    """
    return _to_response(await use_case.execute(identifier, actor))


@guest_router.get(
    "/{booking_id}/refund-preview",
    response_model=RefundPreviewResponse,
    summary="What cancelling now would refund",
)
async def preview_refund(
    booking_id: uuid.UUID,
    actor: ActorDep,
    use_case: Annotated[PreviewRefundUseCase, Depends(deps.preview_refund_uc)],
) -> RefundPreviewResponse:
    """Read-only. Show this **before** the confirm button.

    Includes the full policy ladder, so the guest can see that waiting another
    day would cost them half the refund — which is information they can act on.
    """
    return RefundPreviewResponse(**await use_case.execute(booking_id, actor))


@guest_router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking",
    responses={409: {"description": "Already cancelled, completed, or in-stay"}},
)
async def cancel_booking(
    booking_id: uuid.UUID,
    body: CancelBookingRequest,
    actor: ActorDep,
    use_case: Annotated[CancelBookingUseCase, Depends(deps.cancel_booking_uc)],
) -> BookingResponse:
    """Cancel and compute the refund.

    The refund is calculated from the charges **recorded on this booking**, not
    from today's rates — a guest who paid ₹47,000 is refunded against ₹47,000
    even if the vendor has since raised their price.

    Inventory is released immediately. The money moves shortly after, through
    the outbox: calling the gateway inside this transaction would hold it open
    across a third-party network call, and a gateway success with a failed
    commit would refund a booking that is still confirmed.

    Who cancels matters — a vendor cancelling on a guest refunds in full
    regardless of the policy.
    """
    view = await use_case.execute(
        dto.CancelBookingInput(booking_id=booking_id, reason=body.reason), actor
    )
    return _to_response(view)


@guest_router.get(
    "/{booking_id}/invoice",
    response_model=InvoiceResponse,
    summary="Tax invoice",
    responses={409: {"description": "Issued once the booking is confirmed"}},
)
async def get_invoice(
    booking_id: uuid.UUID,
    actor: ActorDep,
    use_case: Annotated[GetInvoiceUseCase, Depends(deps.get_invoice_uc)],
) -> InvoiceResponse:
    """A GST invoice with a gapless sequential number.

    Rendered from the booking rather than stored twice — the booking's charges
    are the single source of the numbers. The *number* is stored, because it
    must be stable and consecutive; two versions of a tax document is the one
    thing an auditor cannot accept.
    """
    view = await use_case.execute(booking_id, actor)
    return InvoiceResponse(**dto_dict(view))


# ══════════════════════════════════════════════════════════════════════════
# Vendor
# ══════════════════════════════════════════════════════════════════════════


@vendor_router.get(
    "",
    response_model=BookingListResponse,
    dependencies=[CanReadVendor],
    summary="Bookings at your properties",
)
async def list_vendor_bookings(
    actor: ActorDep,
    use_case: Annotated[ListVendorBookingsUseCase, Depends(deps.list_vendor_bookings_uc)],
    property_id: uuid.UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> BookingListResponse:
    """The arrivals and departures view.

    Scoped to the caller's own vendor id by the repository query, so a
    `property_id` belonging to someone else simply returns nothing.
    """
    view = await use_case.execute(
        (property_id, status_filter, from_date, to_date, page, size), actor
    )
    return BookingListResponse(items=[_to_response(v) for v in view.items], total=view.total)


@vendor_router.post(
    "/{booking_id}/approve",
    response_model=BookingResponse,
    dependencies=[CanReadVendor],
    summary="Accept a request-to-book",
)
async def approve_booking(
    booking_id: uuid.UUID,
    actor: ActorDep,
    use_case: Annotated[ApproveBookingUseCase, Depends(deps.approve_booking_uc)],
) -> BookingResponse:
    """For properties with instant booking off. The inventory was already held
    while you decided; the guest now gets a payment window."""
    return _to_response(await use_case.execute(booking_id, actor))


@vendor_router.post(
    "/{booking_id}/reject",
    response_model=BookingResponse,
    dependencies=[CanReadVendor],
    summary="Decline a request-to-book",
)
async def reject_booking(
    booking_id: uuid.UUID,
    body: RejectBookingRequest,
    actor: ActorDep,
    use_case: Annotated[RejectBookingUseCase, Depends(deps.reject_booking_uc)],
) -> BookingResponse:
    """Releases the dates immediately — holding them for a booking that will
    never happen is lost revenue and makes the property look sold out."""
    return _to_response(await use_case.execute((booking_id, body.reason), actor))


@vendor_router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    dependencies=[CanCancelVendor],
    summary="Cancel a confirmed booking",
)
async def vendor_cancel(
    booking_id: uuid.UUID,
    body: CancelBookingRequest,
    actor: ActorDep,
    use_case: Annotated[CancelBookingUseCase, Depends(deps.cancel_booking_uc)],
) -> BookingResponse:
    """**Refunds the guest in full, whatever the property's policy says.**

    The guest did nothing wrong and is about to have their trip disrupted; they
    will rebook at today's prices, which are usually higher. A platform that
    applied the cancellation policy here would have vendors dumping low-rate
    bookings every time demand rose.
    """
    view = await use_case.execute(
        dto.CancelBookingInput(booking_id=booking_id, reason=body.reason), actor
    )
    return _to_response(view)


# ══════════════════════════════════════════════════════════════════════════
# Internal
# ══════════════════════════════════════════════════════════════════════════


@internal_router.post(
    "/{booking_id}/confirm",
    response_model=BookingResponse,
    include_in_schema=False,
    summary="Confirm after payment (webhook-driven)",
)
async def confirm_booking(
    booking_id: uuid.UUID,
    body: ConfirmBookingRequest,
    actor: ActorDep,
    use_case: Annotated[ConfirmBookingUseCase, Depends(deps.confirm_booking_uc)],
) -> BookingResponse:
    """Called by the payment module on a verified gateway callback.

    Hidden from the public schema and permission-gated: a guest able to call
    this could confirm a booking without paying.

    Idempotent — gateways retry webhooks, and a retry must not issue a second
    invoice number or send a second confirmation email. Returns **409
    BOOKING_HOLD_EXPIRED** if payment lands after the hold lapsed, in which
    case the payment module refunds.
    """
    view = await use_case.execute(
        dto.ConfirmBookingInput(
            booking_id=booking_id,
            payment_id=body.payment_id,
            paid_amount_minor=body.paid_amount_minor,
        ),
        actor,
    )
    return _to_response(view)
