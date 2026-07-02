import pytest
from datetime import date
from src.health.sleep_correlator import SleepCorrelator
from src.health.hrv_trend import HRVTrendAnalyzer
from src.health.readiness import ReadinessCalculator
from src.ingestion.garmin_health_client import HealthDaily


def test_correlator_returns_coefficient():
    data = [(80, 100), (75, 90), (85, 110), (70, 80), (90, 120)] * 6
    r = SleepCorrelator().correlate(data)
    assert r is not None and -1.0 <= r <= 1.0


def test_correlator_positive_for_good_sleep():
    assert SleepCorrelator().correlate([(i + 60, i + 80) for i in range(20)]) > 0


def test_correlator_none_with_insufficient():
    assert SleepCorrelator().correlate([(80, 100), (75, 90), (85, 110)]) is None


def test_hrv_detects_declining():
    r = HRVTrendAnalyzer().analyze({date(2024, 1, i + 1): 55 - i * 2 for i in range(10)})
    assert r.trend == "declining" and r.alert == True


def test_hrv_detects_stable():
    r = HRVTrendAnalyzer().analyze({date(2024, 1, i + 1): 47 + i % 4 for i in range(10)})
    assert r.trend == "stable" and r.alert == False


def test_hrv_uses_7day_ma():
    r = HRVTrendAnalyzer().analyze({date(2024, 1, i + 1): 45.0 for i in range(14)})
    assert len(r.ma7_values) >= 7


def test_readiness_high():
    good = HealthDaily(date=date(2024, 1, 15), sleep_score=90, hrv_rmssd_ms=55, body_battery_max=90)
    assert ReadinessCalculator().calculate(good, {"tsb": 5.0}) >= 75


def test_readiness_low():
    poor = HealthDaily(date=date(2024, 1, 15), sleep_score=45, hrv_rmssd_ms=22, body_battery_max=40)
    assert ReadinessCalculator().calculate(poor, {"tsb": -25.0}) <= 50


def test_readiness_handles_missing_hrv():
    h = HealthDaily(date=date(2024, 1, 15), sleep_score=70)
    s = ReadinessCalculator().calculate(h, {"tsb": 0})
    assert 0 <= s <= 100


def test_recommendation_matches_band():
    c = ReadinessCalculator()
    assert "Descanso" in c.get_recommendation(40)
    assert "moderado" in c.get_recommendation(65).lower()
    assert "intenso" in c.get_recommendation(80).lower()
