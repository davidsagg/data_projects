"""Testes da correlação recuperação × performance (US-12)."""
import pytest
from datetime import date, timedelta

from health.sleep_correlator import (
    ALPHA,
    MIN_PAIRS,
    SleepCorrelator,
    pair_recovery_with_performance,
)


def linear_pairs(n, slope=1.0, noise=0.0):
    """Pares perfeitamente lineares, com ruído opcional alternado."""
    return [(i, slope * i + (noise if i % 2 else -noise)) for i in range(n)]


# --- Coeficiente -----------------------------------------------------------

def test_perfect_positive_correlation():
    assert SleepCorrelator().correlate(linear_pairs(20)) == pytest.approx(1.0)


def test_perfect_negative_correlation():
    assert SleepCorrelator().correlate(linear_pairs(20, slope=-1.0)) == pytest.approx(-1.0)


def test_no_correlation_for_constant_series():
    """Série constante não tem variância, então não há correlação a medir."""
    assert SleepCorrelator().correlate([(i, 5.0) for i in range(20)]) == 0.0


def test_returns_none_below_minimum_pairs():
    assert SleepCorrelator().correlate(linear_pairs(MIN_PAIRS - 1)) is None


# --- Significância ---------------------------------------------------------

def test_analyze_reports_n_and_p_value():
    result = SleepCorrelator().analyze(linear_pairs(20), "Sono", "NP")
    assert result.n == 20
    assert result.p_value < ALPHA
    assert result.significant


# Série sem tendência: r ≈ -0,10, que com n = 8 não passa de significância.
NO_TREND_PAIRS = [(1, 4), (2, 7), (3, 2), (4, 8), (5, 1), (6, 6), (7, 3), (8, 5)]


def test_weak_correlation_in_small_sample_is_not_significant():
    """O ponto do valor-p: r pequeno com amostra pequena não sustenta nada."""
    result = SleepCorrelator().analyze(NO_TREND_PAIRS, "Sono", "NP")
    assert abs(result.r) < 0.3
    assert not result.significant


def test_interpretation_says_nothing_detected_when_not_significant():
    result = SleepCorrelator().analyze(NO_TREND_PAIRS, "Sono", "NP")
    assert "Sem associação estatisticamente detectável" in result.interpretation


def test_interpretation_warns_about_causality():
    result = SleepCorrelator().analyze(linear_pairs(30), "Sono", "NP")
    assert "não implica causa" in result.interpretation


def test_strength_bands():
    strong = SleepCorrelator().analyze(linear_pairs(30), "a", "b")
    assert strong.strength == "forte"
    assert strong.direction == "positiva"


def test_direction_is_negative_for_inverse_relation():
    result = SleepCorrelator().analyze(linear_pairs(30, slope=-1.0), "a", "b")
    assert result.direction == "negativa"


def test_analyze_returns_none_below_minimum():
    assert SleepCorrelator().analyze(linear_pairs(3), "a", "b") is None


# --- Pareamento ------------------------------------------------------------

def test_pairs_same_day_recovery_with_performance():
    """O sono da noite que termina em D precede o treino de D."""
    day = date(2026, 1, 10)
    health = [{"date": day, "sleep_hours": 7.5}]
    activities = [{"date": day, "normalized_power_w": 200.0, "tss": 80}]

    pairs = pair_recovery_with_performance(
        health, activities, "sleep_hours", "normalized_power_w"
    )
    assert pairs == [(7.5, 200.0, day)]


def test_pairing_picks_highest_tss_activity_of_the_day():
    day = date(2026, 1, 10)
    health = [{"date": day, "sleep_hours": 7.0}]
    activities = [
        {"date": day, "normalized_power_w": 150.0, "tss": 40},
        {"date": day, "normalized_power_w": 220.0, "tss": 180},
    ]

    pairs = pair_recovery_with_performance(
        health, activities, "sleep_hours", "normalized_power_w"
    )
    assert pairs[0][1] == pytest.approx(220.0)


def test_pairing_skips_days_without_activity():
    health = [
        {"date": date(2026, 1, 10), "sleep_hours": 7.0},
        {"date": date(2026, 1, 11), "sleep_hours": 8.0},
    ]
    activities = [{"date": date(2026, 1, 11), "normalized_power_w": 200.0}]

    pairs = pair_recovery_with_performance(
        health, activities, "sleep_hours", "normalized_power_w"
    )
    assert len(pairs) == 1


def test_pairing_skips_missing_recovery_value():
    day = date(2026, 1, 10)
    health = [{"date": day, "sleep_hours": None}]
    activities = [{"date": day, "normalized_power_w": 200.0}]

    assert (
        pair_recovery_with_performance(
            health, activities, "sleep_hours", "normalized_power_w"
        )
        == []
    )


def test_pairs_are_chronological():
    health = [
        {"date": date(2026, 1, 10) + timedelta(days=i), "sleep_hours": 7.0}
        for i in reversed(range(5))
    ]
    activities = [
        {"date": date(2026, 1, 10) + timedelta(days=i), "normalized_power_w": 200.0}
        for i in range(5)
    ]

    pairs = pair_recovery_with_performance(
        health, activities, "sleep_hours", "normalized_power_w"
    )
    dates = [p[2] for p in pairs]
    assert dates == sorted(dates)
