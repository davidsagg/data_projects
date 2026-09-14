"""
Testes dos endpoints de análise avançada de treino.

Cobrem o contrato que o frontend consome: semana executada, intervalos, W'bal e
durabilidade — incluindo os casos em que a resposta certa é "não dá para
responder" (sem FTP, sem potência, sem teste de CP registrado).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import duckdb
import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_db
from api.main import app
from storage.catalog_store import CatalogStore
from storage.models import Activity, ActivityStream

ATHLETE_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    CatalogStore(conn).initialize_schema()
    conn.execute(
        "INSERT INTO athletes (id, name, ftp_w) VALUES (?, ?, ?)",
        [ATHLETE_ID, "Teste", 250.0],
    )
    conn.execute(
        "INSERT INTO ftp_history (id, athlete_id, effective_from, ftp_w, source) "
        "VALUES (uuid(), ?, DATE '2023-01-01', 250.0, 'manual')",
        [ATHLETE_ID],
    )
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def add(db, day: date, power: list[float] | None = None, tss: float = 80.0) -> str:
    """Grava uma atividade com streams opcionais e devolve o id."""
    store = CatalogStore(db)
    activity_id = store.upsert_activity(
        Activity(
            source="fit",
            sport_type="cycling",
            started_at=datetime(day.year, day.month, day.day, 7, tzinfo=timezone.utc),
            elapsed_time_s=len(power) if power else 3600,
            moving_time_s=len(power) if power else 3600,
            distance_m=40000.0,
            elevation_gain_m=400.0,
            tss=tss,
        ),
        ATHLETE_ID,
    )
    if power:
        store.insert_streams(
            activity_id,
            [ActivityStream(time_s=i, power_w=w) for i, w in enumerate(power)],
        )
    return activity_id


def workout(reps: int, work_s: int, work_w: float, rest_s: int, rest_w: float) -> list:
    points: list[float] = [rest_w] * 300
    for _ in range(reps):
        points += [work_w] * work_s + [rest_w] * rest_s
    return points


# ---------------------------------------------------------------------------
# /week e /weeks
# ---------------------------------------------------------------------------


def test_week_defaults_to_monday_sunday(client, db):
    add(db, date(2026, 9, 9))

    payload = client.get("/week?reference=2026-09-09&zones=false").json()

    assert payload["week_start"] == "2026-09-07"
    assert payload["week_end"] == "2026-09-13"
    assert payload["session_count"] == 1


def test_week_aggregates_volume(client, db):
    for offset in range(3):
        add(db, date(2026, 9, 7) + timedelta(days=offset), tss=50.0)

    payload = client.get("/week?reference=2026-09-09&zones=false").json()

    assert payload["total_tss"] == pytest.approx(150.0)
    assert payload["total_km"] == pytest.approx(120.0)
    assert payload["rest_days"] == 4


def test_week_reports_intensity_distribution(client, db):
    add(db, date(2026, 9, 8), power=[140.0] * 7200)
    add(db, date(2026, 9, 10), power=[140.0] * 3600 + [300.0] * 600)

    payload = client.get("/week?reference=2026-09-09").json()

    assert payload["distribution"] in {"polarizado", "piramidal"}
    assert payload["intensity"]["easy"]["pct"] > 70
    assert payload["intensity"]["hard"]["seconds"] > 0


def test_week_without_zones_is_light(client, db):
    add(db, date(2026, 9, 8), power=[200.0] * 3600)

    payload = client.get("/week?reference=2026-09-09&zones=false").json()

    assert payload["zone_seconds"] == {}
    assert payload["intensity"]["easy"] is None


def test_empty_week_returns_zeros(client):
    payload = client.get("/week?reference=2026-09-09&zones=false").json()

    assert payload["session_count"] == 0
    assert payload["rest_days"] == 7
    assert payload["distribution"] == "sem dados"


def test_weeks_series_is_chronological(client, db):
    add(db, date(2026, 9, 8))

    payload = client.get("/weeks?weeks=4&reference=2026-09-09").json()

    assert len(payload) == 4
    assert [w["week_start"] for w in payload] == sorted(w["week_start"] for w in payload)


def test_weeks_is_capped_at_52(client):
    payload = client.get("/weeks?weeks=500&reference=2026-09-09").json()

    assert len(payload) == 52


# ---------------------------------------------------------------------------
# /activities/{id}/intervals
# ---------------------------------------------------------------------------


def test_intervals_detects_workout_structure(client, db):
    activity_id = add(db, date(2026, 9, 8), power=workout(4, 240, 300.0, 180, 150.0))

    payload = client.get(f"/activities/{activity_id}/intervals").json()

    assert payload["interval_count"] == 4
    assert payload["ftp_w_at_time"] == 250.0
    assert payload["threshold_w"] == pytest.approx(220.0)
    assert len(payload["sets"]) == 1
    assert payload["sets"][0]["count"] == 4
    assert payload["sets"][0]["label"].startswith("4 × 4min")


def test_intervals_carry_intensity_factor(client, db):
    activity_id = add(db, date(2026, 9, 8), power=workout(3, 240, 300.0, 180, 150.0))

    payload = client.get(f"/activities/{activity_id}/intervals").json()

    first = payload["intervals"][0]
    assert first["intensity_factor"] == pytest.approx(1.2, abs=0.06)
    assert first["end_s"] == first["start_s"] + first["duration_s"]


def test_steady_ride_reports_no_intervals(client, db):
    activity_id = add(db, date(2026, 9, 8), power=[160.0] * 3600)

    payload = client.get(f"/activities/{activity_id}/intervals").json()

    assert payload["interval_count"] == 0
    assert payload["sets"] == []


def test_intervals_threshold_is_tunable(client, db):
    """Baixar o limiar revela blocos de sweet spot que o padrão ignora."""
    activity_id = add(db, date(2026, 9, 8), power=workout(3, 300, 200.0, 120, 120.0))

    default = client.get(f"/activities/{activity_id}/intervals").json()
    lowered = client.get(f"/activities/{activity_id}/intervals?threshold=0.75").json()

    assert default["interval_count"] == 0
    assert lowered["interval_count"] == 3


def test_intervals_unknown_activity_is_404(client):
    missing = "22222222-2222-2222-2222-222222222222"

    assert client.get(f"/activities/{missing}/intervals").status_code == 404


# ---------------------------------------------------------------------------
# /activities/{id}/wbal
# ---------------------------------------------------------------------------


def _register_cp_test(db, when: str = "2026-01-31", cp: float = 218.1, wp: float = 17000.0):
    db.execute(
        "INSERT INTO ftp_history (id, athlete_id, effective_from, ftp_w, cp_w, "
        "w_prime_j, source) VALUES (uuid(), ?, CAST(? AS DATE), ?, ?, ?, 'test')",
        [ATHLETE_ID, when, cp, cp, wp],
    )


def test_wbal_uses_registered_cp_test(client, db):
    _register_cp_test(db)
    activity_id = add(db, date(2026, 9, 8), power=[300.0] * 120 + [120.0] * 600)

    payload = client.get(f"/activities/{activity_id}/wbal").json()

    assert payload["cp_w"] == pytest.approx(218.1)
    assert payload["w_prime_j"] == pytest.approx(17000.0)
    assert payload["depletion_pct"] > 0
    assert len(payload["balance"]) == 720


def test_wbal_depletes_above_cp_and_recovers_below(client, db):
    _register_cp_test(db, cp=200.0, wp=20000.0)
    activity_id = add(db, date(2026, 9, 8), power=[400.0] * 60 + [100.0] * 900)

    payload = client.get(f"/activities/{activity_id}/wbal").json()

    balance = payload["balance"]
    assert balance[0] < payload["w_prime_j"], "consumiu acima do CP"
    assert balance[-1] > min(balance), "repôs abaixo do CP"
    assert payload["tau_s"] > 0


def test_wbal_accepts_manual_override(client, db):
    activity_id = add(db, date(2026, 9, 8), power=[300.0] * 300)

    payload = client.get(
        f"/activities/{activity_id}/wbal?cp=200&w_prime=15000"
    ).json()

    assert payload["cp_w"] == 200.0
    assert payload["w_prime_j"] == 15000.0


def test_wbal_without_cp_test_is_422(client, db):
    activity_id = add(db, date(2026, 9, 8), power=[300.0] * 300)

    response = client.get(f"/activities/{activity_id}/wbal")

    assert response.status_code == 422
    assert "potência crítica" in response.json()["detail"]


def test_wbal_without_power_is_422(client, db):
    _register_cp_test(db)
    activity_id = add(db, date(2026, 9, 8))

    response = client.get(f"/activities/{activity_id}/wbal")

    assert response.status_code == 422
    assert "potência" in response.json()["detail"]


def test_wbal_long_series_is_decimated(client, db):
    _register_cp_test(db)
    activity_id = add(db, date(2026, 9, 8), power=[250.0] * 5000)

    payload = client.get(f"/activities/{activity_id}/wbal").json()

    assert len(payload["balance"]) == 900, "a série cabe no gráfico"


# ---------------------------------------------------------------------------
# /activities/{id}/durability
# ---------------------------------------------------------------------------


def test_durability_of_short_ride_is_inconclusive(client, db):
    activity_id = add(db, date(2026, 9, 8), power=[200.0] * 1200)

    payload = client.get(f"/activities/{activity_id}/durability").json()

    assert payload["is_conclusive"] is False
    assert payload["verdict"] == "inconclusivo"


def test_durability_detects_decline(client, db):
    activity_id = add(
        db, date(2026, 9, 8), power=[300.0] * 3333 + [240.0] * 3000
    )

    payload = client.get(f"/activities/{activity_id}/durability").json()

    assert payload["is_conclusive"] is True
    assert payload["verdict"] == "baixa"
    assert all(p["change_pct"] < -15 for p in payload["points"])


def test_durability_threshold_is_tunable(client, db):
    activity_id = add(db, date(2026, 9, 8), power=[250.0] * 9000)

    low = client.get(f"/activities/{activity_id}/durability?kj=500").json()
    high = client.get(f"/activities/{activity_id}/durability?kj=1500").json()

    assert low["split_time_s"] < high["split_time_s"]


def test_durability_unknown_activity_is_404(client):
    missing = "22222222-2222-2222-2222-222222222222"

    assert client.get(f"/activities/{missing}/durability").status_code == 404
