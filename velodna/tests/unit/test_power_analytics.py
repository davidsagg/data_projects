import pytest
from datetime import datetime, timedelta, timezone
from src.ingestion.fit_parser import ActivityStream
from src.analytics.power_curve_engine import PowerCurveEngine
from src.analytics.zone_analyzer import ZoneAnalyzer
from src.analytics.wprime_model import WPrimeModel


def S(powers):
    b = datetime(2024, 1, 1, 8, tzinfo=timezone.utc)
    return [ActivityStream(timestamp=b + timedelta(seconds=i), power_w=p) for i, p in enumerate(powers)]


def test_power_curve_best_per_duration():
    c = PowerCurveEngine().compute(S([400] * 5 + [320] * 300 + [200] * 600), [5, 300])
    assert c[5] == pytest.approx(400, rel=0.05) and c[300] >= 270.0  # ≥ 300 * 0.9


def test_power_curve_zero_no_data():
    streams = [ActivityStream(timestamp=datetime(2024, 1, 1, 8, tzinfo=timezone.utc)) for _ in range(10)]
    assert all(v == 0.0 for v in PowerCurveEngine().compute(streams, [5, 300]).values())


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
