import pytest
import duckdb
import numpy as np
from datetime import date, datetime, timedelta, timezone

from analytics.pmc_calculator import PMCCalculator, FTPDetector
from analytics.timeseries import ActivitySeries, Segment
from storage.catalog_store import CatalogStore
from storage.models import Activity

ATHLETE_ID = "11111111-1111-1111-1111-111111111111"


def _tss(days=50, tss=80.0):
    return {date(2024, 1, 1) + timedelta(i): tss for i in range(days)}


def _series_power(w=320, secs=1300):
    """Série de um único segmento contínuo com potência constante."""
    return ActivitySeries(
        "test",
        [Segment(start_time_s=0, channels={"power": np.full(secs, float(w))})],
    )


def test_ctl_increases_with_consistent_training():
    series = PMCCalculator().calculate_ctl(_tss(50, 80))
    days = sorted(series)
    assert series[days[-1]] > series[days[0]]


def test_atl_responds_faster_than_ctl():
    calc = PMCCalculator()
    tss = _tss(30, 100)
    assert calc.calculate_atl(tss)[max(tss)] > calc.calculate_ctl(tss)[max(tss)]


def test_tsb_is_ctl_minus_atl():
    assert PMCCalculator().calculate_tsb(50.0, 60.0) == pytest.approx(-10.0)


def test_ftp_95pct_of_best_20min():
    ftp = FTPDetector().detect(_series_power(330, 1300))
    assert ftp is not None and ftp == pytest.approx(330 * 0.95, rel=0.05)


def test_ftp_none_when_insufficient():
    assert FTPDetector().detect(_series_power(320, 300)) is None


# --- Série diária: o ponto onde o cálculo antigo errava ---------------------

def test_daily_series_sums_activities_on_same_day():
    """Dois treinos no mesmo dia somam — antes o segundo sobrescrevia o primeiro."""
    calc = PMCCalculator()
    series = calc.build_daily_series(
        [(date(2024, 1, 1), 80.0), (date(2024, 1, 1), 45.0)],
        end_date=date(2024, 1, 1),
    )
    assert series[date(2024, 1, 1)] == pytest.approx(125.0)


def test_daily_series_fills_rest_days_with_zero():
    """Dias sem treino precisam existir na série para o decaimento ocorrer."""
    calc = PMCCalculator()
    series = calc.build_daily_series(
        [(date(2024, 1, 1), 100.0), (date(2024, 1, 10), 100.0)],
        end_date=date(2024, 1, 10),
    )
    assert len(series) == 10
    assert series[date(2024, 1, 5)] == 0.0


def test_atl_decays_during_rest():
    """Após um bloco forte, parar de treinar tem de derrubar a fadiga."""
    calc = PMCCalculator()
    rows = [(date(2024, 1, 1) + timedelta(i), 150.0) for i in range(14)]
    series = calc.build_daily_series(rows, end_date=date(2024, 1, 28))
    atl = calc.calculate_atl(series)

    assert atl[date(2024, 1, 28)] < atl[date(2024, 1, 14)] * 0.2


def test_tsb_turns_positive_after_taper():
    """Duas semanas de descanso depois de carga constante devem dar forma positiva."""
    calc = PMCCalculator()
    rows = [(date(2024, 1, 1) + timedelta(i), 100.0) for i in range(42)]
    series = calc.build_daily_series(rows, end_date=date(2024, 3, 10))
    ctl = calc.calculate_ctl(series)
    atl = calc.calculate_atl(series)

    last = max(series)
    assert calc.calculate_tsb(ctl[last], atl[last]) > 0


@pytest.fixture
def db30():
    conn = duckdb.connect(":memory:")
    store = CatalogStore(conn)
    store.initialize_schema()
    conn.execute(
        "INSERT INTO athletes (id, name) VALUES (?, ?)", [ATHLETE_ID, "Teste"]
    )
    for i in range(30):
        activity = Activity(
            source="fit",
            garmin_id=f"r{i}",
            sport_type="cycling",
            started_at=datetime(2024, 1, i + 1, 8, tzinfo=timezone.utc),
            elapsed_time_s=3600,
            distance_m=40000,
            elevation_gain_m=300,
            tss=80.0,
        )
        store.upsert_activity(activity, ATHLETE_ID, garmin_id=f"r{i}")
    yield conn
    conn.close()


def test_pmc_stores_metrics(db30):
    store = CatalogStore(db30)
    PMCCalculator().run_and_store(store, date(2024, 1, 30))
    assert (
        db30.execute(
            "SELECT COUNT(*) FROM training_load WHERE ctl IS NOT NULL"
        ).fetchone()[0]
        == 30
    )


def test_pmc_covers_every_day_including_rest(db30):
    """A série persistida vai até end_date mesmo sem treino nos últimos dias."""
    store = CatalogStore(db30)
    PMCCalculator().run_and_store(store, date(2024, 2, 15))
    rows = db30.execute("SELECT COUNT(*), MAX(date) FROM training_load").fetchone()
    assert rows[0] == 46
    assert rows[1] == date(2024, 2, 15)
