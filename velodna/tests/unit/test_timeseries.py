"""Testes da camada de séries temporais e das métricas derivadas dela."""
import numpy as np
import pytest
import duckdb

from analytics.hr_metrics import (
    HeartRateProfile,
    calibrate_threshold_ratio,
    compute_hrss,
    decoupling_pct,
    trimp,
)
from analytics.power_metrics import (
    compute_power_metrics,
    normalized_power,
    rolling_mean,
)
from analytics.timeseries import ActivitySeries, Segment, load_series
from storage.catalog_store import CatalogStore
from storage.models import ActivityStream

ATHLETE_ID = "11111111-1111-1111-1111-111111111111"


def series(*channel_segments):
    """Monta uma ActivitySeries a partir de dicionários {canal: lista}."""
    segments = []
    start = 0
    for channels in channel_segments:
        arrays = {k: np.array(v, dtype=float) for k, v in channels.items()}
        segments.append(Segment(start_time_s=start, channels=arrays))
        start += len(next(iter(arrays.values()))) + 600
    return ActivitySeries("test", segments)


# --- Segmentação por pausa -------------------------------------------------

@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    store = CatalogStore(conn)
    store.initialize_schema()
    conn.execute("INSERT INTO athletes (id, name) VALUES (?, ?)", [ATHLETE_ID, "T"])
    yield conn
    conn.close()


def _insert_streams(conn, times_and_power):
    from datetime import datetime, timezone

    from storage.models import Activity

    store = CatalogStore(conn)
    activity_id = store.upsert_activity(
        Activity(
            source="fit",
            sport_type="cycling",
            started_at=datetime(2024, 1, 1, 8, tzinfo=timezone.utc),
            elapsed_time_s=3600,
        ),
        ATHLETE_ID,
    )
    store.insert_streams(
        activity_id,
        [ActivityStream(time_s=t, power_w=p) for t, p in times_and_power],
    )
    return activity_id


def test_load_series_splits_on_long_gap(db):
    """Uma lacuna maior que o limiar de pausa separa a série em dois segmentos."""
    points = [(t, 200.0) for t in range(0, 60)] + [
        (t, 200.0) for t in range(600, 660)
    ]
    activity_id = _insert_streams(db, points)

    loaded = load_series(db, activity_id)
    assert len(loaded.segments) == 2


def test_load_series_keeps_short_gap_in_one_segment(db):
    """Falha curta de gravação é interpolada, não vira pausa."""
    points = [(t, 200.0) for t in range(0, 60)] + [
        (t, 200.0) for t in range(63, 120)
    ]
    activity_id = _insert_streams(db, points)

    loaded = load_series(db, activity_id)
    assert len(loaded.segments) == 1
    assert len(loaded.segments[0]) == 120


def test_moving_time_excludes_pause(db):
    """O tempo em movimento ignora a pausa; o decorrido, não."""
    points = [(t, 200.0) for t in range(0, 60)] + [
        (t, 200.0) for t in range(600, 660)
    ]
    activity_id = _insert_streams(db, points)

    loaded = load_series(db, activity_id)
    assert loaded.moving_time_s == 120
    assert loaded.elapsed_time_s == 659


def test_artifact_above_physiological_limit_is_dropped(db):
    """Um pico de 3600 W é artefato de sensor e não pode virar recorde."""
    points = [(t, 200.0) for t in range(0, 60)]
    points[30] = (30, 3600.0)
    activity_id = _insert_streams(db, points)

    loaded = load_series(db, activity_id)
    assert loaded.concat("power").max() < 2500


# --- Normalized Power ------------------------------------------------------

def test_rolling_mean_matches_manual_average():
    values = np.arange(10, dtype=float)
    assert rolling_mean(values, 3)[0] == pytest.approx(1.0)


def test_rolling_mean_empty_when_window_too_large():
    assert rolling_mean(np.arange(5, dtype=float), 10).size == 0


