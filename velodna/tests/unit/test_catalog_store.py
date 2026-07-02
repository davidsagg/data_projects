import pytest
import duckdb
from datetime import datetime, date, timezone
from src.ingestion.catalog_store import CatalogStore
from src.ingestion.fit_parser import Activity
from src.ingestion.garmin_health_client import HealthDaily

EXPECTED_TABLES = {
    "activities","activity_streams","health_daily",
    "routes","route_segments","athlete_metrics","power_curve"
}

@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()

@pytest.fixture
def store(db):
    s = CatalogStore(db)
    s.initialize_schema()
    return s

def _make_activity(garmin_id="ride_001", distance_m=50000.0, start_time=None):
    return Activity(
        garmin_id=garmin_id, sport_type="cycling",
        start_time=start_time or datetime(2024,1,15,8,tzinfo=timezone.utc),
        duration_s=7200, distance_m=distance_m, elevation_m=500.0)

def _make_health(target_date=date(2024,1,15), sleep_score=78):
    return HealthDaily(date=target_date, sleep_duration_h=7.0,
        sleep_score=sleep_score, hrv_rmssd_ms=42.5)

# Grupo 1: Schema
def test_schema_creates_all_seven_tables(db):
    CatalogStore(db).initialize_schema()
    tables = {r[0] for r in db.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}
    assert EXPECTED_TABLES.issubset(tables)

def test_initialize_schema_is_idempotent(store, db):
    CatalogStore(db).initialize_schema()

# Grupo 2: Activities
def test_upsert_activity_inserts_new_record(store, db):
    store.upsert_activity(_make_activity(), "act-001")
    assert db.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 1

def test_upsert_activity_updates_existing_by_garmin_id(store, db):
    store.upsert_activity(_make_activity(distance_m=50000), "act-001")
    store.upsert_activity(_make_activity(distance_m=55000), "act-001")
    assert db.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 1
    assert db.execute("SELECT distance_m FROM activities").fetchone()[0] == pytest.approx(55000.0)

def test_get_activities_by_date_range(store, db):
    for i,(gid,dt) in enumerate([
        ("r1",datetime(2024,1,1, tzinfo=timezone.utc)),
        ("r2",datetime(2024,1,15,tzinfo=timezone.utc)),
        ("r3",datetime(2024,2,1, tzinfo=timezone.utc)),
    ]):
        store.upsert_activity(_make_activity(gid, start_time=dt), f"a{i}")
    results = store.get_activities(start=date(2024,1,1), end=date(2024,1,31))
    assert len(results) == 2

# Grupo 3: Health
def test_upsert_health_daily_inserts_new_record(store, db):
    store.upsert_health_daily(_make_health())
    assert db.execute("SELECT COUNT(*) FROM health_daily").fetchone()[0] == 1

def test_upsert_health_daily_updates_by_date(store, db):
    store.upsert_health_daily(_make_health(sleep_score=70))
    store.upsert_health_daily(_make_health(sleep_score=85))
    assert db.execute("SELECT COUNT(*) FROM health_daily").fetchone()[0] == 1
    assert db.execute("SELECT sleep_score FROM health_daily").fetchone()[0] == 85

# Grupo 4: Routes
def test_upsert_route_with_segments(store, db):
    segs = [{"segment_id":f"s{i}","route_id":"rt-1","sequence":i,
             "segment_type":"flat","length_m":500} for i in range(3)]
    store.upsert_route({"route_id":"rt-1","name":"Test","source":"manual_upload",
                        "distance_m":1500,"elevation_gain_m":0,"elevation_loss_m":0}, segs)
    assert db.execute("SELECT COUNT(*) FROM routes").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM route_segments").fetchone()[0] == 3

def test_insert_segment_without_route_raises_error(store, db):
    with pytest.raises(Exception):
        store.insert_segment({"segment_id":"s0","route_id":"ghost","sequence":0})

# Grupo 5: Metrics
def test_upsert_athlete_metrics(store, db):
    store.upsert_athlete_metrics(date(2024,1,15), 45.2, 52.1, -6.9, 280)
    row = db.execute("SELECT ctl,tsb FROM athlete_metrics").fetchone()
    assert row[0] == pytest.approx(45.2)
    assert row[1] == pytest.approx(-6.9)

def test_upsert_power_curve(store, db):
    store.upsert_activity(_make_activity(), "act-001")
    store.upsert_power_curve(date(2024,1,15), 300, 320.0, "act-001")
    row = db.execute("SELECT duration_s,best_power_w FROM power_curve").fetchone()
    assert row[0] == 300 and row[1] == pytest.approx(320.0)

# Grupo 6: Analytics
def test_get_weekly_tss_returns_sum_per_week(store, db):
    for i,(gid,dt,tss) in enumerate([
        ("r1",datetime(2024,1,2, tzinfo=timezone.utc),150.0),
        ("r2",datetime(2024,1,5, tzinfo=timezone.utc),150.0),
        ("r3",datetime(2024,1,9, tzinfo=timezone.utc),250.0),
    ]):
        store.upsert_activity(_make_activity(gid, start_time=dt), f"a{i}")
        db.execute("UPDATE activities SET tss=? WHERE garmin_id=?", [tss, gid])
    weekly = store.get_weekly_tss(year=2024, month=1)
    assert sum(weekly.values()) == pytest.approx(550.0)
