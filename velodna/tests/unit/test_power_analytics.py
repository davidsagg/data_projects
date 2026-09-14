import numpy as np
import pytest
from datetime import datetime, timedelta, timezone
from ingestion.fit_parser import ActivityStream
from analytics.power_curve_engine import PowerCurveEngine
from analytics.timeseries import ActivitySeries, Segment
from analytics.zone_analyzer import ZoneAnalyzer
from analytics.wprime_model import WPrimeModel


def S(powers):
    b = datetime(2024, 1, 1, 8, tzinfo=timezone.utc)
    return [ActivityStream(timestamp=b + timedelta(seconds=i), power_w=p) for i, p in enumerate(powers)]


def series(*power_segments):
    """Monta uma ActivitySeries com um segmento contínuo por lista informada."""
    segments = []
    start = 0
    for powers in power_segments:
        values = np.array(powers, dtype=float)
        segments.append(Segment(start_time_s=start, channels={"power": values}))
        start += len(powers) + 600  # pausa longa entre segmentos
    return ActivitySeries("test", segments)


def test_power_curve_best_per_duration():
    c = PowerCurveEngine().compute(
        series([400] * 5 + [320] * 300 + [200] * 600), [5, 300]
    )
    assert c[5] == pytest.approx(400, rel=0.05) and c[300] >= 270.0  # ≥ 300 * 0.9


def test_power_curve_omits_durations_without_data():
    assert PowerCurveEngine().compute(series([]), [5, 300]) == {}


def test_power_curve_does_not_span_a_pause():
    """Dois blocos de 200 s separados por pausa não formam um esforço de 400 s."""
    curve = PowerCurveEngine().compute(series([300] * 200, [300] * 200), [200, 400])
    assert curve[200] == pytest.approx(300.0)
    assert 400 not in curve


def test_power_curve_ignores_pause_when_ranking_efforts():
    """O melhor esforço de 60 s é o do bloco forte, não uma média entre blocos."""
    curve = PowerCurveEngine().compute(series([150] * 300, [400] * 60), [60])
    assert curve[60] == pytest.approx(400.0)


def test_zones_time_in_z2_and_z4():
    z = ZoneAnalyzer(300).time_in_zones(S([190] * 60 + [290] * 60))
    assert z.get("Z2", 0) >= 55 and z.get("Z4", 0) >= 55


def test_zones_sum_equals_duration():
    assert sum(ZoneAnalyzer(300).time_in_zones(S([i % 400 + 100 for i in range(600)])).values()) == 600


def test_wprime_depletes_above_ftp():
    b = WPrimeModel(20000, 300).calculate_balance(S([450] * 120))
    assert b[-1] < 20000


def test_wprime_recovers_below_ftp():
    b = WPrimeModel(20000, 300).calculate_balance(S([450] * 60 + [150] * 120))
    assert b[-1] > min(b)
