"""
Testes da detecção automática de intervalos.

O que se exige aqui: achar a estrutura de um treino clássico, não inventar
estrutura num rodízio constante, e nunca deixar um intervalo atravessar uma
pausa — um bloco que começa antes de um semáforo e "termina" depois dele não
existiu.
"""
from __future__ import annotations

import numpy as np
import pytest

from analytics.intervals import (
    Interval,
    detect_intervals,
    group_into_sets,
)
from analytics.timeseries import ActivitySeries, Segment

FTP = 250.0


def series(*power_segments, gap_s: int = 600) -> ActivitySeries:
    """Monta uma ActivitySeries com um segmento contínuo por lista informada."""
    segments = []
    start = 0
    for powers in power_segments:
        values = np.array(powers, dtype=float)
        segments.append(Segment(start_time_s=start, channels={"power": values}))
        start += len(powers) + gap_s
    return ActivitySeries("test", segments)


def workout(reps: int, work_s: int, work_w: float, rest_s: int, rest_w: float) -> list:
    """Gera a série de potência de um treino de intervalos."""
    points: list[float] = [rest_w] * 300
    for _ in range(reps):
        points += [work_w] * work_s + [rest_w] * rest_s
    return points


def test_detects_classic_interval_workout():
    """4 × 4 min a 300 W com 3 min de giro — a estrutura tem de emergir."""
    found = detect_intervals(series(workout(4, 240, 300.0, 180, 150.0)), FTP)

    assert len(found) == 4
    for interval in found:
        assert interval.avg_power_w == pytest.approx(300.0, abs=12)
        assert interval.duration_s == pytest.approx(240, abs=20)


def test_steady_ride_has_no_intervals():
    """Um rodízio constante em Z2 não tem estrutura para achar."""
    assert detect_intervals(series([170.0] * 3600), FTP) == []


def test_effort_below_threshold_is_ignored():
    """Sweet spot logo abaixo do limiar de detecção não vira intervalo."""
    below = FTP * 0.80
    assert detect_intervals(series(workout(3, 300, below, 120, 120.0)), FTP) == []


def test_short_spikes_are_discarded():
    """Ataques de 10 s não são intervalos — são variação de terreno."""
    points: list[float] = []
    for _ in range(10):
        points += [400.0] * 10 + [150.0] * 60
    assert detect_intervals(series(points), FTP) == []


def test_brief_dip_does_not_split_interval():
    """Dois segundos de alívio no meio do bloco não o partem em dois."""
    block = [300.0] * 120 + [200.0] * 3 + [300.0] * 120
    found = detect_intervals(series([150.0] * 120 + block + [150.0] * 120), FTP)

    assert len(found) == 1
    assert found[0].duration_s > 230


def test_interval_never_crosses_a_pause():
    """Cada segmento é analisado por conta própria."""
    hard = [300.0] * 120
    found = detect_intervals(series([150.0] * 60 + hard, hard + [150.0] * 60), FTP)

    assert len(found) == 2
    assert all(i.duration_s <= 125 for i in found)


def test_interval_positions_are_absolute():
    """`start_s` é relativo ao início da atividade, não ao segmento."""
    found = detect_intervals(
        series([150.0] * 60 + [300.0] * 120, [150.0] * 60 + [300.0] * 120), FTP
    )

    assert len(found) == 2
    assert found[0].start_s < found[1].start_s
    assert found[1].start_s > 600, "o segundo bloco está depois da pausa"


def test_recovery_between_intervals_is_measured():
    found = detect_intervals(series(workout(3, 240, 300.0, 180, 120.0)), FTP)

    assert found[0].recovery_s == pytest.approx(180, abs=25)
    assert found[0].recovery_power_w == pytest.approx(120.0, abs=20)
    assert found[-1].recovery_s is None, "o último bloco não tem recuperação depois"


def test_no_ftp_yields_nothing():
    """Sem FTP não há limiar de referência — melhor não adivinhar."""
    assert detect_intervals(series(workout(4, 240, 300.0, 180, 150.0)), None) == []


def test_intensity_factor_of_interval():
    interval = Interval(start_s=0, duration_s=240, avg_power_w=275.0, max_power_w=310.0)

    assert interval.intensity_factor(250.0) == 1.1
    assert interval.intensity_factor(None) is None
    assert interval.end_s == 240


# ---------------------------------------------------------------------------
# Agrupamento em séries
# ---------------------------------------------------------------------------


def test_similar_intervals_form_one_set():
    found = detect_intervals(series(workout(5, 180, 290.0, 120, 140.0)), FTP)
    sets = group_into_sets(found)

    assert len(sets) == 1
    assert sets[0].count == 5


def test_different_blocks_form_separate_sets():
    """Um treino misto: 3 × 5 min de limiar e depois 5 × 1 min de VO2."""
    points = workout(3, 300, 280.0, 180, 140.0) + workout(5, 60, 380.0, 120, 140.0)
    sets = group_into_sets(detect_intervals(series(points), FTP))

    assert len(sets) == 2
    assert sets[0].count == 3
    assert sets[1].count == 5
    assert sets[0].avg_duration_s > sets[1].avg_duration_s
    assert sets[1].avg_power_w > sets[0].avg_power_w


def test_set_label_reads_like_a_workout():
    sets = group_into_sets(detect_intervals(series(workout(4, 240, 300.0, 180, 150.0)), FTP))

    label = sets[0].label(FTP)
    assert label.startswith("4 × 4min @ ")
    assert "IF 1,2" in label


def test_empty_input_groups_to_nothing():
    assert group_into_sets([]) == []
