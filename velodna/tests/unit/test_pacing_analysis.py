"""
Testes da análise de execução e da densidade de carga.

O veredito de pacing é o que mais importa acertar: dizer "saiu forte demais"
para quem executou regular é pior que não dizer nada, porque o atleta mudaria a
estratégia da próxima prova com base num erro.
"""
from __future__ import annotations

import numpy as np
import pytest

from analytics.pacing_analysis import analyze_pacing, load_density
from analytics.timeseries import ActivitySeries, Segment
from analytics.zones import build_power_zones

FTP = 250.0
ZONES = build_power_zones(FTP)


def series(**channels) -> ActivitySeries:
    arrays = {k: np.array(v, dtype=float) for k, v in channels.items()}
    return ActivitySeries("test", [Segment(start_time_s=0, channels=arrays)])


# ---------------------------------------------------------------------------
# Execução por quartos
# ---------------------------------------------------------------------------


def test_even_effort_is_regular():
    result = analyze_pacing(series(power=[200.0] * 2400), ZONES)

    assert len(result["quarters"]) == 4
    assert result["verdict"] == "execução regular"


def test_starting_too_hard_is_detected():
    """Sai em Z5 e termina em Z1 — o erro clássico de prova."""
    power = [300.0] * 600 + [250.0] * 600 + [190.0] * 600 + [120.0] * 600

    result = analyze_pacing(series(power=power), ZONES)

    assert result["verdict"] == "saiu forte demais"


def test_negative_split_is_detected():
    power = [120.0] * 600 + [190.0] * 600 + [250.0] * 600 + [300.0] * 600

    result = analyze_pacing(series(power=power), ZONES)

    assert result["verdict"] == "negative split"


def test_quarters_cover_the_whole_effort():
    """Nenhum segundo pode sumir no corte."""
    result = analyze_pacing(series(power=[200.0] * 2401), ZONES)

    assert sum(q["duration_s"] for q in result["quarters"]) == 2401


def test_quarter_carries_zone_distribution_and_averages():
    result = analyze_pacing(series(power=[200.0] * 2400, hr=[150.0] * 2400), ZONES)
    first = result["quarters"][0]

    assert first["avg_power_w"] == pytest.approx(200, abs=1)
    assert first["avg_hr_bpm"] == pytest.approx(150, abs=1)
    assert sum(first["zone_pct"].values()) == pytest.approx(100, abs=0.5)


def test_short_effort_is_not_analyzed():
    result = analyze_pacing(series(power=[200.0] * 100), ZONES)

    assert result["quarters"] == []
    assert "curto" in result["verdict"]


def test_cardiac_drift_between_first_and_last_quarter():
    """Mesma potência com FC subindo: o custo por watt aumentou."""
    power = [200.0] * 2400
    hr = [140.0] * 1200 + [160.0] * 1200

    result = analyze_pacing(series(power=power, hr=hr), ZONES)

    assert result["decoupling_first_to_last"] < 0


def test_drift_is_none_without_heart_rate():
    result = analyze_pacing(series(power=[200.0] * 2400), ZONES)

    assert result["decoupling_first_to_last"] is None


# ---------------------------------------------------------------------------
# Densidade carga interna × externa
# ---------------------------------------------------------------------------


def test_density_bins_power_and_hr():
    result = load_density(series(power=[205.0] * 600, hr=[152.0] * 600))

    assert len(result["cells"]) == 1
    cell = result["cells"][0]
    assert cell["power_w"] == 200 and cell["hr_bpm"] == 150
    assert cell["seconds"] == 600


def test_density_separates_distinct_efforts():
    result = load_density(
        series(power=[120.0] * 600 + [280.0] * 600, hr=[120.0] * 600 + [170.0] * 600)
    )

    assert len(result["cells"]) == 2
    assert result["total_seconds"] == 1200


def test_density_needs_both_channels():
    assert load_density(series(power=[200.0] * 600))["cells"] == []
    assert load_density(series(hr=[150.0] * 600))["cells"] == []


def test_density_ignores_points_missing_one_channel():
    """Ponto sem FC não diz nada sobre custo — não pode entrar na nuvem."""
    result = load_density(
        series(power=[200.0] * 600, hr=[150.0] * 300 + [np.nan] * 300)
    )

    assert result["total_seconds"] == 300


def test_density_reports_axis_ranges():
    result = load_density(
        series(power=[100.0] * 300 + [300.0] * 300, hr=[110.0] * 300 + [170.0] * 300)
    )

    assert result["power_range"][0] <= 100
    assert result["power_range"][1] >= 300
    assert result["hr_range"][0] <= 110
