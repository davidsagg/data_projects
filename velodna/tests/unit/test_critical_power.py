"""Testes do modelo de potência crítica."""
import pytest

from analytics.critical_power import (
    MAX_VALID_DURATION_S,
    fit_curve,
    fit_two_point,
)


def _synthetic_curve(cp: float, w_prime: float, durations) -> dict[int, float]:
    """Curva gerada pelo próprio modelo, para validar a recuperação dos parâmetros."""
    return {d: w_prime / d + cp for d in durations}


# --- Modelo de dois pontos -------------------------------------------------

def test_two_point_recovers_known_parameters():
    curve = _synthetic_curve(250.0, 20000.0, [60, 720])
    fit = fit_two_point((60, curve[60]), (720, curve[720]))

    assert fit.cp_w == pytest.approx(250.0, abs=0.5)
    assert fit.w_prime_j == pytest.approx(20000.0, rel=0.01)


def test_two_point_matches_athlete_protocol():
    """Protocolo 1 min + 12 min do atleta: 504 W e 242 W devem dar CP ≈ 218 W."""
    fit = fit_two_point((60, 504.0), (720, 242.0))
    assert fit.cp_w == pytest.approx(218.1, abs=0.5)
    assert fit.w_prime_kj == pytest.approx(17.16, abs=0.05)


def test_two_point_rejects_equal_durations():
    assert fit_two_point((300, 300.0), (300, 250.0)) is None


def test_two_point_rejects_impossible_fit():
    """Esforço longo mais forte que o curto não descreve fisiologia humana."""
    assert fit_two_point((60, 200.0), (720, 300.0)) is None


def test_predict_reproduces_input_points():
    fit = fit_two_point((60, 504.0), (720, 242.0))
    assert fit.predict(60) == pytest.approx(504.0, abs=0.5)
    assert fit.predict(720) == pytest.approx(242.0, abs=0.5)


def test_time_to_exhaustion_above_cp():
    """Com W' de 17,2 kJ, 20 W acima de CP se sustenta por ~14 min."""
    fit = fit_two_point((60, 504.0), (720, 242.0))
    assert fit.time_to_exhaustion(fit.cp_w + 20) == pytest.approx(858, rel=0.05)


def test_time_to_exhaustion_none_at_or_below_cp():
    fit = fit_two_point((60, 504.0), (720, 242.0))
    assert fit.time_to_exhaustion(fit.cp_w) is None
    assert fit.time_to_exhaustion(fit.cp_w - 50) is None


# --- Regressão sobre a curva -----------------------------------------------

def test_curve_fit_recovers_known_parameters():
    curve = _synthetic_curve(240.0, 18000.0, [120, 300, 600, 720, 900, 1200])
    fit = fit_curve(curve)

    assert fit.cp_w == pytest.approx(240.0, abs=1.0)
    assert fit.w_prime_j == pytest.approx(18000.0, rel=0.02)
    assert fit.r_squared > 0.99


def test_curve_fit_ignores_durations_outside_valid_range():
    """Sprints e esforços muito longos não seguem a hipérbole e ficam de fora."""
    curve = _synthetic_curve(240.0, 18000.0, [120, 300, 600, 1200])
    curve[5] = 1200.0        # sprint neuromuscular
    curve[7200] = 150.0      # depleção de glicogênio

    fit = fit_curve(curve)
    assert MAX_VALID_DURATION_S >= max(fit.durations_s)
    assert fit.cp_w == pytest.approx(240.0, abs=1.0)


def test_curve_fit_needs_minimum_points():
    assert fit_curve({300: 300.0, 600: 270.0}) is None


def test_curve_fit_returns_none_for_flat_curve():
    """Potência constante em todas as durações implicaria W' nulo."""
    assert fit_curve({120: 250.0, 300: 250.0, 600: 250.0, 1200: 250.0}) is None


def test_ftp_derived_from_cp():
    fit = fit_two_point((60, 504.0), (720, 242.0))
    assert fit.ftp_w == pytest.approx(fit.cp_w, abs=0.1)
