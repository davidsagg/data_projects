"""
Testes do panorama do ciclo, das metas e dos marcos.

O sentido das metas é o ponto mais frágil: no peso, menor é melhor, e inverter
isso daria "meta atingida" para quem engordou — sem nenhum erro visível.
DuckDB real em memória, sem mock do storage.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from analytics.goals import evaluate_goals
from analytics.modality import INDOOR, OTHER, OUTDOOR, STRENGTH, classify
from analytics.panorama import build_panorama
from api.dependencies import get_db
from api.main import app
from storage.catalog_store import CatalogStore
from storage.models import Activity

REFERENCE = date(2026, 9, 30)  # quarta-feira


@pytest.fixture
def store() -> CatalogStore:
    store = CatalogStore.open(":memory:")
    athlete_id = store.resolve_athlete_id()
    store.conn.execute(
        "UPDATE athletes SET weight_kg = 74, ftp_w = 218 WHERE id = ?", [athlete_id]
    )
    store.conn.execute(
        """
        INSERT INTO ftp_history (id, athlete_id, effective_from, ftp_w, cp_w,
                                 w_prime_j, method, source)
        VALUES (gen_random_uuid(), ?, DATE '2026-01-31', 218, 218.1, 17000,
                'cp_60s_720s', 'test')
        """,
        [athlete_id],
    )
    return store


def add(store: CatalogStore, day: date, hours: float, tss: float, **meta) -> str:
    sport = meta.pop("sport", "cycling")
    activity = Activity(
        source="strava",
        sport_type=sport,
        started_at=datetime(day.year, day.month, day.day, 8, tzinfo=timezone.utc),
        elapsed_time_s=int(hours * 3600),
        moving_time_s=int(hours * 3600),
        distance_m=30000.0,
        elevation_gain_m=300.0,
        tss=tss,
    )
    activity_id = store.upsert_activity(activity, store.resolve_athlete_id())
    store.annotate_strava_meta(
        activity_id,
        meta.get("name"),
        meta.get("strava_sport_type"),
        meta.get("trainer"),
    )
    return activity_id


# ---------------------------------------------------------------------------
# Modalidade
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sport", "strava", "trainer", "expected"),
    [
        ("cycling", "Ride", False, OUTDOOR),
        ("cycling", "VirtualRide", None, INDOOR),
        ("cycling", "Ride", True, INDOOR),
        ("cycling", None, None, OUTDOOR),
        ("training", "WeightTraining", None, STRENGTH),
        ("training", None, None, STRENGTH),
        ("running", "Run", None, OTHER),
    ],
)
def test_classify(sport, strava, trainer, expected):
    assert classify(sport, strava, trainer) == expected


# ---------------------------------------------------------------------------
# Metas
# ---------------------------------------------------------------------------


def test_weight_goal_lower_is_better():
    [goal] = evaluate_goals([{"metric": "weight_kg", "target": 68}], {"weight_kg": 74})
    assert goal["remaining"] == 6
    assert goal["status"] == "far"
    assert goal["pct_of_target"] is None


def test_weight_goal_achieved_when_below_target():
    [goal] = evaluate_goals([{"metric": "weight_kg", "target": 68}], {"weight_kg": 67.5})
    assert goal["status"] == "achieved"


def test_volume_goal_pct_and_near():
    [goal] = evaluate_goals(
        [{"metric": "weekly_hours", "target": 10}], {"weekly_hours": 9.2}
    )
    assert goal["pct_of_target"] == 92.0
    assert goal["remaining"] == pytest.approx(0.8)
    assert goal["status"] == "near"


def test_goal_without_current_value_is_unknown():
    [goal] = evaluate_goals([{"metric": "ctl", "target": 60}], {})
    assert goal["status"] == "unknown"


def test_unknown_goal_metric_is_rejected(store):
    with pytest.raises(ValueError):
        store.set_goal(store.resolve_athlete_id(), "vo2max", 50)


def test_setting_goal_twice_replaces(store):
    athlete_id = store.resolve_athlete_id()
    store.set_goal(athlete_id, "weekly_hours", 8)
    store.set_goal(athlete_id, "weekly_hours", 10)
    assert [g["target"] for g in store.get_goals(athlete_id)] == [10]


# ---------------------------------------------------------------------------
# Panorama
# ---------------------------------------------------------------------------


def test_panorama_splits_volume_by_modality(store):
    add(store, date(2026, 9, 27), 4.0, 300, strava_sport_type="Ride", name="Prova")
    add(store, date(2026, 9, 24), 1.0, 40, strava_sport_type="VirtualRide")
    add(store, date(2026, 9, 23), 0.5, 5, sport="training",
        strava_sport_type="WeightTraining")

    result = build_panorama(store, store.resolve_athlete_id(), weeks=2,
                            reference=REFERENCE, with_zones=False)

    previous_week = result["volume"]["weeks"][0]
    assert previous_week["week_start"] == "2026-09-21"
    assert previous_week["hours"]["outdoor"] == 4.0
    assert previous_week["hours"]["indoor"] == 1.0
    assert previous_week["hours"]["strength"] == 0.5
    assert previous_week["total_hours"] == 5.5


def test_average_ignores_the_week_in_progress(store):
    add(store, date(2026, 9, 24), 6.0, 200)
    add(store, date(2026, 9, 29), 1.0, 50)  # semana corrente, ainda aberta

    result = build_panorama(store, store.resolve_athlete_id(), weeks=2,
                            reference=REFERENCE, with_zones=False)

    assert result["window"]["complete_weeks"] == 1
    assert result["volume"]["avg_weekly_hours"] == 6.0


def test_biggest_effort_against_typical_session(store):
    add(store, date(2026, 9, 27), 4.3, 347, name="L'etape Campos")
    for day in (22, 23, 24, 25):
        add(store, date(2026, 9, day), 1.0, 50)

    effort = build_panorama(store, store.resolve_athlete_id(), weeks=2,
                            reference=REFERENCE, with_zones=False)["biggest_effort"]

    assert effort["name"] == "L'etape Campos"
    assert effort["median_session_tss"] == 50
    assert effort["ratio_to_median"] == pytest.approx(6.9)


def test_w_per_kg_projected_at_goal_weight(store):
    store.set_goal(store.resolve_athlete_id(), "weight_kg", 68)
    athlete = build_panorama(store, store.resolve_athlete_id(), weeks=1,
                             reference=REFERENCE, with_zones=False)["athlete"]
    assert athlete["w_per_kg"] == pytest.approx(2.95)
    assert athlete["w_per_kg_at_goal"] == pytest.approx(3.21)


def test_cp_tests_appear_as_milestones(store):
    athlete_id = store.resolve_athlete_id()
    store.add_milestone(athlete_id, date(2026, 2, 10), "exame", "Ergoespirometria",
                        measurements={"vo2max_ml_kg_min": 48.0})
    milestones = build_panorama(store, athlete_id, weeks=1, reference=REFERENCE,
                                with_zones=False)["milestones"]

    assert [m["kind"] for m in milestones] == ["exame", "teste"]
    assert milestones[0]["measurements"] == {"vo2max_ml_kg_min": 48.0}
    assert milestones[1]["measurements"]["cp_w"] == 218.1


def test_unknown_milestone_kind_is_rejected(store):
    with pytest.raises(ValueError):
        store.add_milestone(store.resolve_athlete_id(), REFERENCE, "festa", "x")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client(store):
    app.dependency_overrides[get_db] = lambda: store.conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_goal_roundtrip(client):
    assert client.put("/goals", json={"metric": "weight_kg", "target": 68}).status_code == 200
    [goal] = client.get("/goals").json()
    assert goal["metric"] == "weight_kg" and goal["current"] == 74
    assert client.delete("/goals/weight_kg").status_code == 200
    assert client.get("/goals").json() == []


def test_goal_with_unknown_metric_is_422(client):
    assert client.put("/goals", json={"metric": "vo2", "target": 1}).status_code == 422


def test_milestone_roundtrip(client):
    created = client.post(
        "/milestones",
        json={"date": "2026-02-10", "kind": "exame", "title": "Ergoespirometria",
              "measurements": {"vo2max_ml_kg_min": 48}},
    )
    assert created.status_code == 201
    [milestone] = client.get("/milestones").json()
    assert milestone["title"] == "Ergoespirometria"
    client.delete(f"/milestones/{created.json()['id']}")
    assert client.get("/milestones").json() == []


def test_panorama_endpoint(client):
    body = client.get("/panorama", params={"weeks": 4, "zones": False}).json()
    assert body["window"]["weeks"] == 4
    assert len(body["volume"]["weeks"]) == 4
    assert body["volume"]["modalities"][0]["key"] == "outdoor"


def test_panorama_rejects_absurd_window(client):
    assert client.get("/panorama", params={"weeks": 200}).status_code == 422
