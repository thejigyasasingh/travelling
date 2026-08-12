"""Search: one statement, no N+1, index-driven.

This is the highest-volume query in the system and the one most able to take
the database down. Everything here exists to keep it index-driven.

**One statement.** Twenty cards need a cover image, a cheapest rate, a rating
and a distance. Hydrating aggregates would be 20 properties + 20 image queries
+ 20 rate queries = 41 round trips for one page. This returns flat rows.

**Denormalised sort keys.** ``min_rate_minor``, ``max_guests`` and
``review_average`` live on ``properties``, trigger-maintained. A sort must be
satisfiable *before* the LIMIT, so computing "cheapest room" per candidate
would run over every match, not just the twenty returned.

**Availability as ``NOT EXISTS``.** The question "is anything free for all of
these nights?" is answered by looking for a night that is *not* free and
stopping at the first one. The alternative — generating a row per night and
counting — does work proportional to the whole stay for every candidate.
Because inventory is sparse, the absence of a row means available, so the
subquery only ever touches rows that represent an actual booking or block.

**Cursor pagination.** ``OFFSET 40000`` makes Postgres walk and discard 40,000
rows; at a million listings the last page of a search is a table scan. The
cursor is a ``(sort_key, id)`` tuple compared as a row value, which rides the
index and is stable while new listings arrive mid-scroll.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.types.pagination import Cursor
from app.modules.property.application.dto import (
    SearchCriteria,
    SearchResultItem,
    SearchResults,
    SearchSort,
)

logger = get_logger(__name__)

#: Above this we stop counting and report "200+". An exact count over a
#: filtered million-row set is a full index scan on every keystroke, and no
#: user has ever needed to know they matched 47,213 properties.
COUNT_CEILING: Final = 200

#: Blends rating, review volume and proximity. The `review_count` term uses a
#: log so that a 5.0 from two guests does not outrank a 4.7 from four hundred —
#: the single most common way a naive rating sort goes wrong.
_RELEVANCE_BASE: Final = """
    (p.review_average * 20)
  + (LEAST(ln(GREATEST(p.review_count, 1) + 1) * 8, 40))
  + (CASE WHEN p.instant_booking THEN 5 ELSE 0 END)
