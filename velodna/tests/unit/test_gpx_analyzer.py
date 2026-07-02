import pytest
import duckdb
from src.routes.gpx_analyzer import GPXAnalyzer, ElevationProfile, AnalyzedSegment
from src.routes.segment_classifier import SegmentClassifier
from src.ingestion.catalog_store import CatalogStore
from src.ingestion.gpx_loader import Route, RouteWaypoint


def route(wps_data):
    wps = [RouteWaypoint(lat=d[0], lon=d[1], altitude_m=d[2], distance_m=d[3]) for d in wps_data]
    return Route(name="T", source="manual", gpx_file_path="/t.gpx",
                 distance_m=wps_data[-1][3], elevation_gain_m=0, elevation_loss_m=0, waypoints=wps)


def test_analyzer_calculates_elevation_profile():
    p = GPXAnalyzer().analyze(route([(-23.55, -46.63, 760, 0), (-23.551, -46.631, 800, 500), (-23.552, -46.632, 780, 1000)]))
    assert isinstance(p, ElevationProfile) and p.total_gain_m >= 30 and p.total_loss_m >= 10


def test_analyzer_calculates_gradient():
    p = GPXAnalyzer().analyze(route([(-23.55, -46.63, 760, 0), (-23.551, -46.631, 785, 500)]))
    assert len(p.segments) > 0 and max(s.avg_gradient_pct for s in p.segments) == pytest.approx(5.0, abs=1.0)


def test_classifier_labels():
    segs = [AnalyzedSegment(0, 1000, 1000, 60, 6.0), AnalyzedSegment(1000, 2000, 1000, 5, 0.5), AnalyzedSegment(2000, 3000, 1000, -50, -5.0)]
    c = SegmentClassifier().classify(segs)
    assert c[0].segment_type == "climb" and c[1].segment_type == "flat" and c[2].segment_type == "descent"


def test_classifier_assigns_category():
    s = SegmentClassifier().classify([AnalyzedSegment(0, 4000, 4000, 200, 5.0)])
    assert s[0].category is not None and ("Cat" in s[0].category or s[0].category == "HC")


def test_flat_route_zero_gradient():
    p = GPXAnalyzer().analyze(route([(-23.55, -46.63, 760, 0), (-23.551, -46.631, 760, 500)]))
    assert p.max_gradient_pct == pytest.approx(0, abs=0.1) and p.total_gain_m == pytest.approx(0, abs=0.1)


def test_analyzer_stores_in_duckdb():
    conn = duckdb.connect(":memory:")
    s = CatalogStore(conn)
    s.initialize_schema()
    r = route([(-23.55, -46.63, 760, 0), (-23.551, -46.631, 800, 500), (-23.552, -46.632, 780, 1000)])
    GPXAnalyzer().analyze_and_store(r, s)
    assert conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM route_segments").fetchone()[0] > 0
    conn.close()
