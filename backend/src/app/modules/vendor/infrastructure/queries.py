"""Vendor-scoped reporting.

Every query here takes a `vendor_id` and filters on it in SQL. That is not
belt-and-braces: a reporting query with a forgotten predicate shows one host
another's revenue, and it is the single most damaging bug this file could have.
The parameter is required — never defaulted, never optional — so omitting it is
a `TypeError` rather than a leak.

Raw SQL for the same reason the admin projections are: these join bookings,
payments and properties, and expressing them through three repositories would
be either a boundary violation or an N+1.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Statuses that represent money the vendor will actually be paid for. An
#: unpaid hold is not earnings, and counting it is how a payout statement
#: disagrees with the bank.
EARNED = "('confirmed','in_stay','completed')"


# ══════════════════════════════════════════════════════════════════════════
# Result rows
#
# Typed rather than ``dict[str, Any]``. These feed response models field for
# field, and with a dict a forgotten key type-checks perfectly and then fails
# as a 500 the first time a real vendor opens the page — which is exactly how
# ``reviews_awaiting`` escaped into a running server. A dataclass makes the
# same mistake a mypy error.
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DashboardRow:
    live_listings: int
    in_review: int
    awaiting_approval: int
    arrivals_this_week: int
    in_stay: int
    gross_30d_minor: int
    commission_30d_minor: int
    #: What the vendor actually receives. Shown alongside gross rather than
    #: instead of it: a host who only sees gross is a host who queries every
    #: payout.
    net_30d_minor: int
    reviews_awaiting: int


@dataclass(frozen=True, slots=True)
class EarningsRow:
    gross_minor: int
    commission_minor: int
    tax_collected_minor: int
    refunded_minor: int
    net_payable_minor: int
    bookings: int
    nights_sold: int
    average_booking_minor: int
    average_nightly_minor: int


@dataclass(frozen=True, slots=True)
class RevenueDayRow:
    day: date
    revenue_minor: int
    bookings: int


@dataclass(frozen=True, slots=True)
class PropertyPerformanceRow:
    property_id: str
    name: str
    city: str
    status: str
    bookings: int
    gross_minor: int
    nights_sold: int
    review_average: float
    review_count: int


@dataclass(frozen=True, slots=True)
class OccupancyRow:
    nights_booked: int
    nights_available: int
    occupancy_percent: float


@dataclass(frozen=True, slots=True)
class ArrivalRow:
    booking_id: str
    reference: str
    guest_name: str
    guest_phone: str | None
    property_name: str
    room_type_name: str
    check_in: date
    check_out: date
    guests: int
    status: str
    total_minor: int
    currency: str


@dataclass(frozen=True, slots=True)
class StatementRow:
    month: date
    bookings: int
    gross_minor: int
    commission_minor: int
    tax_minor: int
    net_minor: int


class VendorQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def dashboard(self, *, vendor_id: uuid.UUID) -> DashboardRow:
        """The portal's landing tiles, in one round trip."""
        row = (
            await self._session.execute(
                text(f"""
                SELECT
                  (SELECT count(*) FROM properties
                    WHERE vendor_id = :v AND status = 'published')            AS live_listings,
                  (SELECT count(*) FROM properties
                    WHERE vendor_id = :v AND status = 'pending_review')       AS in_review,
                  (SELECT count(*) FROM bookings
                    WHERE vendor_id = :v AND status = 'pending_approval')     AS awaiting_approval,
                  (SELECT count(*) FROM bookings
                    WHERE vendor_id = :v AND status IN {EARNED}
                      AND check_in >= CURRENT_DATE
                      AND check_in < CURRENT_DATE + 7)                        AS arrivals_this_week,
                  (SELECT count(*) FROM bookings
                    WHERE vendor_id = :v AND status = 'in_stay')              AS in_stay,
                  (SELECT COALESCE(sum(total_minor), 0) FROM bookings
                    WHERE vendor_id = :v AND status IN {EARNED}
                      AND created_at >= now() - interval '30 days')           AS gross_30d,
                  (SELECT COALESCE(sum(platform_fee_minor), 0) FROM bookings
                    WHERE vendor_id = :v AND status IN {EARNED}
                      AND created_at >= now() - interval '30 days')           AS commission_30d,
                  (SELECT count(*) FROM reviews
                    WHERE vendor_id = :v AND host_reply IS NULL
                      AND moderation <> 'removed')                            AS reviews_awaiting
                """),
                {"v": vendor_id},
            )
        ).one()
        gross, commission = int(row[5]), int(row[6])
        return DashboardRow(
            live_listings=int(row[0]),
            in_review=int(row[1]),
            awaiting_approval=int(row[2]),
            arrivals_this_week=int(row[3]),
            in_stay=int(row[4]),
            gross_30d_minor=gross,
            commission_30d_minor=commission,
            net_30d_minor=max(0, gross - commission),
            reviews_awaiting=int(row[7]),
        )

    async def earnings(
        self, *, vendor_id: uuid.UUID, from_date: date, to_date: date
    ) -> EarningsRow:
        """The payout statement for a period.

        Refunds are subtracted from the period they were *issued* in, not the
        period the booking was made — which is how the platform's ledger works
        and therefore how the bank transfer will look.
        """
        row = (
            await self._session.execute(
                text(f"""
                SELECT
                  COALESCE((SELECT sum(b.total_minor) FROM bookings b
                             WHERE b.vendor_id = :v AND b.status IN {EARNED}
                               AND b.created_at::date BETWEEN :from_date AND :to_date), 0)
                                                                              AS gross,
                  COALESCE((SELECT sum(b.platform_fee_minor) FROM bookings b
                             WHERE b.vendor_id = :v AND b.status IN {EARNED}
                               AND b.created_at::date BETWEEN :from_date AND :to_date), 0)
                                                                              AS commission,
                  COALESCE((SELECT sum(b.tax_minor) FROM bookings b
                             WHERE b.vendor_id = :v AND b.status IN {EARNED}
                               AND b.created_at::date BETWEEN :from_date AND :to_date), 0)
                                                                              AS tax,
                  COALESCE((SELECT sum(r.amount_minor) FROM booking_refunds r
                             JOIN bookings b ON b.id = r.booking_id
                            WHERE b.vendor_id = :v AND r.status = 'completed'
                              AND r.requested_at::date BETWEEN :from_date AND :to_date), 0)
                                                                              AS refunded,
                  (SELECT count(*) FROM bookings b
                    WHERE b.vendor_id = :v AND b.status IN {EARNED}
                      AND b.created_at::date BETWEEN :from_date AND :to_date) AS bookings,
                  COALESCE((SELECT sum(b.check_out - b.check_in) FROM bookings b
                             WHERE b.vendor_id = :v AND b.status IN {EARNED}
                               AND b.created_at::date BETWEEN :from_date AND :to_date), 0)
                                                                              AS nights
                """),
                {"v": vendor_id, "from_date": from_date, "to_date": to_date},
            )
        ).one()

        gross, commission, tax, refunded = (int(row[0]), int(row[1]), int(row[2]), int(row[3]))
        bookings, nights = int(row[4]), int(row[5])
        return EarningsRow(
            gross_minor=gross,
            commission_minor=commission,
            tax_collected_minor=tax,
            refunded_minor=refunded,
            # Tax is remitted, not earned — it is shown so a host can reconcile
            # their GST filing, and excluded from what they are paid.
            net_payable_minor=max(0, gross - commission - refunded - tax),
            bookings=bookings,
            nights_sold=nights,
            average_booking_minor=gross // bookings if bookings else 0,
            average_nightly_minor=gross // nights if nights else 0,
        )

    async def revenue_by_day(self, *, vendor_id: uuid.UUID, days: int = 30) -> list[RevenueDayRow]:
        """Dense: days with no bookings appear as zero, so a chart cannot draw a
        straight line through a bad week."""
        rows = (
            await self._session.execute(
                text(f"""
                SELECT d.day::date,
                       COALESCE(sum(b.total_minor), 0),
                       count(b.id)
                  FROM generate_series(
                         CURRENT_DATE - make_interval(days => :days - 1),
                         CURRENT_DATE, '1 day') AS d(day)
                  LEFT JOIN bookings b
                         ON b.created_at::date = d.day::date
                        AND b.vendor_id = :v
                        AND b.status IN {EARNED}
                 GROUP BY d.day ORDER BY d.day
                """),
                {"v": vendor_id, "days": days},
            )
        ).all()
        return [RevenueDayRow(day=r[0], revenue_minor=int(r[1]), bookings=int(r[2])) for r in rows]

    async def by_property(
        self, *, vendor_id: uuid.UUID, from_date: date, to_date: date
    ) -> list[PropertyPerformanceRow]:
        rows = (
            await self._session.execute(
                text(f"""
                SELECT p.id, p.name, p.city, p.status,
                       count(b.id)                                AS bookings,
                       COALESCE(sum(b.total_minor), 0)            AS gross,
                       COALESCE(sum(b.check_out - b.check_in), 0) AS nights,
                       p.review_average, p.review_count
                  FROM properties p
                  LEFT JOIN bookings b
                         ON b.property_id = p.id
                        AND b.status IN {EARNED}
                        AND b.created_at::date BETWEEN :from_date AND :to_date
                 WHERE p.vendor_id = :v
                 GROUP BY p.id, p.name, p.city, p.status, p.review_average, p.review_count
                 ORDER BY gross DESC
                """),
                {"v": vendor_id, "from_date": from_date, "to_date": to_date},
            )
        ).all()
        return [
            PropertyPerformanceRow(
                property_id=str(r[0]),
                name=r[1],
                city=r[2],
                status=r[3],
                bookings=int(r[4]),
                gross_minor=int(r[5]),
                nights_sold=int(r[6]),
                review_average=float(r[7] or 0),
                review_count=int(r[8] or 0),
            )
            for r in rows
        ]

    async def occupancy(
        self, *, vendor_id: uuid.UUID, from_date: date, to_date: date
    ) -> OccupancyRow:
        """Occupancy across this vendor's managed inventory.

        Only nights the inventory table has a row for are counted. Rows are
        sparse — they exist where a date deviates from the room's defaults — so
        this is occupancy across *managed* nights, not across the calendar. The
        distinction is stated wherever the number is shown, because a host
        comparing it to a hotel's RevPAR would otherwise be comparing two
        different things.
        """
        row = (
            await self._session.execute(
                text("""
                SELECT COALESCE(sum(i.units_booked), 0),
                       COALESCE(sum(i.units_total), 0)
                  FROM room_inventory i
                  JOIN room_types rt ON rt.id = i.room_type_id
                  JOIN properties p  ON p.id = rt.property_id
                 WHERE p.vendor_id = :v
                   AND i.stay_date BETWEEN :from_date AND :to_date
                """),
                {"v": vendor_id, "from_date": from_date, "to_date": to_date},
            )
        ).one()
        booked, available = int(row[0]), int(row[1])
        return OccupancyRow(
            nights_booked=booked,
            nights_available=available,
            occupancy_percent=round(booked / available * 100, 2) if available else 0.0,
        )

    async def upcoming_arrivals(
        self, *, vendor_id: uuid.UUID, days: int = 14, limit: int = 50
    ) -> list[ArrivalRow]:
        """Who is turning up, and when. The one operational list a host reads
        every morning."""
        rows = (
            await self._session.execute(
                text(f"""
                SELECT b.id, b.reference, b.guest_name, b.guest_phone,
                       b.property_name, b.room_type_name, b.check_in, b.check_out,
                       b.adults + b.children AS guests, b.status, b.total_minor, b.currency
                  FROM bookings b
                 WHERE b.vendor_id = :v
                   AND b.status IN {EARNED}
                   AND b.check_in BETWEEN CURRENT_DATE AND CURRENT_DATE + CAST(:days AS integer)
                 ORDER BY b.check_in, b.property_name
                 LIMIT :limit
                """),
                {"v": vendor_id, "days": days, "limit": limit},
            )
        ).all()
        return [
            ArrivalRow(
                booking_id=str(r[0]),
                reference=r[1],
                guest_name=r[2],
                guest_phone=r[3],
                property_name=r[4],
                room_type_name=r[5],
                check_in=r[6],
                check_out=r[7],
                guests=int(r[8]),
                status=r[9],
                total_minor=int(r[10]),
                currency=r[11],
            )
            for r in rows
        ]

    async def monthly_statement(
        self, *, vendor_id: uuid.UUID, months: int = 12
    ) -> list[StatementRow]:
        """Month by month, for the reports screen and the CSV export."""
        rows = (
            await self._session.execute(
                text(f"""
                SELECT date_trunc('month', b.created_at)::date AS month,
                       count(*)                                AS bookings,
                       COALESCE(sum(b.total_minor), 0)         AS gross,
                       COALESCE(sum(b.platform_fee_minor), 0)  AS commission,
                       COALESCE(sum(b.tax_minor), 0)           AS tax
                  FROM bookings b
                 WHERE b.vendor_id = :v
                   AND b.status IN {EARNED}
                   AND b.created_at >= date_trunc('month', now()) - make_interval(months => :months)
                 GROUP BY month
                 ORDER BY month DESC
                """),
                {"v": vendor_id, "months": months},
            )
        ).all()
        return [
            StatementRow(
                month=r[0],
                bookings=int(r[1]),
                gross_minor=int(r[2]),
                commission_minor=int(r[3]),
                tax_minor=int(r[4]),
                net_minor=max(0, int(r[2]) - int(r[3]) - int(r[4])),
            )
            for r in rows
        ]
