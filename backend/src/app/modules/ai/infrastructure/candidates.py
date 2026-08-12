"""Retrieval: finding properties worth ranking.

Raw SQL, and against the **read replica**, for the same reasons the admin
projections are: these queries join bookings to properties across module
boundaries, and expressing them through two repositories would be either a
boundary violation or an N+1 per candidate. Nothing here writes.

Two things every query in this file does, and both are load-bearing:

* **filters on `status = 'published' AND deleted_at IS NULL`.** A recommendation
  is a link. Recommending an unpublished, rejected or deleted listing sends a
  guest to a 404 and, worse, leaks that a property a host took down still
  exists.
* **bounds itself.** Every query has a LIMIT and every join has a predicate
  that hits an index. A recommendation is a nice-to-have on a page that must
  render; it does not get to run a sequential scan.

There is no vector index here, and no pretence of one. The signals are
co-booking, attribute overlap and geography — all of which this schema already
indexes, and all of which are explainable to the host who asks why they were
not recommended. When there is enough behavioural data to warrant embeddings,
:class:`~app.modules.ai.application.ports.CandidateSource` is the seam to
implement again; nothing above it changes.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Final

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.domain.value_objects import Candidate

#: A booking only counts as a preference once it has been paid for. A pending
#: hold is an intention, and an expired one is often a change of mind — folding
#: either into "guests who booked this also booked that" measures browsing, not
#: taste.
BOOKED: Final = "('confirmed','in_stay','completed')"

#: Only stays that actually happened inform a guest's own history. Someone who
#: cancelled a trip to Jaipur did not experience Jaipur.
STAYED: Final = "('in_stay','completed')"

#: Every query selects this, in this order, so one mapper serves all of them.
_COLUMNS: Final = """
    p.id, p.name, p.city, p.property_type, p.min_rate_minor, p.currency,
    p.review_average, p.review_count, p.amenity_codes
