"""Testes das zonas de potência e frequência cardíaca."""
import numpy as np
import pytest

from analytics.timeseries import ActivitySeries, Segment
from analytics.zones import (
    build_hr_zones,
    build_power_zones,
    time_in_zones,
    zone_distribution,
)


def series(channel: str, values):
    return ActivitySeries(
        "t",
        [Segment(start_time_s=0, channels={channel: np.array(values, dtype=float)})],
    )


# --- Construção das zonas --------------------------------------------------

def test_power_zones_anchored_on_ftp():
    zones = build_power_zones(200.0)
    assert len(zones) == 7
    assert zones[3].name == "Z4"           # limiar
    assert zones[3].low == pytest.approx(180.0)   # 90% do FTP
    assert zones[3].high == pytest.approx(210.0)  # 105% do FTP


def test_top_power_zone_is_open_ended():
    assert build_power_zones(200.0)[-1].high == float("inf")


def test_zones_scale_with_ftp():
    """Mesma potência muda de zona quando o FTP muda — é o ponto de derivar do limiar."""
    low_ftp = build_power_zones(180.0)
    high_ftp = build_power_zones(260.0)
    assert low_ftp[3].low < high_ftp[3].low


def test_hr_zones_anchored_on_threshold():
    zones = build_hr_zones(152.0)
    assert len(zones) == 5
    assert zones[3].name == "Z4"
    assert zones[3].high == pytest.approx(152.0)  # limiar é o topo da Z4


# --- Tempo em zona ---------------------------------------------------------

def test_time_in_zones_counts_seconds():
    """A série é de 1 Hz, logo contar amostras é contar segundos."""
    zones = build_power_zones(200.0)
    result = time_in_zones(series("power", [100.0] * 60), zones)
    assert result["Z1"] == 60


def test_time_in_zones_sums_to_sample_count():
    zones = build_power_zones(200.0)
    values = [float(v) for v in range(0, 400)]
    assert sum(time_in_zones(series("power", values), zones).values()) == 400


def test_time_in_zones_classifies_each_band():
    zones = build_power_zones(200.0)
    # 100 W → Z1, 130 W → Z2, 170 W → Z3, 200 W → Z4, 230 W → Z5
    values = [100.0] * 10 + [130.0] * 10 + [170.0] * 10 + [200.0] * 10 + [230.0] * 10
    result = time_in_zones(series("power", values), zones)
    assert result["Z1"] == 10
    assert result["Z2"] == 10
    assert result["Z3"] == 10
    assert result["Z4"] == 10
    assert result["Z5"] == 10


def test_time_in_zones_ignores_missing_samples():
    """NaN é ausência de medida, não zero — não pode contar como recuperação."""
    zones = build_power_zones(200.0)
    values = [100.0] * 30 + [np.nan] * 30
    assert sum(time_in_zones(series("power", values), zones).values()) == 30


def test_time_in_zones_returns_all_zones_even_when_empty():
    zones = build_power_zones(200.0)
    result = time_in_zones(series("power", [100.0] * 10), zones)
    assert set(result) == {z.name for z in zones}


def test_time_in_hr_zones():
    zones = build_hr_zones(152.0)
    result = time_in_zones(series("hr", [160.0] * 120), zones, channel="hr")
    assert result["Z5"] == 120


# --- Distribuição ----------------------------------------------------------

def test_distribution_percentages_sum_to_100():
    zones = build_power_zones(200.0)
    values = [float(v % 350) for v in range(600)]
    dist = zone_distribution(series("power", values), zones)
    assert sum(d["pct"] for d in dist) == pytest.approx(100.0, abs=0.2)


def test_distribution_reports_open_top_as_none():
    zones = build_power_zones(200.0)
    dist = zone_distribution(series("power", [100.0] * 10), zones)
    assert dist[-1]["high"] is None


def test_distribution_without_data_is_all_zero():
    zones = build_power_zones(200.0)
    dist = zone_distribution(series("power", [np.nan] * 10), zones)
    assert all(d["seconds"] == 0 for d in dist)
