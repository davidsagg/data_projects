"""Testes de projeção de carga e calendário de treino."""
import duckdb
import pytest
from datetime import date, datetime, time, timedelta

from planning.calendar import build_calendar, create_planned_workout, reconcile
from planning.projection import (
    SAFE_RAMP_RATE_PER_WEEK,
    build_flat_plan,
    project,
    ramp_rate_per_week,
    required_daily_tss,
    summarize,
)
from storage.catalog_store import CatalogStore
from storage.models import Activity

ATHLETE_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    CatalogStore(conn).initialize_schema()
    conn.execute("INSERT INTO athletes (id, name) VALUES (?, ?)", [ATHLETE_ID, "T"])
    yield conn
    conn.close()


def _add_activity(conn, when: date, tss: float):
    """Cria uma atividade no meio do dia.

    O horário importa: `started_at` é TIMESTAMPTZ e o calendário agrupa pela
    data local. Uma atividade à meia-noite UTC cairia no dia anterior em
    qualquer fuso a oeste de Greenwich, o que mascararia o comportamento real.
    """
    return CatalogStore(conn).upsert_activity(
        Activity(
            source="fit",
            sport_type="cycling",
            started_at=datetime.combine(when, time(12, 0)).astimezone(),
            elapsed_time_s=3600,
            tss=tss,
        ),
        ATHLETE_ID,
    )


# --- Projeção --------------------------------------------------------------

def test_constant_load_converges_to_daily_tss():
    """Com TSS constante por tempo suficiente, o CTL tende ao próprio TSS diário."""
    plan = {date(2026, 1, 1) + timedelta(days=i): 100.0 for i in range(365)}
    projection = project(0.0, 0.0, plan)
    assert projection[-1].ctl == pytest.approx(100.0, abs=1.0)


def test_rest_period_decays_ctl():
    plan = {date(2026, 1, 1) + timedelta(days=i): 0.0 for i in range(42)}
    projection = project(80.0, 80.0, plan)
    assert projection[-1].ctl < 80.0 * 0.5


def test_atl_falls_faster_than_ctl_during_rest():
    """É o que produz o pico de forma no taper: fadiga some antes do fitness."""
    plan = {date(2026, 1, 1) + timedelta(days=i): 0.0 for i in range(14)}
    projection = project(80.0, 80.0, plan)
    assert projection[-1].atl < projection[-1].ctl


def test_taper_produces_positive_tsb():
    plan = {date(2026, 1, 1) + timedelta(days=i): 20.0 for i in range(14)}
    projection = project(80.0, 90.0, plan)
    assert projection[-1].tsb > 0


def test_projection_is_empty_for_empty_plan():
    assert project(50.0, 50.0, {}) == []


# --- TSS necessário --------------------------------------------------------

def test_required_tss_reaches_target():
    """O TSS calculado tem de levar exatamente ao CTL alvo no prazo."""
    start_ctl, target, days = 50.0, 80.0, 56
    daily = required_daily_tss(start_ctl, target, days)

    plan = {date(2026, 1, 1) + timedelta(days=i): daily for i in range(days)}
    projection = project(start_ctl, start_ctl, plan)
    assert projection[-1].ctl == pytest.approx(target, abs=0.5)


def test_required_tss_is_lower_for_longer_deadline():
    assert required_daily_tss(50.0, 80.0, 90) < required_daily_tss(50.0, 80.0, 30)


def test_required_tss_none_for_zero_days():
    assert required_daily_tss(50.0, 80.0, 0) is None


def test_required_tss_none_when_target_needs_negative_load():
    """Alvo muito abaixo do CTL atual não se atinge treinando — só descansando."""
    assert required_daily_tss(100.0, 5.0, 7) is None


# --- Distribuição do plano -------------------------------------------------

def test_flat_plan_respects_rest_days():
    plan = build_flat_plan(date(2026, 1, 5), 7, 600.0, rest_days={0})  # segunda
    assert plan[date(2026, 1, 5)] == 0.0            # segunda
    assert plan[date(2026, 1, 6)] == pytest.approx(100.0)  # 600 / 6 dias


def test_flat_plan_totals_weekly_tss():
    plan = build_flat_plan(date(2026, 1, 5), 7, 700.0)
    assert sum(plan.values()) == pytest.approx(700.0)


def test_flat_plan_with_all_rest_days_is_zero():
    plan = build_flat_plan(date(2026, 1, 5), 7, 700.0, rest_days=set(range(7)))
    assert sum(plan.values()) == 0.0


# --- Rampa e resumo --------------------------------------------------------

