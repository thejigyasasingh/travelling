"""Address, coordinates, occupancy and slugs."""

from __future__ import annotations

import pytest

from app.modules.property.domain.value_objects import (
    Address,
    GeoPoint,
    Occupancy,
    PropertyType,
    slugify,
)

pytestmark = pytest.mark.unit

GOA = GeoPoint(15.5736, 73.7407)
MUMBAI = GeoPoint(19.0760, 72.8777)


class TestPropertyType:
    def test_villas_and_apartments_are_whole_unit(self) -> None:
        """The one structural difference between the five types.

        A villa has exactly one bookable unit, so "2 rooms available" is
        meaningless and occupancy applies to the whole property.
        """
        assert PropertyType.VILLA.is_whole_unit
        assert PropertyType.APARTMENT.is_whole_unit

    def test_hotels_resorts_and_homestays_sell_rooms(self) -> None:
        assert not PropertyType.HOTEL.is_whole_unit
        assert not PropertyType.RESORT.is_whole_unit
        assert not PropertyType.HOMESTAY.is_whole_unit


class TestAddress:
    def test_country_code_is_normalised_to_upper(self) -> None:
        # "India" vs "india" vs "IN" in one column makes "how many properties
        # in India?" unanswerable.
        assert Address.parse(line1="A", city="B", country_code="in").country_code == "IN"

    def test_rejects_a_non_iso_country(self) -> None:
        with pytest.raises(ValueError, match="alpha-2"):
            Address(line1="A", city="B", country_code="India")

    def test_rejects_an_empty_street(self) -> None:
        with pytest.raises(ValueError, match="line 1"):
            Address(line1="  ", city="B", country_code="IN")

    def test_completeness_requires_a_postal_code(self) -> None:
        assert not Address(line1="A", city="B", country_code="IN").is_complete
        assert Address(line1="A", city="B", country_code="IN", postal_code="403509").is_complete

    def test_the_approximate_form_withholds_the_street(self) -> None:
        """What an unbooked guest sees. Publishing the exact address lets
        anyone locate an occupied private home."""
        full = Address(
            line1="Plot 12, Anjuna Beach Road",
            city="Anjuna",
            state="Goa",
            country_code="IN",
            postal_code="403509",
        )
        assert "Plot 12" not in full.approximate()
        assert "Anjuna" in full.approximate()
        assert "Plot 12" in full.single_line()


class TestGeoPoint:
    def test_rejects_out_of_range_coordinates(self) -> None:
        with pytest.raises(ValueError, match="latitude"):
            GeoPoint(91.0, 0.0)
        with pytest.raises(ValueError, match="longitude"):
            GeoPoint(0.0, 181.0)

    def test_rejects_null_island(self) -> None:
        # Almost always an uninitialised value, which would put a Goa villa in
        # the Gulf of Guinea.
        with pytest.raises(ValueError, match="mistake"):
            GeoPoint(0.0, 0.0)

    def test_wkt_puts_longitude_first(self) -> None:
        # The opposite of how humans say it, and a reliable source of
        # properties appearing in the wrong ocean.
        assert GOA.to_wkt() == "POINT(73.7407 15.5736)"

    def test_distance_is_plausible(self) -> None:
        # Goa to Mumbai is roughly 420 km.
        km = GOA.distance_metres(MUMBAI) / 1000
        assert 400 < km < 450

    def test_obfuscation_is_deterministic(self) -> None:
        """A pin that moves on every page load looks broken, and repeated
        samples of a random jitter average out to the true location."""
        assert GOA.obfuscated == GOA.obfuscated
        assert GOA.obfuscated != GOA

    def test_obfuscation_stays_in_the_right_neighbourhood(self) -> None:
        # ~1 km: enough for "is this near the beach?", not enough to stand
        # outside someone's house.
        assert GOA.distance_metres(GOA.obfuscated) < 2_000


class TestOccupancy:
    def test_infants_are_not_billable(self) -> None:
        # Charging for one is a support ticket, not revenue.
        occ = Occupancy(adults=2, children=1, infants=1)
        assert occ.billable_guests == 3
        assert occ.total == 4

    def test_at_least_one_adult_is_required(self) -> None:
        with pytest.raises(ValueError, match="one adult"):
            Occupancy(adults=0, children=2)

    def test_rejects_implausible_counts(self) -> None:
        with pytest.raises(ValueError):
            Occupancy(adults=50)


class TestSlugify:
    def test_produces_a_readable_url_segment(self) -> None:
        assert slugify("Sea Breeze Resort & Spa") == "sea-breeze-resort-spa"

    def test_transliterates_rather_than_percent_encoding(self) -> None:
        # "/goa-beach-villa" is shareable and indexable; "/%E0%A4%97" is not.
        assert slugify("Café Münchën") == "cafe-munchen"

    def test_truncates_without_a_trailing_hyphen(self) -> None:
        slug = slugify("A very long property name " * 10, max_length=40)
        assert len(slug) <= 40
        assert not slug.endswith("-")

    def test_never_returns_empty(self) -> None:
        # An empty slug would produce a URL that resolves to the collection.
        assert slugify("!!!") == "property"
