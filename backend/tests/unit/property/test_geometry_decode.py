"""Decoding a PostGIS point back into the domain.

This file exists because of a bug that cost the platform its entire publishing
flow and produced no error anywhere.

``geoalchemy2.shape.to_shape`` needs Shapely, which was not installed. The
decode was wrapped in ``except Exception``, so the ``ImportError`` was absorbed
and every property in the database decoded to *no coordinates*. Map search kept
working — it runs through raw PostGIS and never touches this function — so
nothing looked broken. The only symptom was that the publish checklist reported
``map_location`` missing for every listing ever created, which reads exactly
like a product rule rather than a missing package.

Two things are asserted here, and the second is the one that matters:

* a real geometry round-trips to the coordinates that went in;
* a *dependency* failure is not silently treated as bad data.
"""

from __future__ import annotations

import pytest
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point

from app.modules.property.domain.value_objects import GeoPoint
from app.modules.property.infrastructure.mappers import _to_point, _wkt

pytestmark = pytest.mark.unit

# Anjuna, Goa — the coordinates used throughout the fixtures.
LATITUDE = 15.5867
LONGITUDE = 73.7431


def test_shapely_is_installed() -> None:
    """The dependency assertion.

    Not a tautology: ``geoalchemy2`` installs and imports perfectly well
    without Shapely, and only fails at the moment it is asked to decode. If
    this line ever fails, publishing is broken platform-wide and every other
    test in the suite still passes.
    """
    assert to_shape(from_shape(Point(LONGITUDE, LATITUDE))).x == LONGITUDE


def test_a_point_round_trips() -> None:
    element = from_shape(Point(LONGITUDE, LATITUDE), srid=4326)
    decoded = _to_point(element)

    assert decoded is not None, "a valid geometry must not decode to None"
    assert decoded.latitude == pytest.approx(LATITUDE)
    assert decoded.longitude == pytest.approx(LONGITUDE)


def test_longitude_and_latitude_are_not_swapped() -> None:
    """WKT is ``POINT(longitude latitude)`` and the domain is (lat, lon).

    Swapping them puts an Indian property in Somalia, and both numbers stay
    plausible enough that nobody notices until a guest searches by map.
    """
    element = from_shape(Point(LONGITUDE, LATITUDE), srid=4326)
    decoded = _to_point(element)

    assert decoded is not None
    assert decoded.latitude < decoded.longitude, "Goa is ~15°N, ~73°E"
    assert _wkt(GeoPoint(latitude=LATITUDE, longitude=LONGITUDE)) == (
        f"SRID=4326;POINT({LONGITUDE} {LATITUDE})"
    )


def test_no_geometry_is_none() -> None:
    assert _to_point(None) is None


@pytest.mark.parametrize("value", ["not-a-geometry", b"\x00\x01", 42, object()])
def test_unreadable_geometry_is_tolerated(value: object) -> None:
    """Bad *data* is survivable: one broken coordinate should hide a property
    from map search, not take its listing page down."""
    assert _to_point(value) is None


def test_a_missing_dependency_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """**The regression.**

    An ``ImportError`` here means the deployment is broken, not that the row is
    bad, and absorbing it turns a five-minute fix into a product mystery. The
    except clause must be narrow enough to let it through.
    """
    import app.modules.property.infrastructure.mappers as mappers

    def explode(_: object) -> object:
        msg = "This feature needs the optional Shapely dependency."
        raise ImportError(msg)

    monkeypatch.setattr(mappers, "to_shape", explode)

    with pytest.raises(ImportError):
        _to_point(from_shape(Point(LONGITUDE, LATITUDE), srid=4326))
