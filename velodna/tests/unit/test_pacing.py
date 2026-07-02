import pytest
from src.routes.gpx_analyzer import AnalyzedSegment
from src.routes.pacing_strategy import PacingStrategy
from src.routes.time_estimator import TimeEstimator


def test_pacing_lower_on_climbs():
    r = PacingStrategy(280).calculate([AnalyzedSegment(0, 1000, 1000, 5, 0.5, "flat"),
                                       AnalyzedSegment(0, 1000, 1000, 80, 8.0, "climb")])
    assert r[1].recommended_power_w < r[0].recommended_power_w


def test_pacing_targets_pct_ftp():
    r = PacingStrategy(280).calculate([AnalyzedSegment(0, 1000, 1000, 5, 0.5, "flat")], 0.85)
    assert r[0].recommended_power_w == pytest.approx(280 * 0.85, rel=0.05)


def test_pacing_penalizes_negative_tsb():
    s = [AnalyzedSegment(0, 1000, 1000, 5, 0.5, "flat")]
    base = PacingStrategy(280, tsb=0).calculate(s)[0].recommended_power_w
    fat = PacingStrategy(280, tsb=-20).calculate(s)[0].recommended_power_w
    assert fat < base


def test_estimator_plausible():
    s = [AnalyzedSegment(0, 5000, 5000, 25, 0.5, "flat"),
         AnalyzedSegment(0, 2000, 2000, 100, 5, "climb"),
         AnalyzedSegment(0, 3000, 3000, -90, -3, "descent")]
    assert 4800 < TimeEstimator(280).estimate(s) < 10800


def test_estimator_slower_on_climbs():
    te = TimeEstimator(280)
    flat = AnalyzedSegment(0, 1000, 1000, 5, 0.5, "flat")
    climb = AnalyzedSegment(0, 1000, 1000, 70, 7, "climb")
    assert te.estimate([climb]) > te.estimate([flat])


def test_estimator_adjusts_for_fitness():
    s = [AnalyzedSegment(0, 5000, 5000, 150, 3, "climb")]
    assert TimeEstimator(280, ctl=70).estimate(s) < TimeEstimator(280, ctl=30).estimate(s)
