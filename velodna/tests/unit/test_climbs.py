"""
Testes da detecção de subidas.

Dois riscos guiam estes testes: fragmentar uma subida real em pedaços (qualquer
ondulação encerraria a subida sem histerese) e atravessar uma pausa, o que
transformaria uma parada para foto numa subida de duas horas com VAM absurdo.
"""
from __future__ import annotations

import numpy as np
import pytest

from analytics.climbs import Climb, detect_climbs, summarize_climbs
from analytics.timeseries import ActivitySeries, Segment


def series(*segments_data, gap_s: int = 600) -> ActivitySeries:
    """Monta uma ActivitySeries; cada argumento é um dict {canal: lista}."""
    segments = []
    start = 0
    for channels in segments_data:
        arrays = {k: np.array(v, dtype=float) for k, v in channels.items()}
        segments.append(Segment(start_time_s=start, channels=arrays))
        start += len(next(iter(arrays.values()))) + gap_s
    return ActivitySeries("test", segments)


def ramp(seconds: int, gain_m: float, distance_m: float, start_alt: float = 0.0,
         start_dist: float = 0.0) -> dict:
    """Trecho de inclinação constante."""
    return {
        "altitude": list(np.linspace(start_alt, start_alt + gain_m, seconds)),
        "distance": list(np.linspace(start_dist, start_dist + distance_m, seconds)),
    }


def join(*blocks: dict) -> dict:
    """Concatena trechos num único segmento contínuo."""
    out: dict[str, list] = {}
    for block in blocks:
        for key, values in block.items():
            out.setdefault(key, []).extend(values)
    return out


# ---------------------------------------------------------------------------
# Detecção
# ---------------------------------------------------------------------------


def test_detects_a_single_sustained_climb():
    """600 s subindo 120 m em 2 km → 6% de inclinação, VAM 720 m/h."""
    climbs = detect_climbs(series(ramp(600, 120, 2000)))

    assert len(climbs) == 1
    climb = climbs[0]
    assert climb.elevation_gain_m == pytest.approx(120, abs=6)
    assert climb.avg_gradient_pct == pytest.approx(6.0, abs=0.5)
    assert climb.vam_mh == pytest.approx(720, abs=40)


def test_flat_ride_has_no_climbs():
    flat = {"altitude": [100.0] * 1800, "distance": list(np.linspace(0, 30000, 1800))}

    assert detect_climbs(series(flat)) == []


def test_false_flat_is_not_a_climb():
    """40 m em 5 km é 0,8% — não é subida, é falso plano."""
    assert detect_climbs(series(ramp(900, 40, 5000))) == []


def test_short_gain_is_ignored():
    """Ganho abaixo do mínimo é ondulação, não subida."""
    assert detect_climbs(series(ramp(120, 15, 300))) == []


def test_brief_dip_does_not_split_the_climb():
    """Nenhuma subida real é monotônica — a histerese tem de segurar."""
    profile = join(
        ramp(300, 60, 1000),
        ramp(40, -6, 150, start_alt=60, start_dist=1000),   # respiro curto
        ramp(300, 60, 1000, start_alt=54, start_dist=1150),
    )

    climbs = detect_climbs(series(profile))

    assert len(climbs) == 1, "a descida curta não pode partir a subida"
    assert climbs[0].elevation_gain_m > 100


def test_real_descent_separates_two_climbs():
    """Uma descida de verdade encerra a subida."""
    profile = join(
        ramp(300, 70, 1200),
        ramp(300, -70, 1500, start_alt=70, start_dist=1200),
        ramp(300, 70, 1200, start_alt=0, start_dist=2700),
    )

    climbs = detect_climbs(series(profile))

    assert len(climbs) == 2


def test_climb_never_crosses_a_pause():
    """Parar no meio da subida não pode virar uma subida gigante."""
    climbs = detect_climbs(
        series(ramp(400, 80, 1300), ramp(400, 80, 1300))
    )

    assert len(climbs) == 2
    assert all(c.duration_s <= 405 for c in climbs)


def test_positions_are_absolute():
    climbs = detect_climbs(series(ramp(400, 80, 1300), ramp(400, 80, 1300)))

    assert climbs[1].start_s > 600, "o segundo trecho está depois da pausa"


