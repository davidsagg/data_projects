import pytest
import duckdb
from datetime import datetime, date, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app
from api.dependencies import get_db
from storage.catalog_store import CatalogStore
from storage.models import Activity

FIXTURES = Path("tests/fixtures")

ATHLETE_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    CatalogStore(conn).initialize_schema()
    conn.execute(
        "INSERT INTO athletes (id, name, ftp_w) VALUES (?, ?, ?)",
        [ATHLETE_ID, "Teste", 250.0],
    )
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def ins(db, gid="r1", dt=datetime(2024, 1, 15, 8, tzinfo=timezone.utc)):
    a = Activity(
        source="fit",
        garmin_id=gid,
        sport_type="cycling",
        started_at=dt,
        elapsed_time_s=3600,
        distance_m=40000,
        elevation_gain_m=400,
    )
    return CatalogStore(db).upsert_activity(a, ATHLETE_ID, garmin_id=gid)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_get_activities(client, db):
    ins(db, "r1")
    ins(db, "r2")
    r = client.get("/activities")
    assert r.status_code == 200 and len(r.json()) == 2


def test_filter_by_date(client, db):
    ins(db, "j", datetime(2024, 1, 15, 8, tzinfo=timezone.utc))
    ins(db, "f", datetime(2024, 2, 15, 8, tzinfo=timezone.utc))
    r = client.get("/activities?start=2024-01-01&end=2024-01-31")
    assert r.status_code == 200 and len(r.json()) == 1


def test_ingest_fit(client):
    with open(FIXTURES / "sample.fit", "rb") as f:
        r = client.post("/activities/ingest/fit",
                        files={"file": ("s.fit", f, "application/octet-stream")})
    assert r.status_code == 201 and "activity_id" in r.json()


def test_get_pmc(client, db):
    CatalogStore(db).upsert_training_load(ATHLETE_ID, date(2024, 1, 15), 45.0, 52.0, -7.0)
    r = client.get("/pmc")
    assert r.status_code == 200 and len(r.json()) > 0 and "ctl" in r.json()[0]


def test_get_power_curve(client, db):
    aid = ins(db)
    CatalogStore(db).save_power_curve(aid, date(2024, 1, 15), {300: 320.0})
    r = client.get("/power-curve")
    assert r.status_code == 200 and len(r.json()) > 0


def test_get_health_daily(client, db):
    CatalogStore(db).insert_health_daily(
        ATHLETE_ID, date(2024, 1, 15), sleep_quality_score=75
    )
    r = client.get("/health-daily?days=7")
    assert r.status_code == 200 and len(r.json()) >= 1


def test_readiness_today(client, db):
    today = date.today()
    CatalogStore(db).insert_health_daily(
        ATHLETE_ID, today, sleep_quality_score=80, hrv_rmssd_ms=45
    )
    CatalogStore(db).upsert_training_load(ATHLETE_ID, today, 55.0, 58.0, -3.0)
    r = client.get("/readiness/today")
    assert r.status_code == 200 and "score" in r.json()


def test_route_analyze(client):
    with open(FIXTURES / "sample.gpx", "rb") as f:
        r = client.post("/routes/analyze",
                        files={"file": ("s.gpx", f, "application/gpx+xml")})
    assert r.status_code == 200 and "total_gain_m" in r.json()


def test_health_alerts_no_data(client):
    r = client.get("/health/alerts")
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_health_alerts_tsb_danger(client, db):
    CatalogStore(db).upsert_training_load(ATHLETE_ID, date.today(), 80.0, 115.0, -35.0)
    r = client.get("/health/alerts")
    assert r.status_code == 200
    types = [a["type"] for a in r.json()]
    assert "tsb_critical" in types
    severities = [a["severity"] for a in r.json()]
    assert "danger" in severities


def test_health_alerts_tsb_warning(client, db):
    CatalogStore(db).upsert_training_load(ATHLETE_ID, date.today(), 60.0, 85.0, -25.0)
    r = client.get("/health/alerts")
    assert r.status_code == 200
    assert any(a["type"] == "tsb_high" for a in r.json())


@patch("api.routers.coach_router.PostActivityCoach")
def test_coach_analyze(MockCoach, client, db):
    from ai.post_activity_coach import CoachResponse
    MockCoach.return_value.analyze.return_value = CoachResponse(summary="Bom treino!")
    aid = ins(db)
    r = client.post("/coach/analyze-activity", json={"activity_id": aid})
    assert r.status_code == 200 and r.json()["summary"] == "Bom treino!"


@patch("api.routers.coach_router.WeeklyPlanCoach")
def test_weekly_plan(MockCoach, client, db):
    MockCoach.return_value.suggest_week.return_value = "Seg: Z2 60min\nTer: descanso"
    CatalogStore(db).upsert_training_load(ATHLETE_ID, date.today(), 55.0, 58.0, -3.0)
    r = client.post("/coach/weekly-plan", json={"target_tss_week": 400, "available_days": ["seg", "qua", "sex"]})
    assert r.status_code == 200
    body = r.json()
    assert "plan" in body and "insight_id" in body


