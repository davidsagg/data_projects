"""
Testes do resumo da semana executada.

Dois pontos merecem atenção especial: a semana tem de começar na segunda-feira
(a `TodayView` antiga usava os últimos 7 dias corridos, que não é a mesma coisa
e não é a unidade com que se periodiza), e as zonas de cada atividade têm de ser
as vigentes na data dela — agregar 2023 e 2026 contra o FTP de hoje deslocaria
as sessões antigas de zona.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from analytics.weekly import (
    WeekSummary,
    ZoneBucket,
    build_week_series,
    build_week_summary,
    week_bounds,
)
from storage.catalog_store import CatalogStore
from storage.models import Activity, ActivityStream


@pytest.fixture
def store() -> CatalogStore:
    return CatalogStore.open(":memory:")


@pytest.fixture
def athlete(store: CatalogStore) -> str:
    athlete_id = store.resolve_athlete_id()
    store.conn.execute(
        "INSERT INTO ftp_history (id, athlete_id, effective_from, ftp_w, source) "
        "VALUES (uuid(), ?, DATE '2023-01-01', 250.0, 'manual')",
        [athlete_id],
    )
    return athlete_id


def add_activity(
    store: CatalogStore,
    athlete_id: str,
    day: date,
    tss: float = 80.0,
    distance_m: float = 40000.0,
    power: list[float] | None = None,
) -> str:
    """Grava uma atividade no dia informado, com streams opcionais."""
    activity_id = store.upsert_activity(
        Activity(
            source="fit",
            sport_type="cycling",
            started_at=datetime(day.year, day.month, day.day, 7, tzinfo=timezone.utc),
            elapsed_time_s=3600,
            moving_time_s=3600,
            distance_m=distance_m,
            elevation_gain_m=400.0,
            tss=tss,
        ),
        athlete_id,
    )
    if power:
        store.insert_streams(
            activity_id,
            [ActivityStream(time_s=i, power_w=w) for i, w in enumerate(power)],
        )
    return activity_id


# ---------------------------------------------------------------------------
# Fronteiras da semana
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reference",
    [date(2026, 9, 7), date(2026, 9, 10), date(2026, 9, 13)],
)
def test_week_bounds_always_monday_to_sunday(reference: date):
    start, end = week_bounds(reference)

    assert start == date(2026, 9, 7), "segunda-feira"
    assert end == date(2026, 9, 13), "domingo"
    assert start.weekday() == 0 and end.weekday() == 6


def test_sunday_belongs_to_the_week_that_started_monday():
    """O domingo fecha a semana, não abre a seguinte."""
    assert week_bounds(date(2026, 9, 13))[0] == date(2026, 9, 7)


# ---------------------------------------------------------------------------
# Volume e carga
# ---------------------------------------------------------------------------


def test_sums_volume_of_the_week(store: CatalogStore, athlete: str):
    for offset in range(3):
        add_activity(store, athlete, date(2026, 9, 7) + timedelta(days=offset))

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.session_count == 3
    assert week.total_tss == pytest.approx(240.0)
    assert week.total_km == pytest.approx(120.0)
    assert week.total_hours == pytest.approx(3.0)
    assert week.rest_days == 4


def test_activity_outside_the_week_is_excluded(store: CatalogStore, athlete: str):
    add_activity(store, athlete, date(2026, 9, 6))  # domingo anterior
    add_activity(store, athlete, date(2026, 9, 14))  # segunda seguinte
    add_activity(store, athlete, date(2026, 9, 10))

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.session_count == 1


def test_compares_with_previous_week(store: CatalogStore, athlete: str):
    add_activity(store, athlete, date(2026, 8, 31), tss=100.0)
    add_activity(store, athlete, date(2026, 9, 8), tss=150.0)

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.previous_tss == pytest.approx(100.0)
    assert week.tss_change_pct == pytest.approx(50.0)
    assert week.ramp_is_safe is False, "50% de aumento não é rampa segura"


def test_safe_ramp_is_flagged(store: CatalogStore, athlete: str):
    add_activity(store, athlete, date(2026, 8, 31), tss=100.0)
    add_activity(store, athlete, date(2026, 9, 8), tss=110.0)

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.ramp_is_safe is True


def test_compliance_against_plan(store: CatalogStore, athlete: str):
    from planning.calendar import create_planned_workout

    add_activity(store, athlete, date(2026, 9, 8), tss=80.0)
    create_planned_workout(
        store.conn, athlete, {"date": date(2026, 9, 8), "planned_tss": 100.0}
    )

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.planned_tss == pytest.approx(100.0)
    assert week.compliance_pct == pytest.approx(80.0)


def test_week_without_plan_has_no_compliance(store: CatalogStore, athlete: str):
    add_activity(store, athlete, date(2026, 9, 8))

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.compliance_pct is None


def test_empty_week_is_not_an_error(store: CatalogStore, athlete: str):
    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.session_count == 0
    assert week.total_tss == 0
    assert week.rest_days == 7
    assert week.distribution == "sem dados"


# ---------------------------------------------------------------------------
# Distribuição de intensidade
# ---------------------------------------------------------------------------


def test_polarized_week_is_classified(store: CatalogStore, athlete: str):
    """Muito tempo fácil e um bloco forte, quase nada no limiar."""
    add_activity(store, athlete, date(2026, 9, 8), power=[140.0] * 7200)
    add_activity(store, athlete, date(2026, 9, 10), power=[140.0] * 3600 + [290.0] * 600)

    week = build_week_summary(store, athlete, date(2026, 9, 9))

    assert week.easy.pct > 75
    assert week.hard.seconds > 0
    assert week.distribution == "polarizado"


def test_threshold_heavy_week_is_classified(store: CatalogStore, athlete: str):
    """Muito tempo em Z3/Z4 — o padrão associado a estagnação."""
    add_activity(store, athlete, date(2026, 9, 8), power=[210.0] * 3600)
    add_activity(store, athlete, date(2026, 9, 10), power=[140.0] * 3600)

    week = build_week_summary(store, athlete, date(2026, 9, 9))

    assert week.distribution == "limiar"


def test_base_week_is_classified(store: CatalogStore, athlete: str):
    """Só endurance, sem nada forte."""
    add_activity(store, athlete, date(2026, 9, 8), power=[150.0] * 7200)

    week = build_week_summary(store, athlete, date(2026, 9, 9))

    assert week.distribution == "base"
    assert week.hard.seconds == 0


def test_zones_use_the_ftp_of_each_activity_date(store: CatalogStore, athlete: str):
    """A mesma potência cai em zonas diferentes conforme o FTP da época."""
    store.conn.execute(
        "INSERT INTO ftp_history (id, athlete_id, effective_from, ftp_w, source) "
        "VALUES (uuid(), ?, DATE '2026-09-01', 180.0, 'manual')",
        [athlete],
    )
    # 175 W com FTP 180 dá IF 0,97 — Z4, limiar. Com o FTP antigo de 250 o
    # mesmo esforço seria IF 0,70, ou seja Z2, endurance.
    add_activity(store, athlete, date(2026, 9, 8), power=[175.0] * 3600)

    week = build_week_summary(store, athlete, date(2026, 9, 9))

    assert week.zone_seconds.get("Z4", 0) > 3000
    assert week.zone_seconds.get("Z2", 0) == 0


def test_zones_skipped_when_requested(store: CatalogStore, athlete: str):
    add_activity(store, athlete, date(2026, 9, 8), power=[200.0] * 3600)

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.zone_seconds == {}
    assert week.easy is None


# ---------------------------------------------------------------------------
# Série de semanas
# ---------------------------------------------------------------------------


def test_week_series_is_chronological(store: CatalogStore, athlete: str):
    for offset in range(3):
        add_activity(store, athlete, date(2026, 9, 8) - timedelta(weeks=offset))

    weeks = build_week_series(store, athlete, weeks=3, reference=date(2026, 9, 9))

    assert len(weeks) == 3
    assert [w.week_start for w in weeks] == sorted(w.week_start for w in weeks)
    assert weeks[-1].week_start == date(2026, 9, 7)


def test_serialization_has_the_api_contract(store: CatalogStore, athlete: str):
    add_activity(store, athlete, date(2026, 9, 8), power=[150.0] * 3600)

    payload = build_week_summary(store, athlete, date(2026, 9, 9)).to_dict()

    assert payload["week_start"] == "2026-09-07"
    assert payload["week_end"] == "2026-09-13"
    assert "distribution" in payload
    assert set(payload["intensity"]) == {"easy", "threshold", "hard"}
    assert payload["intensity"]["easy"]["pct"] > 0


def test_zone_bucket_serializes_to_none_when_absent():
    week = WeekSummary(
        week_start=date(2026, 9, 7),
        week_end=date(2026, 9, 13),
        total_tss=0,
        planned_tss=0,
        total_hours=0,
        total_km=0,
        total_elevation_m=0,
        session_count=0,
        rest_days=7,
    )

    assert week.to_dict()["intensity"]["easy"] is None
    assert ZoneBucket(seconds=60, pct=10.0).pct == 10.0


# ---------------------------------------------------------------------------
# Timeline unificada — treino e saúde no mesmo eixo
# ---------------------------------------------------------------------------


def test_days_always_seven_monday_to_sunday(store: CatalogStore, athlete: str):
    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert len(week.days) == 7
    assert [d.weekday for d in week.days] == list(range(7))
    assert week.days[0].date == date(2026, 9, 7)
    assert week.days[-1].date == date(2026, 9, 13)


def test_day_carries_training_and_health_together(store: CatalogStore, athlete: str):
    """O eixo compartilhado é o ponto do componente-assinatura."""
    add_activity(store, athlete, date(2026, 9, 9), tss=120.0)
    store.insert_health_daily(
        athlete, date(2026, 9, 9), hrv_rmssd_ms=62.0, sleep_hours=6.5
    )

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)
    wednesday = week.days[2]

    assert wednesday.tss == pytest.approx(120.0)
    assert wednesday.hrv_rmssd_ms == pytest.approx(62.0)
    assert wednesday.sleep_hours == pytest.approx(6.5)
    assert wednesday.is_rest is False


def test_rest_day_with_health_still_appears(store: CatalogStore, athlete: str):
    """Dia sem treino mas com sono medido não pode sumir da timeline."""
    store.insert_health_daily(athlete, date(2026, 9, 8), sleep_hours=8.1)

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)
    tuesday = week.days[1]

    assert tuesday.is_rest is True
    assert tuesday.tss == 0
    assert tuesday.sleep_hours == pytest.approx(8.1)


def test_training_day_without_health_still_appears(store: CatalogStore, athlete: str):
    """E o inverso: treino sem sincronização do Garmin."""
    add_activity(store, athlete, date(2026, 9, 10), tss=90.0)

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)
    thursday = week.days[3]

    assert thursday.tss == pytest.approx(90.0)
    assert thursday.hrv_rmssd_ms is None
    assert thursday.sleep_hours is None


def test_day_aggregates_multiple_activities(store: CatalogStore, athlete: str):
    """Dia de dois treinos soma a carga, mas conta duas sessões."""
    add_activity(store, athlete, date(2026, 9, 9), tss=60.0, distance_m=20000.0)
    add_activity(store, athlete, date(2026, 9, 9), tss=40.0, distance_m=10000.0)

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.days[2].tss == pytest.approx(100.0)
    assert week.days[2].activity_count == 2
    assert week.days[2].distance_m == pytest.approx(30000.0)


def test_day_carries_planned_load(store: CatalogStore, athlete: str):
    from planning.calendar import create_planned_workout

    create_planned_workout(
        store.conn, athlete, {"date": date(2026, 9, 11), "planned_tss": 140.0}
    )

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.days[4].planned_tss == pytest.approx(140.0)


def test_week_health_averages_ignore_missing_days(store: CatalogStore, athlete: str):
    store.insert_health_daily(athlete, date(2026, 9, 7), sleep_hours=7.0, hrv_rmssd_ms=60.0)
    store.insert_health_daily(athlete, date(2026, 9, 8), sleep_hours=8.0, hrv_rmssd_ms=70.0)

    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.avg_sleep_hours == pytest.approx(7.5)
    assert week.avg_hrv_ms == pytest.approx(65.0)


def test_week_without_health_has_no_averages(store: CatalogStore, athlete: str):
    week = build_week_summary(store, athlete, date(2026, 9, 9), with_zones=False)

    assert week.avg_sleep_hours is None
    assert week.avg_hrv_ms is None