def test_power_and_hr_are_averaged_over_the_climb():
    profile = ramp(400, 80, 1300)
    profile["power"] = [210.0] * 400
    profile["hr"] = [158.0] * 400

    climb = detect_climbs(series(profile))[0]

    assert climb.avg_power_w == pytest.approx(210, abs=1)
    assert climb.avg_hr_bpm == pytest.approx(158, abs=1)


def test_missing_altitude_yields_nothing():
    assert detect_climbs(series({"power": [200.0] * 600})) == []


def test_missing_distance_yields_nothing():
    """Sem distância não há inclinação, e sem inclinação não há classificação."""
    assert detect_climbs(series({"altitude": list(np.linspace(0, 100, 600))})) == []


# ---------------------------------------------------------------------------
# Métricas derivadas
# ---------------------------------------------------------------------------


def test_vam_is_gain_over_hours():
    """300 m em 30 min = 600 m/h."""
    climb = Climb(0, 1800, 6000, 300, 5.0, 8.0, 600.0)

    assert climb.vam_mh == 600.0


def test_watts_per_kg():
    climb = Climb(0, 1800, 6000, 300, 5.0, 8.0, 600.0, avg_power_w=213.0)

    assert climb.watts_per_kg(71) == pytest.approx(3.0, abs=0.01)
    assert climb.watts_per_kg(None) is None


@pytest.mark.parametrize(
    ("gain", "gradient", "expected"),
    [(1000, 8.0, "HC"), (800, 8.0, "1"), (500, 7.0, "2"),
     (300, 6.0, "3"), (200, 5.0, "4"), (40, 4.0, "sem categoria")],
)
def test_category_from_gain_and_gradient(gain, gradient, expected):
    assert Climb(0, 1800, 6000, gain, gradient, gradient, 600.0).category() == expected


def test_summary_aggregates_the_set():
    profile = join(
        ramp(300, 70, 1200),
        ramp(300, -70, 1500, start_alt=70, start_dist=1200),
        ramp(600, 90, 1400, start_alt=0, start_dist=2700),
    )

    summary = summarize_climbs(detect_climbs(series(profile)))

    assert summary["count"] == 2
    assert summary["total_gain_m"] > 150
    assert summary["best_vam_mh"] is not None


def test_summary_of_nothing_is_not_an_error():
    summary = summarize_climbs([])

    assert summary["count"] == 0
    assert summary["best_vam_mh"] is None


# ---------------------------------------------------------------------------
# Artefatos
# ---------------------------------------------------------------------------


def test_high_starting_altitude_does_not_create_a_phantom_climb():
    """O bug que passou despercebido até um pedal real acusar 100% de inclinação.

    `np.convolve(mode="same")` completa as pontas com zeros. Numa série que
    começa a 722 m, isso fabricava uma rampa de 0 a 722 m nos primeiros
    segundos — lida como uma subida de 384 m a 100%. O padding tem de ser de
    borda, repetindo o valor real do terreno.
    """
    flat_high = {
        "altitude": [722.0] * 1200,
        "distance": list(np.linspace(0, 20000, 1200)),
    }

    assert detect_climbs(series(flat_high)) == [], "planalto alto não é subida"


def test_total_climb_gain_stays_within_the_activity():
    """A soma das subidas não pode exceder o ganho real do terreno."""
    profile = join(
        ramp(600, 200, 4000, start_alt=700),
        ramp(600, -200, 5000, start_alt=900, start_dist=4000),
        ramp(600, 200, 4000, start_alt=700, start_dist=9000),
    )

    summary = summarize_climbs(detect_climbs(series(profile)))

    assert summary["total_gain_m"] <= 420, "sem ganho fantasma das bordas"


def test_implausible_gradient_is_rejected():
    """Acima de 25% sustentado é artefato de barômetro, não subida pedalável."""
    absurd = {
        "altitude": list(np.linspace(700, 900, 300)),
        "distance": list(np.linspace(0, 400, 300)),  # 200 m em 400 m → 50%
    }

    assert detect_climbs(series(absurd)) == []