def test_ramp_rate_detects_aggressive_progression():
    plan = {date(2026, 1, 1) + timedelta(days=i): 200.0 for i in range(28)}
    projection = project(30.0, 30.0, plan)
    assert ramp_rate_per_week(projection) > SAFE_RAMP_RATE_PER_WEEK


def test_summary_flags_unsafe_ramp():
    plan = {date(2026, 1, 1) + timedelta(days=i): 250.0 for i in range(28)}
    summary = summarize(project(20.0, 20.0, plan))
    assert summary["ramp_exceeds_safe_limit"] is True


def test_summary_accepts_moderate_ramp():
    plan = {date(2026, 1, 1) + timedelta(days=i): 60.0 for i in range(28)}
    summary = summarize(project(50.0, 50.0, plan))
    assert summary["ramp_exceeds_safe_limit"] is False


# --- Calendário ------------------------------------------------------------

def test_calendar_marks_unplanned_activity(db):
    _add_activity(db, date(2026, 1, 10), 100.0)
    days = build_calendar(db, ATHLETE_ID, date(2026, 1, 10), date(2026, 1, 10))
    assert days[0].status == "unplanned"


def test_calendar_marks_missed_past_workout(db):
    create_planned_workout(db, ATHLETE_ID, {"date": date(2020, 1, 10), "planned_tss": 100})
    days = build_calendar(db, ATHLETE_ID, date(2020, 1, 10), date(2020, 1, 10))
    assert days[0].status == "missed"


def test_calendar_does_not_mark_future_workout_as_missed(db):
    """Um treino de amanhã está agendado, não perdido."""
    tomorrow = date.today() + timedelta(days=1)
    create_planned_workout(db, ATHLETE_ID, {"date": tomorrow, "planned_tss": 100})
    days = build_calendar(db, ATHLETE_ID, tomorrow, tomorrow)
    assert days[0].status == "scheduled"


def test_calendar_computes_compliance(db):
    create_planned_workout(db, ATHLETE_ID, {"date": date(2020, 1, 10), "planned_tss": 100})
    _add_activity(db, date(2020, 1, 10), 90.0)
    days = build_calendar(db, ATHLETE_ID, date(2020, 1, 10), date(2020, 1, 10))
    assert days[0].compliance_pct == pytest.approx(90.0)
    assert days[0].status == "completed"


def test_calendar_marks_partial_when_below_threshold(db):
    create_planned_workout(db, ATHLETE_ID, {"date": date(2020, 1, 10), "planned_tss": 200})
    _add_activity(db, date(2020, 1, 10), 80.0)
    days = build_calendar(db, ATHLETE_ID, date(2020, 1, 10), date(2020, 1, 10))
    assert days[0].status == "partial"


def test_calendar_covers_every_day_in_range(db):
    days = build_calendar(db, ATHLETE_ID, date(2026, 1, 1), date(2026, 1, 31))
    assert len(days) == 31


def test_reconcile_links_workout_to_activity(db):
    create_planned_workout(db, ATHLETE_ID, {"date": date(2020, 1, 10), "planned_tss": 100})
    activity_id = _add_activity(db, date(2020, 1, 10), 95.0)

    assert reconcile(db, ATHLETE_ID, date(2020, 1, 1), date(2020, 1, 31)) == 1
    linked = db.execute(
        "SELECT activity_id, status FROM planned_workouts"
    ).fetchone()
    assert str(linked[0]) == activity_id
    assert linked[1] == "completed"


def test_reconcile_picks_highest_tss_activity(db):
    """Com dois treinos no dia, o plano casa com a sessão principal."""
    create_planned_workout(db, ATHLETE_ID, {"date": date(2020, 1, 10), "planned_tss": 100})
    _add_activity(db, date(2020, 1, 10), 30.0)
    main = _add_activity(db, date(2020, 1, 10), 150.0)

    reconcile(db, ATHLETE_ID, date(2020, 1, 1), date(2020, 1, 31))
    linked = db.execute("SELECT activity_id FROM planned_workouts").fetchone()
    assert str(linked[0]) == main


def test_reconcile_is_idempotent(db):
    create_planned_workout(db, ATHLETE_ID, {"date": date(2020, 1, 10), "planned_tss": 100})
    _add_activity(db, date(2020, 1, 10), 95.0)

    reconcile(db, ATHLETE_ID, date(2020, 1, 1), date(2020, 1, 31))
    assert reconcile(db, ATHLETE_ID, date(2020, 1, 1), date(2020, 1, 31)) == 0
