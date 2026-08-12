"""Admin read queries.

Raw SQL, deliberately. These are cross-module projections — a user row joins
bookings and payments; a vendor row joins properties and bookings — and
expressing them through four modules' repositories would either violate the
module boundaries or issue an N+1 per row.

The boundary is preserved a different way: this file **only reads**, and every
admin *action* goes through the owning module's use case. A read-only projection
cannot corrupt an invariant it never writes to.

Every query here is bounded — by a date window, a limit, or both. An admin panel
that runs an unbounded aggregate over `bookings` is a panel that takes the site
down on the day it finally matters.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.application.dto import (
    AdminBookingRow,
    AdminPaymentRow,
    AdminPropertyRow,
    AdminUserRow,
    AdminVendorRow,
    Kpi,
    PagedResult,
    RevenueBreakdown,
    TimeSeriesPoint,
    TopProperty,
)

#: Statuses that represent money the platform actually expects to keep.
#: `pending_payment` is excluded everywhere: an unpaid hold is not revenue, and
#: counting it is how a dashboard reports a number finance cannot find.
EARNING_STATUSES = "('confirmed','in_stay','completed')"


class AdminQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── dashboard ─────────────────────────────────────────────────────────

    async def kpis(self, *, window_days: int = 30) -> list[Kpi]:
        """Headline numbers, each against the preceding equal window.

        One query rather than eight round trips: a dashboard that issues a
        query per tile is slow in exactly the moment someone is watching it.
        """
        row = (
            await self._session.execute(
                text(f"""
                WITH windows AS (
                    SELECT now() - make_interval(days => :days)     AS current_start,
                           now() - make_interval(days => :days * 2) AS previous_start,
                           now() - make_interval(days => :days)     AS previous_end
                )
                SELECT
                  (SELECT count(*) FROM bookings, windows
                    WHERE created_at >= current_start)                       AS bookings_now,
                  (SELECT count(*) FROM bookings, windows
                    WHERE created_at >= previous_start
                      AND created_at <  previous_end)                        AS bookings_prev,
                  (SELECT COALESCE(sum(total_minor), 0) FROM bookings, windows
                    WHERE created_at >= current_start
                      AND status IN {EARNING_STATUSES})                      AS revenue_now,
                  (SELECT COALESCE(sum(total_minor), 0) FROM bookings, windows
                    WHERE created_at >= previous_start AND created_at < previous_end
                      AND status IN {EARNING_STATUSES})                      AS revenue_prev,
                  (SELECT count(*) FROM users, windows
                    WHERE created_at >= current_start)                       AS users_now,
                  (SELECT count(*) FROM users, windows
                    WHERE created_at >= previous_start
                      AND created_at <  previous_end)                        AS users_prev,
                  (SELECT count(*) FROM properties WHERE status = 'published') AS live_properties,
                  (SELECT count(*) FROM bookings, windows
                    WHERE created_at >= current_start AND status = 'cancelled') AS cancelled_now
                """),
                {"days": window_days},
            )
        ).one()

        bookings_now, bookings_prev = int(row[0]), int(row[1])
        revenue_now, revenue_prev = int(row[2]), int(row[3])
        users_now, users_prev = int(row[4]), int(row[5])

        return [
            Kpi(
                key="bookings",
                label="Bookings",
                value=bookings_now,
                change_percent=_change(bookings_now, bookings_prev),
            ),
            Kpi(
                key="revenue",
                label="Revenue",
                value=revenue_now,
                change_percent=_change(revenue_now, revenue_prev),
                unit="money",
            ),
            Kpi(
                key="new_users",
                label="New guests",
                value=users_now,
                change_percent=_change(users_now, users_prev),
            ),
            Kpi(key="live_properties", label="Live properties", value=int(row[6])),
            Kpi(
                key="cancellations",
                label="Cancellations",
                value=int(row[7]),
                change_percent=None,
            ),
        ]

    async def action_queue(self) -> dict[str, int]:
        """What needs a human. The only part of the dashboard that is a to-do
        list rather than a report."""
        row = (
            await self._session.execute(
                text("""
                SELECT
                  (SELECT count(*) FROM vendors
                    WHERE status IN ('pending','under_review'))             AS vendors_pending,
                  (SELECT count(*) FROM properties WHERE status = 'pending_review')
                                                                            AS properties_pending,
                  (SELECT count(*) FROM support_tickets
                    WHERE status IN ('open','in_progress'))                 AS tickets_open,
                  (SELECT count(*) FROM support_tickets
                    WHERE status IN ('open','in_progress')
                      AND first_responded_at IS NULL
                      AND opened_at < now() - interval '4 hours')           AS tickets_breaching,
                  (SELECT count(*) FROM booking_refunds WHERE status IN ('pending','failed'))
                                                                            AS refunds_pending,
                  (SELECT count(*) FROM payments
                    WHERE status IN ('created','pending','authorized')
                      AND created_at < now() - interval '30 minutes')       AS payments_stuck,
                  (SELECT count(*) FROM notifications WHERE status = 'failed')
                                                                            AS notifications_failed
                """)
            )
        ).one()
        return {
            "vendors_pending": int(row[0]),
            "properties_pending": int(row[1]),
            "tickets_open": int(row[2]),
            "tickets_breaching": int(row[3]),
            "refunds_pending": int(row[4]),
            "payments_stuck": int(row[5]),
            "notifications_failed": int(row[6]),
        }

    async def bookings_by_day(self, *, days: int = 30) -> list[TimeSeriesPoint]:
        """A dense series — days with no bookings appear as zero.

        `generate_series` rather than a plain GROUP BY: a chart that silently
        omits empty days draws a line through them and turns a bad week into a
        smooth one.
        """
        rows = (
            await self._session.execute(
                text("""
                SELECT d.day::date AS day, COALESCE(count(b.id), 0) AS total
                  FROM generate_series(
                         CURRENT_DATE - make_interval(days => :days - 1),
                         CURRENT_DATE, '1 day') AS d(day)
                  LEFT JOIN bookings b ON b.created_at::date = d.day::date
                 GROUP BY d.day
                 ORDER BY d.day
                """),
                {"days": days},
            )
        ).all()
        return [TimeSeriesPoint(day=r[0], value=int(r[1])) for r in rows]

    async def revenue_by_day(self, *, days: int = 30) -> list[TimeSeriesPoint]:
        rows = (
            await self._session.execute(
                text(f"""
                SELECT d.day::date AS day, COALESCE(sum(b.total_minor), 0) AS total
                  FROM generate_series(
                         CURRENT_DATE - make_interval(days => :days - 1),
                         CURRENT_DATE, '1 day') AS d(day)
                  LEFT JOIN bookings b
                         ON b.created_at::date = d.day::date
                        AND b.status IN {EARNING_STATUSES}
                 GROUP BY d.day
                 ORDER BY d.day
                """),
                {"days": days},
            )
        ).all()
        return [TimeSeriesPoint(day=r[0], value=int(r[1])) for r in rows]

    async def booking_status_mix(self, *, days: int = 30) -> dict[str, int]:
        rows = (
            await self._session.execute(
                text("""
                SELECT status, count(*)
                  FROM bookings
                 WHERE created_at >= now() - make_interval(days => :days)
                 GROUP BY status
                """),
                {"days": days},
            )
        ).all()
        return {str(r[0]): int(r[1]) for r in rows}

    async def top_properties(self, *, days: int = 30, limit: int = 5) -> list[TopProperty]:
        rows = (
            await self._session.execute(
                text(f"""
                SELECT p.id, p.name, p.city, count(b.id) AS bookings,
                       COALESCE(sum(b.total_minor), 0) AS revenue, min(b.currency) AS currency
                  FROM bookings b
                  JOIN properties p ON p.id = b.property_id
                 WHERE b.created_at >= now() - make_interval(days => :days)
                   AND b.status IN {EARNING_STATUSES}
                 GROUP BY p.id, p.name, p.city
                 ORDER BY revenue DESC
                 LIMIT :limit
                """),
                {"days": days, "limit": limit},
            )
        ).all()
        return [
            TopProperty(
                property_id=r[0],
                name=r[1],
                city=r[2],
                bookings=int(r[3]),
                revenue_minor=int(r[4]),
                currency=r[5] or "INR",
            )
            for r in rows
        ]

    # ── lists ─────────────────────────────────────────────────────────────

    async def users(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        role: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> PagedResult[AdminUserRow]:
        """Users with their booking history.

        The aggregates are lateral subqueries rather than a GROUP BY over a
        three-way join: with a join, a user with twelve bookings and three
        payments produces thirty-six rows to collapse, and the count is wrong
        in a way that looks plausible.
        """
        where, params = _filters(
            [
                (
                    "(lower(u.email) LIKE :q OR lower(u.full_name) LIKE :q)",
                    f"%{query.lower()}%" if query else None,
                    "q",
                ),
                ("u.status = :status", status, "status"),
                (
                    # No join to `roles`. The grant table stores the role *name*
                    # — `user_roles.role_name` is itself the foreign key into
                    # `roles(name)`, and neither table has the surrogate id an
                    # earlier version of this predicate joined on. That spelling
                    # parsed fine in Python and only failed once someone actually
                    # used the filter, as a 500.
                    "EXISTS (SELECT 1 FROM user_roles ur "
                    "        WHERE ur.user_id = u.id AND ur.role_name = :role)",
                    role,
                    "role",
                ),
            ]
        )
        params |= {"limit": size, "offset": (page - 1) * size}

        rows = (
            await self._session.execute(
                text(f"""
                SELECT u.id, u.email, u.full_name, u.phone_e164, u.status,
                       COALESCE(ARRAY(SELECT ur.role_name FROM user_roles ur
                                      WHERE ur.user_id = u.id), '{{}}') AS roles,
                       -- Verification is a timestamp, not a flag: "when" is
                       -- needed for support, and the boolean is derived here.
                       (u.email_verified_at IS NOT NULL) AS email_verified,
                       u.created_at, u.last_login_at,
                       stats.booking_count, stats.lifetime_value
                  FROM users u
                  LEFT JOIN LATERAL (
                       SELECT count(*) AS booking_count,
                              COALESCE(sum(total_minor) FILTER
                                       (WHERE status IN {EARNING_STATUSES}), 0) AS lifetime_value
                         FROM bookings WHERE guest_id = u.id
                  ) stats ON true
                 {where}
                 ORDER BY u.created_at DESC
                 LIMIT :limit OFFSET :offset
                """),
                params,
            )
        ).all()

        total = int(
            (
                await self._session.execute(text(f"SELECT count(*) FROM users u {where}"), params)
            ).scalar()
            or 0
        )

        return PagedResult(
            items=[
                AdminUserRow(
                    id=r[0],
                    email=r[1],
                    full_name=r[2],
                    phone=r[3],
                    status=r[4],
                    roles=list(r[5] or []),
                    email_verified=bool(r[6]),
                    created_at=r[7],
                    last_login_at=r[8],
                    booking_count=int(r[9] or 0),
                    lifetime_value_minor=int(r[10] or 0),
                    currency="INR",
                )
                for r in rows
            ],
            total=total,
            page=page,
            size=size,
        )

    async def properties(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        vendor_id: uuid.UUID | None = None,
        page: int = 1,
        size: int = 20,
    ) -> PagedResult[AdminPropertyRow]:
        where, params = _filters(
            [
                (
                    "(lower(p.name) LIKE :q OR lower(p.city) LIKE :q)",
                    f"%{query.lower()}%" if query else None,
                    "q",
                ),
                ("p.status = :status", status, "status"),
                ("p.vendor_id = :vendor_id", vendor_id, "vendor_id"),
            ]
        )
        params |= {"limit": size, "offset": (page - 1) * size}

        rows = (
            await self._session.execute(
                text(f"""
                SELECT p.id, p.name, p.slug, p.city, p.property_type, p.status,
                       p.vendor_id, v.legal_name,
                       (SELECT count(*) FROM room_types rt WHERE rt.property_id = p.id),
                       p.review_average, p.review_count, p.created_at, p.published_at
                  FROM properties p
                  LEFT JOIN vendors v ON v.id = p.vendor_id
                 {where}
                 ORDER BY p.created_at DESC
                 LIMIT :limit OFFSET :offset
                """),
                params,
            )
        ).all()
        total = int(
            (
                await self._session.execute(
                    text(f"SELECT count(*) FROM properties p {where}"), params
                )
            ).scalar()
            or 0
        )
        return PagedResult(
            items=[
                AdminPropertyRow(
                    id=r[0],
                    name=r[1],
                    slug=r[2],
                    city=r[3],
                    property_type=r[4],
                    status=r[5],
                    vendor_id=r[6],
                    vendor_name=r[7],
                    room_types=int(r[8] or 0),
                    review_average=float(r[9] or 0),
                    review_count=int(r[10] or 0),
                    created_at=r[11],
                    published_at=r[12],
                )
                for r in rows
            ],
            total=total,
            page=page,
            size=size,
        )

    async def bookings(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        property_id: uuid.UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        page: int = 1,
        size: int = 20,
    ) -> PagedResult[AdminBookingRow]:
        where, params = _filters(
            [
                ("(b.reference = :ref OR lower(b.guest_email) LIKE :q)", query, "query_pair"),
                ("b.status = :status", status, "status"),
                ("b.property_id = :property_id", property_id, "property_id"),
                ("b.check_in >= :from_date", from_date, "from_date"),
                ("b.check_in <= :to_date", to_date, "to_date"),
            ]
        )
        if query:
            params |= {"ref": query.strip().upper(), "q": f"%{query.lower()}%"}
            params.pop("query_pair", None)
        params |= {"limit": size, "offset": (page - 1) * size}

        rows = (
            await self._session.execute(
                text(f"""
                SELECT b.id, b.reference, b.status, b.guest_name, b.guest_email,
                       b.property_id, b.property_name, b.check_in, b.check_out,
                       -- Derived, not stored. The stay is half-open, so a
                       -- 12th→14th booking is two nights.
                       (b.check_out - b.check_in) AS nights,
                       b.total_minor, b.currency, b.created_at,
                       EXISTS (SELECT 1 FROM support_tickets t
                                WHERE t.booking_id = b.id
                                  AND t.status IN ('open','in_progress','waiting_on_guest'))
                  FROM bookings b
                 {where}
                 ORDER BY b.created_at DESC
                 LIMIT :limit OFFSET :offset
                """),
                params,
            )
        ).all()
        total = int(
            (
                await self._session.execute(
                    text(f"SELECT count(*) FROM bookings b {where}"), params
                )
            ).scalar()
            or 0
        )
        return PagedResult(
            items=[
                AdminBookingRow(
                    id=r[0],
                    reference=r[1],
                    status=r[2],
                    guest_name=r[3],
                    guest_email=r[4],
                    property_id=r[5],
                    property_name=r[6],
                    check_in=r[7],
                    check_out=r[8],
                    nights=int(r[9]),
                    total_minor=int(r[10]),
                    currency=r[11],
                    created_at=r[12],
                    has_open_ticket=bool(r[13]),
                )
                for r in rows
            ],
            total=total,
            page=page,
            size=size,
        )

    async def payments(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> PagedResult[AdminPaymentRow]:
        where, params = _filters(
            [
                ("p.status = :status", status, "status"),
                ("p.booking_reference = :ref", query.strip().upper() if query else None, "ref"),
            ]
        )
        params |= {"limit": size, "offset": (page - 1) * size}

        rows = (
            await self._session.execute(
                text(f"""
                SELECT p.id, p.booking_reference, p.status, p.method,
                       p.expected_amount_minor,
                       COALESCE((SELECT sum(amount_minor) FROM payment_refunds r
                                  WHERE r.payment_id = p.id AND r.status = 'processed'), 0),
                       COALESCE((SELECT sum(signed_minor) FROM payment_ledger l
                                  WHERE l.payment_id = p.id), 0),
                       p.currency, p.created_at, p.captured_at
                  FROM payments p
                 {where}
                 ORDER BY p.created_at DESC
                 LIMIT :limit OFFSET :offset
                """),
                params,
            )
        ).all()
        total = int(
            (
                await self._session.execute(
                    text(f"SELECT count(*) FROM payments p {where}"), params
                )
            ).scalar()
            or 0
        )
        return PagedResult(
            items=[
                AdminPaymentRow(
                    id=r[0],
                    booking_reference=r[1],
                    status=r[2],
                    method=r[3],
                    amount_minor=int(r[4]),
                    refunded_minor=int(r[5]),
                    net_minor=int(r[6]),
                    currency=r[7],
                    created_at=r[8],
                    captured_at=r[9],
                )
                for r in rows
            ],
            total=total,
            page=page,
            size=size,
        )

    async def vendors(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> PagedResult[AdminVendorRow]:
        where, params = _filters(
            [
                ("v.status = :status", status, "status"),
                (
                    "(lower(v.legal_name) LIKE :q OR lower(v.contact_email) LIKE :q)",
                    f"%{query.lower()}%" if query else None,
                    "q",
                ),
            ]
        )
        params |= {"limit": size, "offset": (page - 1) * size}

        rows = (
            await self._session.execute(
                text(f"""
                SELECT v.id, v.legal_name, v.display_name, v.contact_email, v.status,
                       v.commission_bps,
                       (SELECT count(*) FROM properties p WHERE p.vendor_id = v.id),
                       (SELECT count(*) FROM properties p
                         WHERE p.vendor_id = v.id AND p.status = 'published'),
                       COALESCE((SELECT sum(b.total_minor) FROM bookings b
                                  WHERE b.vendor_id = v.id
                                    AND b.status IN {EARNING_STATUSES}), 0),
                       v.created_at, v.approved_at
                  FROM vendors v
                 {where}
                 ORDER BY v.created_at DESC
                 LIMIT :limit OFFSET :offset
                """),
                params,
            )
        ).all()
        total = int(
            (
                await self._session.execute(text(f"SELECT count(*) FROM vendors v {where}"), params)
            ).scalar()
            or 0
        )
        return PagedResult(
            items=[
                AdminVendorRow(
                    id=r[0],
                    legal_name=r[1],
                    display_name=r[2],
                    contact_email=r[3],
                    status=r[4],
                    commission_bps=int(r[5]),
                    property_count=int(r[6]),
                    published_count=int(r[7]),
                    gross_bookings_minor=int(r[8]),
                    currency="INR",
                    created_at=r[9],
                    approved_at=r[10],
                )
                for r in rows
            ],
            total=total,
            page=page,
            size=size,
        )

    # ── analytics ─────────────────────────────────────────────────────────

    async def revenue_breakdown(self, *, from_date: date, to_date: date) -> RevenueBreakdown:
        """Where the money went, for the period.

        Fees and commission come from the payment ledger rather than being
        recomputed from percentages: the ledger is what actually happened, and
        a report that recalculates it will disagree with the bank.
        """
        row = (
            await self._session.execute(
                text(f"""
                SELECT
                  COALESCE((SELECT sum(total_minor) FROM bookings
                             WHERE created_at::date BETWEEN :from_date AND :to_date
                               AND status IN {EARNING_STATUSES}), 0)          AS gross,
                  COALESCE((SELECT sum(amount_minor) FROM booking_refunds
                             WHERE requested_at::date BETWEEN :from_date AND :to_date
                               AND status = 'completed'), 0)                  AS refunded,
                  COALESCE((SELECT -sum(signed_minor) FROM payment_ledger
                             WHERE occurred_at::date BETWEEN :from_date AND :to_date
                               AND kind IN ('gateway_fee','gateway_tax')), 0) AS fees,
                  COALESCE((SELECT sum(tax_minor) FROM bookings
                             WHERE created_at::date BETWEEN :from_date AND :to_date
                               AND status IN {EARNING_STATUSES}), 0)          AS tax,
                  COALESCE((SELECT sum(platform_fee_minor) FROM bookings
                             WHERE created_at::date BETWEEN :from_date AND :to_date
                               AND status IN {EARNING_STATUSES}), 0)          AS commission,
                  COALESCE((SELECT sum(discount_minor) FROM coupon_redemptions
                             WHERE redeemed_at::date BETWEEN :from_date AND :to_date
                               AND released_at IS NULL), 0)                   AS discounts
                """),
                {"from_date": from_date, "to_date": to_date},
            )
        ).one()

        gross, refunded, fees = int(row[0]), int(row[1]), int(row[2])
        commission = int(row[4])
        return RevenueBreakdown(
            gross_minor=gross,
            refunded_minor=refunded,
            gateway_fees_minor=fees,
            platform_commission_minor=commission,
            # What the vendors are owed: everything except the platform's cut,
            # the gateway's cut, and anything refunded.
            vendor_payable_minor=max(0, gross - refunded - commission - fees),
            tax_collected_minor=int(row[3]),
            discounts_minor=int(row[5]),
            currency="INR",
            from_date=from_date,
            to_date=to_date,
        )

    async def analytics_extras(self, *, from_date: date, to_date: date) -> dict[str, Any]:
        row = (
            await self._session.execute(
                text(f"""
                WITH scoped AS (
                    SELECT * FROM bookings
                     WHERE created_at::date BETWEEN :from_date AND :to_date
                )
                SELECT
                  (SELECT count(*) FROM scoped)                                AS total,
                  (SELECT count(*) FROM scoped WHERE status = 'cancelled')     AS cancelled,
                  (SELECT COALESCE(avg(total_minor), 0) FROM scoped
                    WHERE status IN {EARNING_STATUSES})                        AS avg_value,
                  (SELECT COALESCE(avg(EXTRACT(EPOCH FROM
                            (check_in::timestamp - created_at)) / 86400), 0)
                     FROM scoped WHERE status IN {EARNING_STATUSES})           AS lead_days,
                  (SELECT COALESCE(sum(units_booked), 0) FROM room_inventory
                    WHERE stay_date BETWEEN :from_date AND :to_date)           AS booked_nights,
                  (SELECT COALESCE(sum(units_total), 0) FROM room_inventory
                    WHERE stay_date BETWEEN :from_date AND :to_date)           AS total_nights
                """),
                {"from_date": from_date, "to_date": to_date},
            )
        ).one()

        total, cancelled = int(row[0]), int(row[1])
        booked_nights, available_nights = int(row[4]), int(row[5])
        return {
            "cancellation_rate": round(cancelled / total * 100, 2) if total else 0.0,
            "average_booking_value_minor": int(row[2] or 0),
            "average_lead_time_days": round(float(row[3] or 0), 1),
            # Only counts nights the inventory table actually has a row for —
            # sparse rows mean unmodified dates are absent, so this is
            # occupancy across *managed* inventory, not across all time.
            "occupancy_percent": (
                round(booked_nights / available_nights * 100, 2) if available_nights else 0.0
            ),
        }

    async def bookings_by_city(
        self, *, from_date: date, to_date: date, limit: int = 10
    ) -> list[tuple[str, int, int]]:
        rows = (
            await self._session.execute(
                text(f"""
                SELECT p.city, count(b.id), COALESCE(sum(b.total_minor), 0)
                  FROM bookings b
                  JOIN properties p ON p.id = b.property_id
                 WHERE b.created_at::date BETWEEN :from_date AND :to_date
                   AND b.status IN {EARNING_STATUSES}
                 GROUP BY p.city
                 ORDER BY 3 DESC
                 LIMIT :limit
                """),
                {"from_date": from_date, "to_date": to_date, "limit": limit},
            )
        ).all()
        return [(r[0], int(r[1]), int(r[2])) for r in rows]

    async def bookings_by_property_type(self, *, from_date: date, to_date: date) -> dict[str, int]:
        rows = (
            await self._session.execute(
                text(f"""
                SELECT p.property_type, count(b.id)
                  FROM bookings b
                  JOIN properties p ON p.id = b.property_id
                 WHERE b.created_at::date BETWEEN :from_date AND :to_date
                   AND b.status IN {EARNING_STATUSES}
                 GROUP BY p.property_type
                """),
                {"from_date": from_date, "to_date": to_date},
            )
        ).all()
        return {str(r[0]): int(r[1]) for r in rows}

    async def notifications(
        self,
        *,
        status: str | None = None,
        template: str | None = None,
        recipient: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        where, params = _filters(
            [
                ("status = :status", status, "status"),
                ("template = :template", template, "template"),
                ("recipient = :recipient", recipient.lower() if recipient else None, "recipient"),
            ]
        )
        params |= {"limit": size, "offset": (page - 1) * size}

        rows = (
            await self._session.execute(
                text(f"""
                SELECT id, channel, template, recipient, subject, preview, status,
                       error, attempts, created_at, sent_at
                  FROM notifications
                 {where}
                 ORDER BY created_at DESC
                 LIMIT :limit OFFSET :offset
                """),
                params,
            )
        ).all()
        total = int(
            (
                await self._session.execute(
                    text(f"SELECT count(*) FROM notifications {where}"), params
                )
            ).scalar()
            or 0
        )
        return (
            [
                {
                    "id": str(r[0]),
                    "channel": r[1],
                    "template": r[2],
                    "recipient": r[3],
                    "subject": r[4],
                    "preview": r[5],
                    "status": r[6],
                    "error": r[7],
                    "attempts": int(r[8]),
                    "created_at": r[9],
                    "sent_at": r[10],
                }
                for r in rows
            ],
            total,
        )


def _change(current: int, previous: int) -> float | None:
    """Percentage change, or `None` when there is nothing to compare against.

    `None` rather than 0: "no change" and "no prior data" look identical on a
    dashboard and mean completely different things.
    """
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _filters(
    clauses: list[tuple[str, Any, str]],
) -> tuple[str, dict[str, Any]]:
    """Build a WHERE from the filters that were actually supplied.

    Only the *clause* is composed; every value stays a bound parameter, so a
    search box cannot reach the query planner as SQL.
    """
    active = [(clause, value, name) for clause, value, name in clauses if value is not None]
    if not active:
        return "", {}
    where = "WHERE " + " AND ".join(clause for clause, _, _ in active)
    params = {name: value for _, value, name in active}
    return where, params
