"""The Property aggregate: lifecycle, room rules, images, publication gates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.types.money import Money
from app.modules.property.domain import errors
from app.modules.property.domain.entities import (
    MIN_IMAGES_TO_PUBLISH,
    Property,
    PropertyImage,
    RoomType,
)
from app.modules.property.domain.pricing import RateConfig
from app.modules.property.domain.value_objects import (
    Address,
    GeoPoint,
    Occupancy,
    PropertyStatus,
    PropertyType,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 6, 15, tzinfo=UTC)
VENDOR = uuid.uuid4()
GOA = GeoPoint(15.5736, 73.7407)


def address(**kw: object) -> Address:
    defaults: dict[str, object] = {
        "line1": "Plot 12, Anjuna Beach Road",
        "city": "Anjuna",
        "state": "Goa",
        "country_code": "IN",
        "postal_code": "403509",
    }
    return Address(**{**defaults, **kw})  # type: ignore[arg-type]


def room(name: str = "Deluxe", units: int = 3, rate_minor: int = 500_000) -> RoomType:
    return RoomType(
        name=name,
        rate=RateConfig(base_rate=Money(rate_minor, "INR")),
        max_occupancy=Occupancy(adults=2),
        total_units=units,
    )


def draft(property_type: PropertyType = PropertyType.HOTEL) -> Property:
    prop = Property.draft(
        vendor_id=VENDOR,
        name="Sea Breeze Resort",
        property_type=property_type,
        address=address(),
        location=GOA,
        description="x" * 200,
    )
    prop.pull_events()
    return prop


def publishable(property_type: PropertyType = PropertyType.HOTEL) -> Property:
    prop = draft(property_type)
    prop.add_room_type(room())
    prop.add_images([PropertyImage(storage_key=f"k{i}") for i in range(MIN_IMAGES_TO_PUBLISH)])
    prop.update_details(amenity_codes=frozenset({"wifi", "pool"}))
    prop.pull_events()
    return prop


class TestCreation:
    def test_starts_as_a_draft_with_a_slug(self) -> None:
        prop = draft()
        assert prop.status is PropertyStatus.DRAFT
        assert prop.slug == "sea-breeze-resort"

    def test_records_a_created_event(self) -> None:
        prop = Property.draft(
            vendor_id=VENDOR,
            name="Test",
            property_type=PropertyType.VILLA,
            address=address(),
        )
        assert [e.event_type for e in prop.pull_events()] == ["property.created"]

    def test_a_draft_needs_almost_nothing(self) -> None:
        # Demanding photos and coordinates on the first screen is where vendor
        # onboarding dies.
        Property.draft(
            vendor_id=VENDOR,
            name="Bare",
            property_type=PropertyType.HOMESTAY,
            address=Address(line1="A", city="B", country_code="IN"),
        )


class TestVendorScoping:
    def test_another_vendor_cannot_touch_it(self) -> None:
        # Raises VendorScopeError, which the interface maps to 404 — a 403
        # would confirm the id exists and let a competitor enumerate inventory.
        with pytest.raises(errors.VendorScopeError):
            draft().assert_owned_by(uuid.uuid4())

    def test_an_anonymous_caller_cannot_touch_it(self) -> None:
        with pytest.raises(errors.VendorScopeError):
            draft().assert_owned_by(None)

    def test_the_owner_may(self) -> None:
        draft().assert_owned_by(VENDOR)


class TestRoomTypes:
    def test_a_villa_may_have_only_one_room_type(self) -> None:
        """A villa is one bookable unit by definition; a second room type would
        make "how many are available?" ambiguous for the whole class."""
        prop = draft(PropertyType.VILLA)
        prop.add_room_type(room("Whole villa"))
        with pytest.raises(errors.WholeUnitRoomLimitError):
            prop.add_room_type(room("Annexe"))

    def test_a_hotel_may_have_many(self) -> None:
        prop = draft(PropertyType.HOTEL)
        prop.add_room_type(room("Deluxe"))
        prop.add_room_type(room("Suite"))
        assert len(prop.room_types) == 2

    def test_duplicate_names_are_refused_case_insensitively(self) -> None:
        # Two "Deluxe Room" entries make the booking screen a coin flip.
        prop = draft()
        prop.add_room_type(room("Deluxe Room"))
        with pytest.raises(errors.DuplicateRoomTypeError):
            prop.add_room_type(room("deluxe room"))

    def test_a_mismatched_currency_is_refused(self) -> None:
        prop = draft()
        mismatched = RoomType(
            name="USD room",
            rate=RateConfig(base_rate=Money(100_00, "USD")),
            max_occupancy=Occupancy(adults=2),
        )
        with pytest.raises(ValueError, match="currency"):
            prop.add_room_type(mismatched)

    def test_a_published_listing_keeps_its_last_room(self) -> None:
        # Otherwise it renders as a live page nobody can book.
        prop = publishable()
        prop.submit_for_review()
        prop.approve(now=NOW, by=None)
        with pytest.raises(errors.LastRoomTypeError):
            prop.remove_room_type(prop.room_types[0].id)

    def test_cheapest_rate_across_room_types(self) -> None:
        prop = draft()
        prop.add_room_type(room("Standard", rate_minor=400_000))
        prop.add_room_type(room("Suite", rate_minor=900_000))
        assert prop.cheapest_rate == Money(400_000, "INR")

    def test_max_occupancy_is_per_room_not_summed(self) -> None:
        """A guest searching for six has not agreed to take three separate
        rooms; offering it produces a booking that gets cancelled."""
        prop = draft()
        prop.add_room_type(room("A"))  # sleeps 2
        prop.add_room_type(room("B"))  # sleeps 2
        assert prop.max_occupancy == 2


class TestImages:
    def test_the_first_image_becomes_the_cover(self) -> None:
        # A vendor who never sets one explicitly still gets a listing that
        # renders instead of a grey box.
        prop = draft()
        prop.add_images([PropertyImage(storage_key="a"), PropertyImage(storage_key="b")])
        assert prop.cover_image is not None
        assert prop.images[0].is_cover

    def test_positions_are_assigned_in_order(self) -> None:
        prop = draft()
        prop.add_images([PropertyImage(storage_key=f"k{i}") for i in range(3)])
        assert [i.position for i in prop.images] == [0, 1, 2]

    def test_removing_the_cover_is_refused_while_others_remain(self) -> None:
        prop = draft()
        prop.add_images([PropertyImage(storage_key="a"), PropertyImage(storage_key="b")])
        with pytest.raises(errors.CoverImageRequiredError):
            prop.remove_image(prop.cover_image.id)  # type: ignore[union-attr]

    def test_the_last_image_may_be_removed(self) -> None:
        prop = draft()
        prop.add_images([PropertyImage(storage_key="only")])
        prop.remove_image(prop.images[0].id)
        assert prop.images == []

    def test_setting_a_new_cover_clears_the_old_one(self) -> None:
        prop = draft()
        prop.add_images([PropertyImage(storage_key="a"), PropertyImage(storage_key="b")])
        prop.set_cover_image(prop.images[1].id)
        assert [i.is_cover for i in prop.images] == [False, True]

    def test_reordering_keeps_unmentioned_images(self) -> None:
        # A client working from a stale list must not silently drop images.
        prop = draft()
        prop.add_images([PropertyImage(storage_key=f"k{i}") for i in range(4)])
        prop.reorder_images([prop.images[3].id, prop.images[0].id])
        assert len(prop.images) == 4

    def test_removal_records_the_storage_key(self) -> None:
        # The S3 object is deleted by the consumer, which needs the key.
        prop = draft()
        prop.add_images([PropertyImage(storage_key="a"), PropertyImage(storage_key="b")])
        prop.pull_events()
        prop.remove_image(prop.images[1].id)
        event = prop.pull_events()[0]
        assert event.to_payload()["storage_key"] == "b"


class TestPublication:
    def test_a_bare_draft_lists_everything_missing(self) -> None:
        """All at once — a vendor fixing one item, resubmitting, and being told
        about the next is how listings get abandoned half-finished."""
        prop = Property.draft(
            vendor_id=VENDOR,
            name="Bare",
            property_type=PropertyType.HOMESTAY,
            address=Address(line1="A", city="B", country_code="IN"),
        )
        missing = prop.missing_for_publication()
        assert "map_location" in missing
        assert "at_least_one_room_type" in missing
        assert "cover_image" in missing
        assert len(missing) > 4

    def test_submitting_an_incomplete_listing_raises_with_the_list(self) -> None:
        with pytest.raises(errors.PropertyNotPublishableError) as exc:
            draft().submit_for_review()
        assert exc.value.details["count"] > 0

    def test_a_complete_listing_submits(self) -> None:
        prop = publishable()
        assert prop.missing_for_publication() == []
        prop.submit_for_review()
        assert prop.status is PropertyStatus.PENDING_REVIEW

    def test_approval_re_checks_completeness(self) -> None:
        """A listing stays editable while it sits in the review queue, so what
        passed at submission may no longer hold."""
        prop = publishable()
        prop.submit_for_review()
        prop.images.clear()  # vendor deleted the photos while it queued
        with pytest.raises(errors.PropertyNotPublishableError):
            prop.approve(now=NOW, by=None)

    def test_approval_publishes_and_stamps_the_time(self) -> None:
        prop = publishable()
        prop.submit_for_review()
        prop.approve(now=NOW, by=uuid.uuid4())
        assert prop.status is PropertyStatus.PUBLISHED
        assert prop.published_at == NOW

    def test_rejection_records_the_reason(self) -> None:
        prop = publishable()
        prop.submit_for_review()
        prop.reject(reason="Photos do not match the address", by=None)
        assert prop.status is PropertyStatus.REJECTED
        assert prop.rejection_reason


class TestStatusTransitions:
    def test_a_draft_cannot_jump_straight_to_published(self) -> None:
        with pytest.raises(errors.InvalidStatusTransitionError):
            publishable().approve(now=NOW, by=None)

    def test_unpublishing_keeps_everything(self) -> None:
        # A hotel closing for monsoon should not rebuild its listing in October.
        prop = publishable()
        prop.submit_for_review()
        prop.approve(now=NOW, by=None)
        prop.unpublish()
        assert prop.status is PropertyStatus.UNPUBLISHED
        assert len(prop.room_types) == 1
        assert len(prop.images) == MIN_IMAGES_TO_PUBLISH

    def test_republishing_skips_the_review_queue(self) -> None:
        prop = publishable()
        prop.submit_for_review()
        prop.approve(now=NOW, by=None)
        prop.unpublish()
        prop.republish()
        assert prop.status is PropertyStatus.PUBLISHED

    def test_republishing_still_re_checks_completeness(self) -> None:
        prop = publishable()
        prop.submit_for_review()
        prop.approve(now=NOW, by=None)
        prop.unpublish()
        prop.images.clear()
        with pytest.raises(errors.PropertyNotPublishableError):
            prop.republish()

    def test_a_vendor_cannot_reverse_a_suspension(self) -> None:
        """Suspension is for fraud and safety complaints. If a vendor could
        republish, it would mean nothing."""
        prop = publishable()
        prop.submit_for_review()
        prop.approve(now=NOW, by=None)
        prop.suspend(reason="Fraudulent listing", by=uuid.uuid4())

        assert prop.status is PropertyStatus.SUSPENDED
        with pytest.raises(errors.InvalidStatusTransitionError):
            prop.republish()

    def test_a_suspended_listing_cannot_be_edited(self) -> None:
        prop = publishable()
        prop.submit_for_review()
        prop.approve(now=NOW, by=None)
        prop.suspend(reason="fraud", by=None)
        with pytest.raises(errors.PropertyNotEditableError):
            prop.update_details(name="New name")


class TestUpdates:
    def test_returns_only_what_actually_changed(self) -> None:
        # A save that changed nothing must not trigger a search reindex.
        prop = draft()
        assert prop.update_details(name="Sea Breeze Resort") == []
        assert prop.update_details(name="Ocean View Resort") == ["name"]

    def test_the_slug_does_not_follow_a_rename(self) -> None:
        """Every existing link, share and indexed search result points at the
        old slug; the id in the URL resolves it anyway."""
        prop = draft()
        prop.update_details(name="Completely Different Name")
        assert prop.slug == "sea-breeze-resort"

    def test_only_search_relevant_changes_request_a_reindex(self) -> None:
        prop = draft()
        prop.update_details(house_rules=["No smoking"])
        assert prop.pull_events()[0].requires_reindex is False

        prop.update_details(name="Renamed")
        assert prop.pull_events()[0].requires_reindex is True
