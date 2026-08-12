"""The rating aggregate, against a real Postgres.

This is deliberately an *integration* test and could not be anything else: the
behaviour under test is Postgres's, not the application's. A fake repository
would return whatever Python arithmetic says and pass while production 409s.

The property rating is a running aggregate rather than a `SELECT avg(...)`
because the alternative re-reads every review of a property on every write, and
a well-reviewed listing would get slower the more successful it became. Running
totals buy that back and cost a correctness burden: the increments have to be
right in every direction, because nothing recomputes them afterwards.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _seed_property(session) -> uuid.UUID:  # type: ignore[no-untyped-def]
    """A vendor and a property, the two foreign keys the summary needs.

    Pending rather than approved: an approved vendor must carry a PAN
    (``ck_vendors_approved_needs_evidence``), and this test has no business
    knowing that. Nothing here reads vendor status.
    """
    owner_id, vendor_id, property_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await session.execute(
        # A password hash because ``ck_users_credential_present`` requires one
        # for a password identity. Not a real hash — nothing here authenticates.
        text(
            "INSERT INTO users (id, email, password_hash) VALUES (:id, :email, 'not-a-real-hash')"
        ),
        {"id": owner_id, "email": f"owner-{owner_id.hex[:8]}@example.com"},
    )
    await session.execute(
        text(
            "INSERT INTO vendors (id, owner_user_id, legal_name, display_name, "
            "contact_email, contact_phone, status, commission_bps) "
            "VALUES (:id, :owner, 'Test Stays LLP', 'Test Stays', "
            "'ops@example.com', '+919000000000', 'pending', 1200)"
        ),
        {"id": vendor_id, "owner": owner_id},
    )
    await session.execute(
        text(
            "INSERT INTO properties (id, vendor_id, name, slug, property_type, status, "
            "currency, line1, city, state, country_code, postal_code, cancellation_policy, "
            "max_guests) "
            "VALUES (:id, :vendor, 'Aggregate Test House', :slug, 'villa', 'published', "
            "'INR', '1 Test Lane', 'Panaji', 'Goa', 'IN', '403001', 'moderate', 4)"
        ),
        {"id": property_id, "vendor": vendor_id, "slug": f"agg-{property_id.hex[:8]}"},
    )
    return property_id


async def _apply(session, property_id: uuid.UUID, rating: int, delta: int):  # type: ignore[no-untyped-def]
    from app.modules.review.infrastructure.repositories import SqlReviewRepository

    return await SqlReviewRepository(session).apply_to_rating(
        property_id=property_id, rating=rating, delta=delta
    )


async def test_a_first_review_creates_the_summary(db_session) -> None:  # type: ignore[no-untyped-def]
    property_id = await _seed_property(db_session)
    count, average = await _apply(db_session, property_id, rating=4, delta=1)

    assert (count, average) == (1, 4.0)


async def test_a_rating_can_go_down(db_session) -> None:  # type: ignore[no-untyped-def]
    """The regression this file was written for.

    Postgres evaluates CHECK constraints against the row *proposed* for
    insertion, before it arbitrates ``ON CONFLICT``. So an upsert whose VALUES
    clause carried a bare ``-1`` raised ``ck_rating_summaries_count_non_negative``
    from a branch that is never taken — and every rating decrease, every
    removal, and every moderation reversal returned 409 on any property that
    already had a review. The clamp lives in the VALUES clause for this reason;
    the one in ``DO UPDATE`` cannot save it.
    """
    property_id = await _seed_property(db_session)
    await _apply(db_session, property_id, rating=5, delta=1)
    await _apply(db_session, property_id, rating=1, delta=1)

    count, average = await _apply(db_session, property_id, rating=1, delta=-1)

    assert (count, average) == (1, 5.0), "removing the 1★ must leave the 5★ alone"


async def test_an_edit_moves_a_review_between_buckets(db_session) -> None:  # type: ignore[no-untyped-def]
    """An edit is a removal and an insertion, and the star histogram has to
    follow — a distribution that disagrees with the average is worse than no
    distribution, because a reader can see the contradiction."""
    property_id = await _seed_property(db_session)
    await _apply(db_session, property_id, rating=2, delta=1)
    await _apply(db_session, property_id, rating=2, delta=-1)
    count, average = await _apply(db_session, property_id, rating=4, delta=1)

    row = (
        await db_session.execute(
            text(
                "SELECT review_count, rating_total, count_2, count_4 "
                "  FROM review_rating_summaries WHERE property_id = :p"
            ),
            {"p": property_id},
        )
    ).one()

    assert (count, average) == (1, 4.0)
    assert tuple(row) == (1, 4, 0, 1)


async def test_removing_the_last_review_returns_to_zero(db_session) -> None:  # type: ignore[no-untyped-def]
    """A property back to no reviews must read as *unrated*, not as 0.0 stars.

    Nought out of five is the worst score on the platform; a new listing
    displaying it would be unsellable through no fault of its own.
    """
    property_id = await _seed_property(db_session)
    await _apply(db_session, property_id, rating=3, delta=1)
    count, average = await _apply(db_session, property_id, rating=3, delta=-1)

    assert (count, average) == (0, 0.0)


async def test_the_floor_holds_against_a_double_removal(db_session) -> None:  # type: ignore[no-untyped-def]
    """At-least-once delivery means a removal can be applied twice.

    Without the floor the count goes negative, and every average computed from
    it afterwards is nonsense that no later write repairs.
    """
    property_id = await _seed_property(db_session)
    await _apply(db_session, property_id, rating=5, delta=1)
    await _apply(db_session, property_id, rating=5, delta=-1)
    count, average = await _apply(db_session, property_id, rating=5, delta=-1)

    assert count == 0
    assert average == 0.0


async def test_totals_survive_a_mixed_sequence(db_session) -> None:  # type: ignore[no-untyped-def]
    """Five writes, two edits and a removal — the shape of a real listing's
    first month. The average has to agree with the histogram at the end."""
    property_id = await _seed_property(db_session)
    for rating in (5, 4, 3, 5, 1):
        await _apply(db_session, property_id, rating=rating, delta=1)

    # the 1★ author edits up to 4★
    await _apply(db_session, property_id, rating=1, delta=-1)
    await _apply(db_session, property_id, rating=4, delta=1)
    # staff remove the 3★
    count, average = await _apply(db_session, property_id, rating=3, delta=-1)

    assert count == 4
    assert average == 4.5  # (5 + 4 + 5 + 4) / 4

    row = (
        await db_session.execute(
            text(
                "SELECT count_1, count_3, count_4, count_5, rating_total "
                "  FROM review_rating_summaries WHERE property_id = :p"
            ),
            {"p": property_id},
        )
    ).one()
    assert tuple(row) == (0, 0, 2, 2, 18)