"""

#: Appended only when the search carries a location. It cannot be written as a
#: runtime `CASE WHEN :near_wkt IS NULL` guard: Postgres has to infer a type
#: for every parameter at *plan* time, and a bare NULL in a comparison gives it
#: nothing to work with — `could not determine data type of parameter $1`. The
#: term is composed in or out instead.
_RELEVANCE_PROXIMITY: Final = (
    " + GREATEST(0, 30 - (ST_Distance(p.location, ST_GeogFromText(:near_wkt)) / 1000.0))"
)

_ORDER_BY: Final[dict[SearchSort, str]] = {
    # `id` is the tiebreaker in every one of these. Without a unique final
    # sort key, rows sharing a value are skipped or repeated across pages —
    # the classic "the same hotel appears on page 2 and page 3" bug.
    SearchSort.RELEVANCE: "relevance DESC, p.id DESC",
    SearchSort.PRICE_ASC: "p.min_rate_minor ASC NULLS LAST, p.id DESC",
    SearchSort.PRICE_DESC: "p.min_rate_minor DESC NULLS LAST, p.id DESC",
    SearchSort.RATING_DESC: "p.review_average DESC, p.review_count DESC, p.id DESC",
    SearchSort.DISTANCE_ASC: "distance_m ASC NULLS LAST, p.id DESC",
    SearchSort.NEWEST: "p.published_at DESC NULLS LAST, p.id DESC",
}

#: Keyset predicates. `{expr}` is substituted with the *computed expression*
#: for the two sorts that order by a derived value.
#:
#: **A SELECT alias cannot be referenced from WHERE.** Postgres evaluates the
#: WHERE clause before the select list exists, so `WHERE (relevance, p.id) <
#: (...)` raises `column "relevance" does not exist`. The first page has no
#: cursor and never hits it; page two of the *default* sort did, on every text
#: search, and answered 500. Repeating the expression is the only correct fix —
#: wrapping the query in a subselect would defeat the index the keyset scan
#: exists to use.
_CURSOR_PREDICATE: Final[dict[SearchSort, str]] = {
    SearchSort.RELEVANCE: "({expr}, p.id) < (:c_num, :c_id)",
    SearchSort.PRICE_ASC: "(p.min_rate_minor, p.id) > (:c_num, :c_id)",
    SearchSort.PRICE_DESC: "(p.min_rate_minor, p.id) < (:c_num, :c_id)",
    SearchSort.RATING_DESC: "(p.review_average, p.id) < (:c_num, :c_id)",
    SearchSort.DISTANCE_ASC: "({expr}, p.id) > (:c_num, :c_id)",
    SearchSort.NEWEST: "(p.published_at, p.id) < (:c_ts, :c_id)",
}


@dataclass(slots=True)
class SqlSearchRepository:
    """Implements :class:`app.modules.property.application.ports.SearchRepository`.

    Takes a **read-replica** session. Search is the heaviest read in the system
    and must never contend with the booking transactions on the primary; a few
    hundred milliseconds of replication lag is invisible on a search page and
    unacceptable inside a booking.
    """

    session: AsyncSession

    async def search(self, criteria: SearchCriteria) -> SearchResults:
        params: dict[str, Any] = {}
        where = self._build_filters(criteria, params)

        near_wkt = criteria.near.to_wkt() if criteria.near else None
        params["limit"] = criteria.limit + 1  # over-fetch to detect a next page

        # Only bind :near_wkt when the SQL actually references it — an unused
        # bind is fine, but a referenced-and-null one is not (see
        # _RELEVANCE_PROXIMITY).
        if near_wkt:
            params["near_wkt"] = near_wkt

        distance_expr = (
            "ST_Distance(p.location, ST_GeogFromText(:near_wkt))"
            if near_wkt
            else "NULL::double precision"
        )
        relevance_expr = _RELEVANCE_BASE + (_RELEVANCE_PROXIMITY if near_wkt else "")

        if criteria.cursor is not None:
            where.append(
                self._cursor_predicate(
                    criteria,
                    params,
                    # The same expressions the select list computes. Passed in
                    # rather than looked up, because they depend on whether the
                    # search is geographic.
                    relevance_expr=relevance_expr,
                    distance_expr=distance_expr,
                )
            )

        sql = f"""
            SELECT
                p.id, p.slug, p.name, p.property_type, p.city, p.country_code,
                ST_Y(p.location::geometry) AS latitude,
                ST_X(p.location::geometry) AS longitude,
                {distance_expr}                       AS distance_m,
                {relevance_expr}                      AS relevance,
                p.review_average, p.review_count, p.amenity_codes,
                p.instant_booking, p.cancellation_policy, p.max_guests,
                p.min_rate_minor, p.currency, p.published_at,
                -- Correlated, but bounded to one row and index-backed. A join
                -- would multiply the property row by its image count and force
                -- a DISTINCT over the whole result set.
                (SELECT i.storage_key FROM property_images i
                  WHERE i.property_id = p.id AND i.is_cover
                    AND i.moderation_status <> 'rejected'
                  LIMIT 1)                            AS cover_key
            FROM properties p
            WHERE {" AND ".join(where)}
            ORDER BY {_ORDER_BY[criteria.sort]}
            LIMIT :limit
        """

        rows = (await self.session.execute(text(sql), params)).mappings().all()

        has_more = len(rows) > criteria.limit
        page = rows[: criteria.limit]
        items = [self._to_item(row, criteria) for row in page]

        next_cursor = None
        if has_more and page:
            next_cursor = self._encode_cursor(page[-1], criteria.sort)

        return SearchResults(
            items=items,
            next_cursor=next_cursor,
            applied_radius_m=criteria.effective_radius_m if criteria.near else None,
        )

    # ── filters ───────────────────────────────────────────────────────────

    def _build_filters(self, criteria: SearchCriteria, params: dict[str, Any]) -> list[str]:
        """Assemble the WHERE clause.

        Every value is a bound parameter. Nothing is interpolated: the only
        strings that reach the SQL text are the fixed ORDER BY and cursor
        fragments chosen from the dicts above, both keyed by an enum. There is
        no path from a user string into the statement.
        """
        where: list[str] = ["p.deleted_at IS NULL"]

        # ── visibility ────────────────────────────────────────────────────
        if criteria.include_unpublished and criteria.vendor_id is not None:
            where.append("p.vendor_id = :vendor_id")
            params["vendor_id"] = criteria.vendor_id
        else:
            where.append("p.status = 'published'")
            if criteria.vendor_id is not None:
                where.append("p.vendor_id = :vendor_id")
                params["vendor_id"] = criteria.vendor_id

        # ── location ──────────────────────────────────────────────────────
        if criteria.bounds is not None:
            # A map viewport takes precedence over a radius: a user who panned
            # the map is asking about what is on screen.
            sw, ne = criteria.bounds
            where.append(
                "p.location && ST_MakeEnvelope(:west, :south, :east, :north, 4326)::geography"
            )
            params |= {
                "west": sw.longitude,
                "south": sw.latitude,
                "east": ne.longitude,
                "north": ne.latitude,
            }
        elif criteria.near is not None:
            # ST_DWithin, not ST_Distance < x. Only DWithin can use the GIST
            # index; the comparison form computes a distance for every row.
            where.append("ST_DWithin(p.location, ST_GeogFromText(:near_wkt), :radius_m)")
            params["radius_m"] = criteria.effective_radius_m
        elif criteria.city_id is not None:
            where.append("p.city_id = :city_id")
            params["city_id"] = criteria.city_id

        # ── text ──────────────────────────────────────────────────────────
        if criteria.query:
            # Trigram similarity, not LIKE '%x%'. LIKE with a leading wildcard
            # cannot use any index; `%` rides the GIN trigram index and
            # tolerates the typos real users make.
            #
            # A SINGLE `%`. It is tempting to double it as an escape, but these
            # statements run through asyncpg, whose paramstyle is numeric
            # ($1, $2) — `%` carries no special meaning and `%%` is simply not
            # an operator. (Doubling would be required only under a pyformat
            # driver such as psycopg, which is used for migrations, not here.)
            where.append("(p.name % :q OR p.city ILIKE :q_prefix OR p.landmark % :q)")
            params["q"] = criteria.query
            params["q_prefix"] = f"{criteria.query}%"

        # ── attributes ────────────────────────────────────────────────────
        if criteria.property_types:
            where.append("p.property_type = ANY(:types)")
            params["types"] = [t.value for t in criteria.property_types]

        if criteria.amenity_codes:
            # @> is containment: "has ALL of these". A guest who ticked pool
            # AND pet-friendly wants both.
            where.append("p.amenity_codes @> :amenities")
            params["amenities"] = sorted(criteria.amenity_codes)

        if criteria.cancellation_policies:
            where.append("p.cancellation_policy = ANY(:policies)")
            params["policies"] = [p.value for p in criteria.cancellation_policies]

        if criteria.instant_booking_only:
            where.append("p.instant_booking")

        if criteria.min_rating is not None:
            where.append("p.review_average >= :min_rating")
            params["min_rating"] = criteria.min_rating

        if criteria.min_price_minor is not None:
            where.append("p.min_rate_minor >= :min_price")
            params["min_price"] = criteria.min_price_minor
        if criteria.max_price_minor is not None:
            where.append("p.min_rate_minor <= :max_price")
            params["max_price"] = criteria.max_price_minor

        # ── capacity ──────────────────────────────────────────────────────
        if criteria.occupancy.billable_guests > 1:
            # Against the largest single room type, not the sum across them: a
            # guest searching for six has not agreed to take three rooms.
            where.append("p.max_guests >= :guests")
            params["guests"] = criteria.occupancy.billable_guests

        # ── availability ──────────────────────────────────────────────────
        if criteria.stay is not None:
            where.append(self._availability_clause())
            params |= {
                "check_in": criteria.stay.start,
                "check_out": criteria.stay.end,
                "nights": criteria.stay.night_count,
                "rooms": criteria.rooms,
                "guests_for_room": criteria.occupancy.billable_guests,
            }

        return where

    @staticmethod
    def _availability_clause() -> str:
        """ "At least one room type is free for every night of the stay."

        Read the inner ``NOT EXISTS`` first: it looks for a night that
        *blocks* the stay and stops at the first one found. Because inventory
        is sparse, a night with no row is available by definition — so this
        only ever touches rows representing a real booking or block, which is a
        tiny fraction of the calendar.

        ``min_nights`` is checked here too: a property with a 3-night minimum
        must not appear in a 1-night search, or every result is a dead end.
        """
        return """
        EXISTS (
            SELECT 1
            FROM room_types rt
            WHERE rt.property_id = p.id
              AND rt.deleted_at IS NULL
              AND rt.max_adults + rt.max_children >= :guests_for_room
              AND rt.min_nights <= :nights
              AND rt.max_nights >= :nights
              AND rt.total_units >= :rooms
              AND NOT EXISTS (
                  SELECT 1
                  FROM room_inventory ri
                  WHERE ri.room_type_id = rt.id
                    AND ri.stay_date >= :check_in
                    AND ri.stay_date <  :check_out
                    AND (ri.is_blocked
                         OR ri.units_total - ri.units_booked < :rooms)
              )
        )
        """

    # ── cursor ────────────────────────────────────────────────────────────

    @staticmethod
    def _cursor_predicate(
        criteria: SearchCriteria,
        params: dict[str, Any],
        *,
        relevance_expr: str,
        distance_expr: str,
    ) -> str:
        """The keyset predicate for this page.

        `relevance` and `distance_m` are select-list aliases and are not
        visible to WHERE, so their expressions are substituted in full. Every
        other sort orders by a real column and needs no substitution.
        """
        assert criteria.cursor is not None
        values = criteria.cursor.values
        if len(values) != 2:
            from app.core.types.pagination import InvalidCursorError

            raise InvalidCursorError("Cursor does not match this sort order")

        sort_value, row_id = values
        try:
            params["c_id"] = uuid.UUID(str(row_id))
        except ValueError as exc:
            # A forged or truncated cursor. A 400 the client can act on rather
            # than a 500 that pages someone.
            from app.core.types.pagination import InvalidCursorError

            raise InvalidCursorError("Cursor is not valid for this search") from exc

        if criteria.sort is SearchSort.NEWEST:
            params["c_ts"] = sort_value
        else:
            params["c_num"] = sort_value

        template = _CURSOR_PREDICATE[criteria.sort]
        if criteria.sort is SearchSort.RELEVANCE:
            return template.format(expr=relevance_expr)
        if criteria.sort is SearchSort.DISTANCE_ASC:
            return template.format(expr=distance_expr)
        return template

    @staticmethod
    def _encode_cursor(row: Any, sort: SearchSort) -> str:
        key = {
            SearchSort.RELEVANCE: row["relevance"],
            SearchSort.PRICE_ASC: row["min_rate_minor"],
            SearchSort.PRICE_DESC: row["min_rate_minor"],
            SearchSort.RATING_DESC: float(row["review_average"]),
            SearchSort.DISTANCE_ASC: row["distance_m"],
            SearchSort.NEWEST: row["published_at"].isoformat() if row["published_at"] else None,
        }[sort]
        return Cursor((key, str(row["id"]))).encode()

    # ── projection ────────────────────────────────────────────────────────

    @staticmethod
    def _to_item(row: Any, criteria: SearchCriteria) -> SearchResultItem:
        lat, lng = row["latitude"], row["longitude"]
        if lat is not None and lng is not None:
            # Coarsened before it leaves the server. A precise pin on a search
            # card locates an occupied private home, and lets a competitor
            # scrape a vendor's whole portfolio.
            lat, lng = round(lat, 2), round(lng, 2)

        return SearchResultItem(
            id=row["id"],
            slug=row["slug"],
            name=row["name"],
            property_type=row["property_type"],
            city=row["city"],
            country_code=row["country_code"],
            latitude=lat,
            longitude=lng,
            distance_m=row["distance_m"],
            cover_image_key=row["cover_key"],
            review_average=float(row["review_average"]),
            review_count=row["review_count"],
            amenity_codes=list(row["amenity_codes"] or []),
            instant_booking=row["instant_booking"],
            cancellation_policy=row["cancellation_policy"],
            max_occupancy=row["max_guests"],
            from_price_minor=row["min_rate_minor"],
            total_price_minor=None,  # filled by the quote step when dates are given
            currency=row["currency"],
            is_available=criteria.stay is not None,
        )

    # ── count and suggest ─────────────────────────────────────────────────

    async def count_estimate(self, criteria: SearchCriteria) -> int:
        """Counts up to :data:`COUNT_CEILING` and stops.

        The LIMIT inside the subquery is what makes this cheap: Postgres stops
        as soon as it has 200 rows instead of scanning the whole match set to
        produce a number the UI renders as "200+" anyway.
        """
        params: dict[str, Any] = {}
        if criteria.near is not None:
            params["near_wkt"] = criteria.near.to_wkt()
        where = self._build_filters(criteria, params)
        params["ceiling"] = COUNT_CEILING

        sql = f"""
            SELECT count(*) FROM (
                SELECT 1 FROM properties p
                WHERE {" AND ".join(where)}
                LIMIT :ceiling
            ) capped
        """
        return int((await self.session.execute(text(sql), params)).scalar() or 0)

    async def suggest(self, prefix: str, *, limit: int = 8) -> list[dict[str, Any]]:
        """Type-ahead over cities and property names.

        Cities rank above properties: a guest typing "goa" almost always means
        the destination, and offering one hotel called "Goa Beach Resort" first
        is a worse answer than offering Goa.
        """
        sql = """
            (SELECT 'city' AS kind, c.id::text AS id, c.name AS label,
                    c.state AS sublabel, c.slug, c.property_count AS weight
               FROM cities c
              WHERE c.is_active AND (c.name ILIKE :prefix OR c.name % :raw)
              ORDER BY c.property_count DESC
              LIMIT :limit)
            UNION ALL
            (SELECT 'property', p.id::text, p.name, p.city, p.slug, p.review_count
               FROM properties p
              WHERE p.status = 'published' AND p.deleted_at IS NULL
                AND (p.name ILIKE :prefix OR p.name % :raw)
              ORDER BY p.review_count DESC
              LIMIT :limit)
        """
        rows = (
            (
                await self.session.execute(
                    text(sql), {"prefix": f"{prefix}%", "raw": prefix, "limit": limit}
                )
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows][: limit * 2]
