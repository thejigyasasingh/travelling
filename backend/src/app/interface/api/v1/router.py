"""v1 API router.

**Versioned from day one.** Adding ``/v1`` before there is a ``/v2`` costs one
path segment; retrofitting versioning onto a shipped mobile app that cannot be
force-updated costs a migration project. Mobile clients live on users' phones
for years — some fraction of traffic will always be from a build you shipped
long ago.

Module routers are mounted here as they land. Each module owns its own router
and knows nothing about this file beyond exporting one; that is what keeps a
new module from touching shared code.

Mount order is alphabetical except where a static path must win over a
parameterised one (``/properties/featured`` before ``/properties/{id}``, or the
literal is swallowed by the parameter).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.admin.interface.router import router as admin_router
from app.modules.ai.interface.router import admin_router as ai_admin_router
from app.modules.ai.interface.router import router as ai_router
from app.modules.ai.interface.router import vendor_router as ai_vendor_router
from app.modules.auth.interface.router import router as auth_router
from app.modules.booking.interface.router import guest_router as booking_guest_router
from app.modules.booking.interface.router import internal_router as booking_internal_router
from app.modules.booking.interface.router import vendor_router as booking_vendor_router
from app.modules.coupon.interface.router import admin_router as coupon_admin_router
from app.modules.coupon.interface.router import router as coupon_router
from app.modules.payment.interface.router import admin_router as payment_admin_router
from app.modules.payment.interface.router import router as payment_router
from app.modules.payment.interface.router import webhook_router as payment_webhook_router
from app.modules.property.interface.router import admin_router as property_admin_router
from app.modules.property.interface.router import public_router as property_public_router
from app.modules.property.interface.router import vendor_router as property_vendor_router
from app.modules.review.interface.router import admin_router as review_admin_router
from app.modules.review.interface.router import router as review_router
from app.modules.review.interface.router import vendor_router as review_vendor_router
from app.modules.support.interface.router import admin_router as support_admin_router
from app.modules.support.interface.router import router as support_router
from app.modules.vendor.interface.router import admin_router as vendor_admin_router
from app.modules.vendor.interface.router import router as vendor_router
from app.modules.wishlist.interface.router import router as wishlist_router

api_router = APIRouter(prefix="/api/v1")

# ── module routers ────────────────────────────────────────────────────────
# An explicit list, not package auto-discovery: an import that happens by
# directory scan is an import you cannot trace, and a module that registers
# itself by side effect is one you cannot disable in a hurry.
api_router.include_router(auth_router)
api_router.include_router(property_public_router)
api_router.include_router(property_vendor_router)
api_router.include_router(property_admin_router)
api_router.include_router(booking_guest_router)
api_router.include_router(booking_vendor_router)
api_router.include_router(booking_internal_router)
api_router.include_router(payment_router)
api_router.include_router(payment_admin_router)
# Unauthenticated by design — the HMAC signature is the authentication — and
# exempt from rate limiting, because a throttled webhook makes Razorpay retry
# and eventually give up on a real payment. See `_WEBHOOK` in the rate-limit
# middleware, which matches this exact prefix.
api_router.include_router(payment_webhook_router)
api_router.include_router(vendor_router)
api_router.include_router(coupon_router)
api_router.include_router(support_router)
api_router.include_router(review_router)
api_router.include_router(review_vendor_router)

# ── admin surface ─────────────────────────────────────────────────────────
# Every route on these requires a permission — there is no merely-authenticated
# admin endpoint. Mounted last so a more specific path (`/admin/coupons`) is
# never shadowed by a parameterised one.
api_router.include_router(admin_router)
api_router.include_router(vendor_admin_router)
api_router.include_router(coupon_admin_router)
api_router.include_router(support_admin_router)
api_router.include_router(review_admin_router)
api_router.include_router(wishlist_router)
api_router.include_router(ai_router)
api_router.include_router(ai_vendor_router)
api_router.include_router(ai_admin_router)

# Wired as each module lands (Phase 12+):
#   api_router.include_router(review_router)
#   ...


@api_router.get("/ping", tags=["meta"], summary="Connectivity check")
async def ping() -> dict[str, str]:
    """Cheapest possible authenticated-path check for clients and smoke tests.

    Distinct from ``/health/*``: those are for the orchestrator, this one is on
    the versioned API surface and goes through the full middleware stack, so it
    proves that CORS, rate limiting and error handling are all wired.
    """
    return {"status": "ok", "version": "v1"}
