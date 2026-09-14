"""
Testes da análise de durabilidade.

O ponto central: a métrica só pode falar quando houve trabalho suficiente dos
dois lados do corte. Um resultado "excelente" vindo de um pedal de 20 minutos
seria pior que resultado nenhum, porque parece informação.
"""
from __future__ import annotations

import numpy as np
import pytest

from analytics.durability import (
    DEFAULT_KJ_THRESHOLD,
    DurabilityPoint,
    compute_durability,
    cumulative_work_kj,
)
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


def ride(power: float, seconds: int, hr: float | None = None) -> dict:
    """Trecho de pedal com potência (e opcionalmente FC) constantes."""
    block = {"power": [power] * seconds}
    if hr is not None:
        block["hr"] = [hr] * seconds
    return block


# ---------------------------------------------------------------------------
# Trabalho acumulado
# ---------------------------------------------------------------------------


def test_cumulative_work_matches_power_times_time():
    """200 W por 1.000 s são 200 kJ."""
    work = cumulative_work_kj(series(ride(200.0, 1000)))

    assert work[-1] == pytest.approx(200.0, abs=0.5)


def test_pause_does_not_accumulate_work():
    """Parar no café não acumula quilojoule, mas o total carrega entre trechos."""
    work = cumulative_work_kj(series(ride(200.0, 1000), ride(200.0, 1000)))

    assert work[-1] == pytest.approx(400.0, abs=1.0)
    assert work.size == 2000, "as amostras da pausa não entram na série"


def test_no_power_yields_empty_work():
    empty = ActivitySeries("test", [Segment(start_time_s=0, channels={"hr": np.array([130.0])})])

    assert cumulative_work_kj(empty).size == 0


# ---------------------------------------------------------------------------
# Durabilidade
# ---------------------------------------------------------------------------


def test_short_ride_is_inconclusive():
    """Sem atingir o limiar de kJ não há o que comparar."""
    result = compute_durability(series(ride(200.0, 1200)))

    assert not result.is_conclusive
    assert result.split_time_s is None
    assert result.verdict == "inconclusivo"


def test_split_happens_at_kj_threshold():
    """A 250 W, os 1.000 kJ chegam aos 4.000 s."""
    result = compute_durability(series(ride(250.0, 9000)))

    assert result.split_time_s == pytest.approx(4000, abs=5)
    assert result.total_kj == pytest.approx(2250.0, abs=5)


def test_fading_rider_shows_power_decline():
    """Quem cai de 300 W para 240 W ao cruzar o corte tem durabilidade baixa.

    A 300 W os 1.000 kJ chegam aos 3.333 s, então a queda é posta exatamente
    ali — se viesse depois, o trecho forte remanescente entraria na janela
    "depois" e mascararia o declínio.
    """
    result = compute_durability(
        series({"power": [300.0] * 3333 + [240.0] * 3000})
    )

    assert result.is_conclusive
    declines = [p.change_pct for p in result.points]
    assert declines and all(d < -15 for d in declines)
    assert result.verdict == "baixa"


def test_decline_after_the_split_only_shows_in_long_efforts():
    """Se a queda vem bem depois do corte, sobra trecho forte na janela "depois".

    É o comportamento correto: a janela curta ainda encontra os watts altos que
    precederam a queda, e só o esforço longo o bastante para abranger os dois
    regimes acusa o declínio. Documentado porque parece bug e não é.
    """
    result = compute_durability(
        series({"power": [300.0] * 4000 + [240.0] * 3000})
    )

    by_duration = {p.duration_s: p.change_pct for p in result.points}
    assert by_duration[60] == pytest.approx(0.0, abs=0.5)
    assert by_duration[1200] < -5


def test_steady_rider_shows_no_decline():
    """Potência constante dos dois lados é durabilidade excelente."""
    result = compute_durability(series(ride(250.0, 9000)))

    assert result.is_conclusive
    assert all(p.change_pct == pytest.approx(0.0, abs=1.0) for p in result.points)
    assert result.verdict == "excelente"


def test_efficiency_factor_captures_cardiac_drift():
    """Mesma potência com FC subindo: o EF cai, mesmo sem queda de watts."""
    before = {"power": [250.0] * 4000, "hr": [140.0] * 4000}
    after = {"power": [250.0] * 3000, "hr": [160.0] * 3000}
    result = compute_durability(
        series({"power": before["power"] + after["power"], "hr": before["hr"] + after["hr"]})
    )

    assert result.ef_before is not None and result.ef_after is not None
    assert result.ef_after < result.ef_before
    assert result.ef_change_pct == pytest.approx(-12.5, abs=1.0)


def test_no_heart_rate_leaves_efficiency_empty():
    result = compute_durability(series(ride(250.0, 9000)))

    assert result.ef_before is None
    assert result.ef_change_pct is None


def test_custom_threshold_moves_the_split():
    low = compute_durability(series(ride(250.0, 9000)), kj_threshold=500.0)
    high = compute_durability(series(ride(250.0, 9000)), kj_threshold=1500.0)

    assert low.split_time_s < high.split_time_s


def test_threshold_reached_too_late_is_inconclusive():
    """Cruzar o limiar nos últimos minutos não deixa amostra do outro lado."""
    result = compute_durability(series(ride(250.0, 4100)), kj_threshold=DEFAULT_KJ_THRESHOLD)

    assert not result.is_conclusive


def test_durability_point_change_pct():
    assert DurabilityPoint(300, 300.0, 270.0).change_pct == -10.0
    assert DurabilityPoint(300, 0.0, 270.0).change_pct == 0.0