"""

_LIVE: Final = "p.status = 'published' AND p.deleted_at IS NULL"


def _to_candidate(row: Row[Any], *, distance_km: float | None = None, co: int = 0) -> Candidate:
    return Candidate(
        property_id=row[0],
        name=row[1],
        city=row[2],
        property_type=row[3],
        min_rate_minor=row[4],
        currency=row[5],
        review_average=float(row[6] or 0),
        review_count=int(row[7] or 0),
        amenity_codes=frozenset(row[8] or []),
        distance_km=distance_km,
        co_bookings=co,
    )


class SqlCandidateSource:
    """Implements :class:`app.modules.ai.application.ports.CandidateSource`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── content neighbours ────────────────────────────────────────────────

    async def similar_to(self, property_id: uuid.UUID, *, limit: int) -> Sequence[Candidate]:
        """Same city, comparable price, ordered by how close it is.

        The price band is ±60%, which is wide on purpose: a guest looking at a
        ₹4,000 room is plausibly interested in ₹6,500, and a narrow band turns
        "similar" into "identical" and shows six versions of the same listing.

        Distance is computed with the geography type, so it is metres on the
        ellipsoid rather than degrees — a difference that matters more the
        further from the equator you go, and India is far enough.
        """
        rows = (
            await self._session.execute(
                text(f"""
                WITH anchor AS (
                    SELECT city, location, min_rate_minor, property_type
                      FROM properties WHERE id = :pid
                )
                SELECT {_COLUMNS},
                       CASE WHEN p.location IS NOT NULL AND a.location IS NOT NULL
                            THEN ST_Distance(p.location, a.location) / 1000.0
                       END AS distance_km
                  FROM properties p, anchor a
                 WHERE {_LIVE}
                   AND p.id <> :pid
                   AND p.city = a.city
                   AND (
                        a.min_rate_minor IS NULL
                     OR p.min_rate_minor IS NULL
                     OR p.min_rate_minor BETWEEN a.min_rate_minor * 0.4
                                             AND a.min_rate_minor * 1.6
                   )
                 ORDER BY (p.property_type = a.property_type) DESC,
                          distance_km NULLS LAST,
                          p.review_count DESC
                 LIMIT :limit
                """),
                {"pid": property_id, "limit": limit},
            )
        ).all()
        return [_to_candidate(r, distance_km=r[9]) for r in rows]

    # ── behavioural ───────────────────────────────────────────────────────

    async def also_booked(self, property_id: uuid.UUID, *, limit: int) -> Sequence[Candidate]:
        """Guests who booked the anchor, and what else they booked.

        A self-join on `bookings.guest_id`, restricted to paid stays. The
        subquery of guests is bounded before the join: an extremely popular
        property would otherwise pull tens of thousands of rows into the
        second half, and this query runs while a guest waits for a page.

        Deliberately *not* filtered to the same city. The strongest result this
        signal produces is the guest who books Goa in December and Manali in
        June, which no content-similarity query will ever surface.
        """
        rows = (
            await self._session.execute(
                text(f"""
                WITH guests AS (
                    SELECT DISTINCT guest_id
                      FROM bookings
                     WHERE property_id = :pid
                       AND status IN {BOOKED}
                     LIMIT 2000
                ), together AS (
                    SELECT b.property_id, count(DISTINCT b.guest_id) AS co
                      FROM bookings b
                      JOIN guests g ON g.guest_id = b.guest_id
                     WHERE b.property_id <> :pid
                       AND b.status IN {BOOKED}
                     GROUP BY b.property_id
                )
                SELECT {_COLUMNS}, t.co
                  FROM together t
                  JOIN properties p ON p.id = t.property_id
                 WHERE {_LIVE}
                 ORDER BY t.co DESC, p.review_count DESC
                 LIMIT :limit
                """),
                {"pid": property_id, "limit": limit},
            )
        ).all()
        return [_to_candidate(r, co=int(r[9])) for r in rows]

    async def from_history(self, user_id: uuid.UUID, *, limit: int) -> Sequence[Candidate]:
        """Properties resembling where this guest has actually stayed.

        Matches on city *or* property type from their last few stays, rather
        than requiring both: someone who liked two beach villas is a signal
        about villas and a signal about beaches, and demanding both together
        usually returns the two properties they already stayed in.

        Their own past stays are excluded. "You liked this, book it again" is a
        different product, and mixing it into discovery makes discovery look
        broken.
        """
        rows = (
            await self._session.execute(
                text(f"""
                WITH stays AS (
                    SELECT DISTINCT b.property_id
                      FROM bookings b
                     WHERE b.guest_id = :uid AND b.status IN {STAYED}
                     ORDER BY b.property_id
                     LIMIT 20
                ), taste AS (
                    SELECT DISTINCT p.city, p.property_type
                      FROM properties p JOIN stays s ON s.property_id = p.id
                )
                SELECT DISTINCT {_COLUMNS}
                  FROM properties p
                 WHERE {_LIVE}
                   AND p.id NOT IN (SELECT property_id FROM stays)
                   AND EXISTS (
                        SELECT 1 FROM taste t
                         WHERE t.city = p.city OR t.property_type = p.property_type
                   )
                 ORDER BY p.review_count DESC, p.review_average DESC
                 LIMIT :limit
                """),
                {"uid": user_id, "limit": limit},
            )
        ).all()
        return [_to_candidate(r) for r in rows]

    # ── cold start ────────────────────────────────────────────────────────

    async def popular_in(self, city: str, *, limit: int) -> Sequence[Candidate]:
        """Recent booking volume, not all-time.

        A 90-day window, because "popular" that includes 2019 is a measure of
        how long a listing has existed. Ordered by bookings first and rating
        second so a well-reviewed listing nobody books does not permanently
        occupy the top of a city nobody can get into.
        """
        rows = (
            await self._session.execute(
                text(f"""
                SELECT {_COLUMNS},
                       (SELECT count(*) FROM bookings b
                         WHERE b.property_id = p.id
                           AND b.status IN {BOOKED}
                           AND b.created_at > now() - interval '90 days') AS recent
                  FROM properties p
                 WHERE {_LIVE}
                   AND (:city = '' OR p.city ILIKE :city)
                 ORDER BY recent DESC, p.review_count DESC, p.review_average DESC
                 LIMIT :limit
                """),
                {"city": city, "limit": limit},
            )
        ).all()
        return [_to_candidate(r) for r in rows]

    async def in_city(self, city: str, *, limit: int) -> Sequence[Candidate]:
        """Grounding for an itinerary: what we can actually sell here."""
        rows = (
            await self._session.execute(
                text(f"""
                SELECT {_COLUMNS}
                  FROM properties p
                 WHERE {_LIVE} AND p.city ILIKE :city
                 ORDER BY p.review_count DESC, p.review_average DESC
                 LIMIT :limit
                """),
                {"city": city, "limit": limit},
            )
        ).all()
        return [_to_candidate(r) for r in rows]

    # ── used by destination suggestions ───────────────────────────────────

    async def city_of(self, property_id: uuid.UUID) -> str:
        """The anchor's city, for the fallback rail.

        Read here rather than passed in by the client: a caller-supplied city
        is a caller-supplied filter, and the one thing this endpoint must not
        do is show a guest another city's listings under "more like this".
        """
        row = (
            await self._session.execute(
                text("SELECT city FROM properties WHERE id = :pid"), {"pid": property_id}
            )
        ).first()
        return str(row[0]) if row else ""

    async def cities_with_supply(self, *, limit: int = 40) -> list[str]:
        """Cities we can actually sell a stay in.

        The candidate set for destination suggestions. Without it the model
        recommends Ladakh, which is a fine holiday and an advert for a
        competitor.
        """
        rows = (
            await self._session.execute(
                text(f"""
                SELECT p.city, count(*) AS n
                  FROM properties p
                 WHERE {_LIVE}
                 GROUP BY p.city
                HAVING count(*) > 0
                 ORDER BY n DESC
                 LIMIT :limit
                """),
                {"limit": limit},
            )
        ).all()
        return [str(r[0]) for r in rows]

    async def stay_history(self, user_id: uuid.UUID, *, limit: int = 10) -> list[dict[str, Any]]:
        """Where this guest has been, and when.

        City and month only. Not the property, not the price, not who they
        travelled with — this goes into a prompt sent to a third party, and the
        rule is that it carries the least that will do the job.
        """
        rows = (
            await self._session.execute(
                text(f"""
                SELECT p.city, to_char(b.check_in, 'Mon') AS month, b.check_in
                  FROM bookings b JOIN properties p ON p.id = b.property_id
                 WHERE b.guest_id = :uid AND b.status IN {STAYED}
                 ORDER BY b.check_in DESC
                 LIMIT :limit
                """),
                {"uid": user_id, "limit": limit},
            )
        ).all()
        return [{"city": r[0], "month": r[1]} for r in rows]
