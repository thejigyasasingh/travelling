"""The booking module's **published contract**.

Payments imports from here and from nowhere else inside ``app.modules.booking``
— enforced by a contract in ``.importlinter``.

The dependency runs one way: **payment → booking**. Booking never imports
payment, which is why it emits ``RefundRequested`` and lets payments execute the
gateway call, rather than calling a gateway itself.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.booking.public.contract import BookingPaymentService, BookingSnapshot


def build_booking_payment_service(session: AsyncSession) -> BookingPaymentService:
    """Construct the adapter against the caller's session, so the payment row
    and the booking status move in one transaction."""
    from app.modules.booking.public.adapters import SqlBookingPaymentService

    return SqlBookingPaymentService(session)


__all__ = ["BookingPaymentService", "BookingSnapshot", "build_booking_payment_service"]
