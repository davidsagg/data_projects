"""
Testes de tradução do payload do Garmin Connect.

O construtor faz login de verdade, então os testes exercitam `_build_health_daily`
diretamente — é onde estava o defeito: o cliente lia o HRV num caminho que a API
não usa mais, e ignorava metade dos campos disponíveis.
"""
from datetime import date

import pytest

from ingestion.garmin_health_client import GarminHealthClient, HealthDaily

TODAY = date(2026, 7, 23)


def build(sleep=None, hrv=None, stats=None) -> HealthDaily:
    return GarminHealthClient._build_health_daily(
        TODAY, sleep or {}, hrv or {}, stats or {}
    )


# --- HRV: o campo que estava sendo lido do lugar errado --------------------

def test_reads_hrv_from_current_api_shape():
    """A API atual entrega o HRV em `hrvSummary.lastNightAvg`."""
    daily = build(hrv={"hrvSummary": {"lastNightAvg": 33, "status": "UNBALANCED"}})
    assert daily.hrv_rmssd_ms == pytest.approx(33.0)
    assert daily.hrv_status == "UNBALANCED"


def test_still_reads_legacy_hrv_shape():
    """Versões antigas usavam `lastNight.rmssd`; aceitar as duas evita quebra."""
    daily = build(hrv={"lastNight": {"rmssd": 41, "status": "BALANCED"}})
    assert daily.hrv_rmssd_ms == pytest.approx(41.0)


def test_hrv_absent_is_none_not_zero():
    assert build().hrv_rmssd_ms is None


# --- Campos que antes eram sempre nulos ------------------------------------

def test_reads_resting_hr_and_stress():
    daily = build(stats={"restingHeartRate": 53, "averageStressLevel": 31})
    assert daily.resting_hr_bpm == 53
    assert daily.stress_avg == 31


def test_reads_body_battery_range():
    daily = build(
        stats={"bodyBatteryHighestValue": 69, "bodyBatteryLowestValue": 19}
    )
    assert daily.body_battery_max == 69
    assert daily.body_battery_min == 19


def test_reads_steps_and_vo2max():
    daily = build(stats={"totalSteps": 6546, "vo2MaxValue": 47.0})
    assert daily.steps == 6546
    assert daily.vo2max_estimated == pytest.approx(47.0)


def test_converts_weight_from_grams():
    """O Garmin devolve peso em gramas."""
    assert build(stats={"weight": 71200}).weight_kg == pytest.approx(71.2)


# --- Sono ------------------------------------------------------------------

def test_converts_sleep_seconds_to_hours():
    daily = build(
        sleep={
            "dailySleepDTO": {
                "sleepTimeSeconds": 25200,
                "deepSleepSeconds": 3600,
                "remSleepSeconds": 5400,
                "sleepScores": {"overall": {"value": 78}},
            }
        }
    )
    assert daily.sleep_duration_h == pytest.approx(7.0)
    assert daily.deep_sleep_min == 60
    assert daily.rem_sleep_min == 90
    assert daily.sleep_score == 78


def test_falls_back_to_stats_when_sleep_detail_missing():
    """Dias sem detalhe de sono ainda têm `sleepingSeconds` em stats."""
    daily = build(stats={"sleepingSeconds": 23972})
    assert daily.sleep_duration_h == pytest.approx(6.66, abs=0.01)


def test_zero_sleep_is_none_not_zero():
    daily = build(sleep={"dailySleepDTO": {"sleepTimeSeconds": 0}})
    assert daily.sleep_duration_h is None


# --- Dias vazios -----------------------------------------------------------

def test_empty_payloads_produce_empty_day():
    assert build().is_empty


def test_day_with_any_metric_is_not_empty():
    assert not build(stats={"restingHeartRate": 53}).is_empty


def test_malformed_payload_does_not_raise():
    """Campos nulos aparecem em dias parciais e não podem derrubar o backfill."""
    daily = build(
        sleep={"dailySleepDTO": None},
        hrv={"hrvSummary": None},
        stats={"restingHeartRate": None},
    )
    assert daily.is_empty


# ---------------------------------------------------------------------------
# Pesagens (composição corporal)
# ---------------------------------------------------------------------------


def test_weigh_ins_parsed_from_body_composition():
    from datetime import date

    from ingestion.garmin_health_client import parse_weigh_ins

    payload = {
        "dateWeightList": [
            {"calendarDate": "2026-01-28", "weight": 73400.0, "date": 2},
            {"calendarDate": "2026-01-24", "weight": 73000.0, "date": 1},
        ]
    }
    assert parse_weigh_ins(payload) == {
        date(2026, 1, 28): 73.4,
        date(2026, 1, 24): 73.0,
    }


def test_latest_weigh_in_of_the_day_wins():
    from datetime import date

    from ingestion.garmin_health_client import parse_weigh_ins

    payload = {
        "dateWeightList": [
            {"calendarDate": "2026-09-30", "weight": 73500.0, "date": 200},
            {"calendarDate": "2026-09-30", "weight": 72900.0, "date": 100},
        ]
    }
    assert parse_weigh_ins(payload) == {date(2026, 9, 30): 73.5}


def test_weigh_ins_tolerate_empty_payload():
    from ingestion.garmin_health_client import parse_weigh_ins

    assert parse_weigh_ins({}) == {}
    assert parse_weigh_ins({"dateWeightList": None}) == {}
