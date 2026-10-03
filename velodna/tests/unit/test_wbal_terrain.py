"""
Testes do W'bal sobre o terreno.

O que mais importa: o ponto de W'bal tem de cair no segundo e no quilômetro
certos mesmo com pausas, e o fundo de cada mergulho não pode sumir na
decimação — é exatamente o momento em que o gás acabou.
"""
from __future__ import annotations

import numpy as np
import pytest

from analytics.timeseries import ActivitySeries, Segment
from analytics.wbal_terrain import (
    aligned_channels,
    decimate_keep_minimum,
    depletion_episodes,
    terrain_points,
)
from analytics.wprime_model import WPrimeModel

CP = 200.0
W_PRIME = 15000.0


def segment(start_s: int, power, altitude=None, speed_ms: float = 8.0, km0: float = 0.0):
    n = len(power)
    return Segment(
        start_time_s=start_s,
        channels={
            "power": np.asarray(power, dtype=float),
            "altitude": np.asarray(altitude if altitude is not None else [700.0] * n, dtype=float),
            "distance": km0 * 1000 + np.arange(n) * speed_ms,
        },
    )


def balance_of(series: ActivitySeries) -> list[float]:
    return WPrimeModel(W_PRIME, CP).compute(series).balance_j


def test_time_axis_keeps_the_pause():
    """Sem o tempo real, o segundo segmento seria desenhado colado no primeiro."""
    series = ActivitySeries("a", [segment(0, [150] * 60), segment(600, [150] * 60, km0=5)])
    channels = aligned_channels(series)

    assert channels["time_s"][59] == 59
    assert channels["time_s"][60] == 600
    assert len(channels["time_s"]) == len(balance_of(series))


def test_decimation_keeps_the_bottom_of_a_short_dip():
    balance = [15000.0] * 1000
    balance[537] = 1200.0  # mergulho de um segundo
    kept = decimate_keep_minimum(balance, 50)

    assert 537 in kept
    assert len(kept) == 50


def test_climb_that_empties_the_tank_is_one_episode_on_a_climb():
    # 10 min de base, 4 min a 330 W subindo 6% (8 m/s → 0,48 m/s de ganho), recuperação.
    base, climb, easy = 600, 240, 600
    power = [150] * base + [330] * climb + [120] * easy
    altitude = [700.0] * base + list(700 + np.arange(climb) * 0.48) + [815.0] * easy
    series = ActivitySeries("a", [segment(0, power, altitude)])

    episodes = depletion_episodes(balance_of(series), aligned_channels(series), W_PRIME)

    assert len(episodes) == 1
    episode = episodes[0]
    assert episode.terrain == "subida"
    # O ganho vai do pé da rampa até o fundo do W', não até o topo.
    assert episode.lead_gain_m == pytest.approx((episode.min_s - base) * 0.48, abs=2)
    assert episode.lead_grade_pct == pytest.approx(6.0, abs=0.3)
    assert base < episode.start_s < base + climb
    assert episode.start_km == pytest.approx(episode.start_s * 8 / 1000, abs=0.01)
    assert episode.min_pct < 25
    assert episode.avg_power_w > CP


def test_flat_effort_is_labelled_flat():
    power = [150] * 300 + [330] * 240 + [120] * 300
    series = ActivitySeries("a", [segment(0, power)])

    [episode] = depletion_episodes(balance_of(series), aligned_channels(series), W_PRIME)

    assert episode.terrain == "plano"


def test_tank_never_low_means_no_episode():
    series = ActivitySeries("a", [segment(0, [150] * 600 + [260] * 60 + [150] * 300)])

    assert depletion_episodes(balance_of(series), aligned_channels(series), W_PRIME) == []


def test_two_dips_close_together_are_merged():
    power = [150] * 300 + [360] * 120 + [210] * 15 + [360] * 60 + [120] * 300
    series = ActivitySeries("a", [segment(0, power)])

    episodes = depletion_episodes(balance_of(series), aligned_channels(series), W_PRIME)

    assert len(episodes) == 1


def test_points_carry_time_distance_and_altitude():
    series = ActivitySeries("a", [segment(0, [150] * 100), segment(400, [150] * 100, km0=2)])
    points = terrain_points(balance_of(series), aligned_channels(series), 900)

    assert points[100]["t"] == 400
    assert points[100]["km"] == pytest.approx(2.0)
    assert points[0]["alt"] == 700.0
    assert set(points[0]) == {"t", "km", "alt", "kj", "w"}


def test_missing_altitude_does_not_break():
    n = 900
    seg = Segment(
        start_time_s=0,
        channels={
            "power": np.asarray([150] * 300 + [340] * 300 + [120] * 300, dtype=float),
            "altitude": np.full(n, np.nan),
            "distance": np.arange(n) * 8.0,
        },
    )
    series = ActivitySeries("a", [seg])

    [episode] = depletion_episodes(balance_of(series), aligned_channels(series), W_PRIME)
    assert episode.terrain == "sem altitude"
    assert terrain_points(balance_of(series), aligned_channels(series), 50)[0]["alt"] is None
