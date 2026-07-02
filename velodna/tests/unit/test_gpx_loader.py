import pytest
from pathlib import Path
from src.ingestion.gpx_loader import GPXLoader, Route, RouteWaypoint, GPXParseError
FIXTURES = Path("tests/fixtures")

def test_load_gpx_returns_route_with_waypoints():
    loader = GPXLoader()
    route = loader.load(FIXTURES / "sample.gpx")
    assert isinstance(route, Route)
    assert route.distance_m > 0
    assert len(route.waypoints) > 0
    assert isinstance(route.waypoints[0], RouteWaypoint)

def test_load_gpx_invalid_raises_error():
    loader = GPXLoader()
    with pytest.raises(GPXParseError):
        loader.load(Path("nonexistent.gpx"))