def test_np_equals_avg_for_constant_power():
    """Com potência constante, NP e potência média coincidem."""
    constant = series({"power": [250.0] * 600})
    assert normalized_power(constant) == pytest.approx(250.0, rel=1e-6)


def test_np_exceeds_avg_for_variable_power():
    """A NP pune a variabilidade — é isso que a distingue da média."""
    variable = series({"power": ([400.0] * 30 + [100.0] * 30) * 20})
    avg = np.mean(([400.0] * 30 + [100.0] * 30) * 20)
    assert normalized_power(variable) > avg


def test_np_ignores_gap_between_segments():
    """A janela de 30 s não atravessa a pausa e não cria rampa artificial."""
    split = series({"power": [250.0] * 300}, {"power": [250.0] * 300})
    assert normalized_power(split) == pytest.approx(250.0, rel=1e-6)


def test_np_none_without_enough_samples():
    assert normalized_power(series({"power": [250.0] * 10})) is None


def test_variability_index_is_np_over_avg():
    metrics = compute_power_metrics(
        series({"power": ([400.0] * 30 + [100.0] * 30) * 20}), ftp_w=250
    )
    assert metrics.variability_index == pytest.approx(
        metrics.normalized_power_w / metrics.avg_power_w, rel=1e-3
    )


def test_tss_of_one_hour_at_ftp_is_100():
    """Definição do TSS: uma hora exatamente no FTP vale 100 pontos."""
    metrics = compute_power_metrics(series({"power": [250.0] * 3600}), ftp_w=250)
    assert metrics.tss == pytest.approx(100.0, rel=0.01)
    assert metrics.intensity_factor == pytest.approx(1.0, rel=0.01)


def test_no_metrics_without_power():
    assert compute_power_metrics(series({"power": [np.nan] * 100}), 250).tss is None


# --- Carga por frequência cardíaca -----------------------------------------

def test_trimp_grows_with_intensity():
    assert trimp(3600, 0.9) > trimp(3600, 0.5)


def test_hrss_of_one_hour_at_threshold_is_100():
    """Âncora do HRSS: uma hora no limiar equivale a 100, como o TSS."""
    profile = HeartRateProfile(max_hr_bpm=190, resting_hr_bpm=50, threshold_hr_bpm=169)
    at_threshold = series({"hr": [169.0] * 3600})
    assert compute_hrss(at_threshold, profile) == pytest.approx(100.0, rel=0.02)


def test_hrss_none_without_hr():
    profile = HeartRateProfile(max_hr_bpm=190, resting_hr_bpm=50)
    assert compute_hrss(series({"power": [200.0] * 100}), profile) is None


def test_calibration_returns_lower_anchor_when_hrss_underestimates():
    """HRSS abaixo do TSS de potência significa âncora de limiar alta demais."""
    profile = HeartRateProfile(max_hr_bpm=190, resting_hr_bpm=50)
    pairs = [(100.0, 75.0)] * 50
    calibrated = calibrate_threshold_ratio(pairs, profile)
    assert calibrated is not None
    assert calibrated < profile.threshold_reserve_ratio


def test_calibration_needs_enough_pairs():
    profile = HeartRateProfile(max_hr_bpm=190, resting_hr_bpm=50)
    assert calibrate_threshold_ratio([(100.0, 75.0)] * 5, profile) is None


# --- Decoupling ------------------------------------------------------------

def test_decoupling_zero_when_ratio_stable():
    stable = series({"power": [200.0] * 600, "hr": [150.0] * 600})
    assert decoupling_pct(stable) == pytest.approx(0.0, abs=0.01)


def test_decoupling_positive_when_hr_drifts_up():
    """Mesma potência com FC subindo é deriva cardíaca — decoupling positivo."""
    drifting = series(
        {"power": [200.0] * 600, "hr": [140.0] * 300 + [160.0] * 300}
    )
    assert decoupling_pct(drifting) > 0