@patch("api.routers.coach_router.WeeklyPlanCoach")
def test_weekly_plan_persisted(MockCoach, client, db):
    MockCoach.return_value.suggest_week.return_value = "Plano semanal teste"
    client.post("/coach/weekly-plan", json={})
    r = client.get("/coach/insights?type=weekly_plan")
    assert r.status_code == 200 and len(r.json()) >= 1
    assert r.json()[0]["insight_type"] == "weekly_plan"


@patch("api.routers.coach_router.OllamaClient")
def test_nutrition_advice(MockOllama, client):
    MockOllama.return_value.generate.return_value = "60g CHO/hora, beba 500ml/hora"
    r = client.post("/coach/nutrition-advice", json={"duration_h": 3.0, "tss_estimate": 250, "intensity": "moderado"})
    assert r.status_code == 200
    body = r.json()
    assert "advice" in body
    assert "Aviso" in body["advice"]  # disclaimer presente


@patch("api.routers.coach_router.InjuryRiskCoach")
def test_assess_injury_risk(MockCoach, client, db):
    from ai.injury_risk_coach import InjuryRiskFactors
    MockCoach.return_value.assess_factors.return_value = InjuryRiskFactors(
        ramp_rate_pct=15.0, tsb=-20.0, risk_level="medium",
        triggered_factors=["Ramp rate de 15% semana-a-semana"]
    )
    MockCoach.return_value.generate_assessment.return_value = "Risco moderado de lesão por overuse."
    r = client.post("/coach/assess-injury-risk")
    assert r.status_code == 200
    body = r.json()
    assert body["risk_level"] == "medium"
    assert "insight_id" in body


@patch("api.routers.coach_router.InjuryRiskCoach")
def test_injury_risk_stored_and_retrieved(MockCoach, client, db):
    from ai.injury_risk_coach import InjuryRiskFactors
    MockCoach.return_value.assess_factors.return_value = InjuryRiskFactors(risk_level="low")
    MockCoach.return_value.generate_assessment.return_value = "Sem fatores de risco."
    client.post("/coach/assess-injury-risk")
    r = client.get("/coach/insights?type=injury_risk")
    assert r.status_code == 200 and len(r.json()) >= 1


# ---------------------------------------------------------------------------
# Painel "como estava em" — o Resumo de uma semana passada
# ---------------------------------------------------------------------------


def _seed_two_moments(db):
    """Saúde e carga em duas datas: um mês atrás e hoje."""
    from datetime import timedelta

    store = CatalogStore(db)
    past = date.today() - timedelta(days=30)
    store.insert_health_daily(
        ATHLETE_ID, past, sleep_quality_score=90, hrv_rmssd_ms=60, body_battery=95
    )
    store.upsert_training_load(ATHLETE_ID, past, 70.0, 60.0, 10.0)
    store.insert_health_daily(
        ATHLETE_ID, date.today(), sleep_quality_score=40, hrv_rmssd_ms=30,
        body_battery=20,
    )
    store.upsert_training_load(ATHLETE_ID, date.today(), 50.0, 80.0, -30.0)
    return past


def test_today_with_reference_reads_that_date(client, db):
    past = _seed_two_moments(db)

    then = client.get(f"/today?reference={past.isoformat()}").json()
    now = client.get("/today").json()

    assert then["date"] == past.isoformat()
    assert then["form"]["tsb"] == 10.0
    assert then["readiness"]["hrv_rmssd_ms"] == 60
    assert then["pmc"][-1]["date"] == past.isoformat()
    assert now["form"]["tsb"] == -30.0
    assert now["readiness"]["hrv_rmssd_ms"] == 30


def test_today_future_reference_falls_back_to_today(client, db):
    from datetime import timedelta

    _seed_two_moments(db)
    future = date.today() + timedelta(days=10)
    r = client.get(f"/today?reference={future.isoformat()}")
    assert r.json()["date"] == date.today().isoformat()


def test_health_daily_end_bounds_the_window(client, db):
    past = _seed_two_moments(db)
    rows = client.get(f"/health-daily?days=45&end={past.isoformat()}").json()
    assert [r["date"] for r in rows] == [past.isoformat()]


def test_health_alerts_with_reference(client, db):
    past = _seed_two_moments(db)
    now = client.get("/health/alerts").json()
    then = client.get(f"/health/alerts?reference={past.isoformat()}").json()
    assert any(a["type"] == "tsb" or "TSB" in a["message"] for a in now)
    assert not any(a["type"] == "tsb" or "TSB" in a["message"] for a in then)
