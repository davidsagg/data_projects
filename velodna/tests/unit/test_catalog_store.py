import pytest
import duckdb
from datetime import datetime, date, timezone

from storage.catalog_store import CatalogStore
from storage.models import Activity, ActivityStream

EXPECTED_TABLES = {
    "athletes", "activities", "activity_streams", "segments", "segment_efforts",
    "routes", "route_waypoints", "health_metrics", "training_load",
    "power_zones", "hr_zones", "ai_conversations", "ai_insights", "power_curves",
}

ATHLETE_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def store(db):
    s = CatalogStore(db)
    s.initialize_schema()
    db.execute(
        "INSERT INTO athletes (id, name) VALUES (?, ?)", [ATHLETE_ID, "Teste"]
    )
    return s


def _make_activity(garmin_id="ride_001", distance_m=50000.0, started_at=None):
    return Activity(
        source="fit",
        garmin_id=garmin_id,
        sport_type="cycling",
        started_at=started_at or datetime(2024, 1, 15, 8, tzinfo=timezone.utc),
        elapsed_time_s=7200,
        distance_m=distance_m,
        elevation_gain_m=500.0,
    )


# Grupo 1: Schema
def test_schema_creates_all_tables(db):
    CatalogStore(db).initialize_schema()
    tables = {
        r[0]
        for r in db.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main'"
        ).fetchall()
    }
    assert EXPECTED_TABLES.issubset(tables)


def test_initialize_schema_is_idempotent(store, db):
    CatalogStore(db).initialize_schema()


# Grupo 2: Activities
def test_upsert_activity_inserts_new_record(store, db):
    store.upsert_activity(_make_activity(), ATHLETE_ID)
    assert db.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 1


def test_upsert_activity_updates_existing_by_garmin_id(store, db):
    store.upsert_activity(_make_activity(distance_m=50000), ATHLETE_ID, "ride_001")
    store.upsert_activity(_make_activity(distance_m=55000), ATHLETE_ID, "ride_001")
    assert db.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 1
    assert db.execute("SELECT distance_m FROM activities").fetchone()[0] == pytest.approx(
        55000.0
    )


def test_query_activities_by_date_range(store):
    for gid, dt in [
        ("r1", datetime(2024, 1, 1, tzinfo=timezone.utc)),
        ("r2", datetime(2024, 1, 15, tzinfo=timezone.utc)),
        ("r3", datetime(2024, 2, 1, tzinfo=timezone.utc)),
    ]:
        store.upsert_activity(_make_activity(gid, started_at=dt), ATHLETE_ID, gid)

    results = store.query_activities_by_date_range(
        ATHLETE_ID,
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 31, tzinfo=timezone.utc),
    )
    assert len(results) == 2


def test_insert_streams_persists_points(store, db):
    activity_id = store.upsert_activity(_make_activity(), ATHLETE_ID)
    store.insert_streams(
        activity_id,
        [ActivityStream(time_s=i, power_w=200 + i, hr_bpm=140) for i in range(10)],
    )
    assert db.execute("SELECT COUNT(*) FROM activity_streams").fetchone()[0] == 10


def test_get_streams_returns_ordered_by_time(store):
    activity_id = store.upsert_activity(_make_activity(), ATHLETE_ID)
    store.insert_streams(
        activity_id,
        [ActivityStream(time_s=t, power_w=float(t)) for t in (5, 1, 3)],
    )
    times = [s.time_s for s in store.get_streams_for_activity(activity_id)]
    assert times == [1, 3, 5]


# Grupo 3: Health
def test_insert_health_daily_inserts_new_record(store, db):
    store.insert_health_daily(
        ATHLETE_ID, date(2024, 1, 15), sleep_hours=7.0, sleep_quality_score=78
    )
    assert db.execute("SELECT COUNT(*) FROM health_metrics").fetchone()[0] == 1


def test_insert_health_daily_updates_by_date(store, db):
    store.insert_health_daily(ATHLETE_ID, date(2024, 1, 15), sleep_quality_score=70)
    store.insert_health_daily(ATHLETE_ID, date(2024, 1, 15), sleep_quality_score=85)
    assert db.execute("SELECT COUNT(*) FROM health_metrics").fetchone()[0] == 1
    assert (
        db.execute("SELECT sleep_quality_score FROM health_metrics").fetchone()[0] == 85
    )


def test_insert_health_daily_rejects_unknown_field(store):
    with pytest.raises(ValueError):
        store.insert_health_daily(ATHLETE_ID, date(2024, 1, 15), campo_inexistente=1)


# Grupo 4: Routes
def test_insert_route_with_waypoints(store, db):
    waypoints = [
        {"lat": -22.9 + i / 1000, "lon": -43.2, "altitude_m": 10.0 * i}
        for i in range(3)
    ]
    store.insert_route(ATHLETE_ID, "Test", waypoints, distance_m=1500)
    assert db.execute("SELECT COUNT(*) FROM routes").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM route_waypoints").fetchone()[0] == 3


# Grupo 5: Training load
def test_upsert_training_load(store, db):
    store.upsert_training_load(ATHLETE_ID, date(2024, 1, 15), 45.2, 52.1, -6.9, 120.0)
    row = db.execute("SELECT ctl, tsb, daily_tss FROM training_load").fetchone()
    assert row[0] == pytest.approx(45.2)
    assert row[1] == pytest.approx(-6.9)
    assert row[2] == pytest.approx(120.0)


def test_upsert_training_load_replaces_same_day(store, db):
    store.upsert_training_load(ATHLETE_ID, date(2024, 1, 15), 40.0, 50.0, -10.0)
    store.upsert_training_load(ATHLETE_ID, date(2024, 1, 15), 45.0, 52.0, -7.0)
    assert db.execute("SELECT COUNT(*) FROM training_load").fetchone()[0] == 1
    assert db.execute("SELECT ctl FROM training_load").fetchone()[0] == pytest.approx(45.0)


def test_bulk_upsert_training_load_replaces_series(store, db):
    store.upsert_training_load(ATHLETE_ID, date(2023, 1, 1), 10.0, 10.0, 0.0)
    store.bulk_upsert_training_load(
        ATHLETE_ID,
        [(date(2024, 1, d), float(d), float(d), 0.0, 50.0) for d in range(1, 6)],
    )
    assert db.execute("SELECT COUNT(*) FROM training_load").fetchone()[0] == 5


# Grupo 6: Power curve
def test_save_power_curve(store, db):
    activity_id = store.upsert_activity(_make_activity(), ATHLETE_ID)
    store.save_power_curve(activity_id, date(2024, 1, 15), {300: 320.0, 60: 400.0})
    row = db.execute(
        "SELECT duration_s, power_w FROM power_curves WHERE duration_s = 300"
    ).fetchone()
    assert row[0] == 300 and row[1] == pytest.approx(320.0)


def test_save_power_curve_is_idempotent(store):
    activity_id = store.upsert_activity(_make_activity(), ATHLETE_ID)
    store.save_power_curve(activity_id, date(2024, 1, 15), {300: 320.0})
    store.save_power_curve(activity_id, date(2024, 1, 15), {300: 350.0})
    assert store.get_power_curve(activity_id) == {300: pytest.approx(350.0)}
