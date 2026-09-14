"""
Testes da sincronização Strava → catálogo.

O que está sob teste aqui é sobretudo o dedupe. O acervo já tem centenas de
atividades vindas dos `.fit`, e o Strava devolve as mesmas pedaladas: se o
casamento falhar, cada treino entra duas vezes e o TSS do dia dobra, corrompendo
o PMC inteiro. Os testes usam DuckDB real, sem mock da camada de storage.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ingestion.strava_sync import (
    MATCH_TOLERANCE_S,
    StravaSync,
    activity_from_strava,
    normalize_sport,
    parse_start,
    streams_from_strava,
)
from storage.catalog_store import CatalogStore
from storage.models import Activity


class FakeStravaClient:
    """Cliente de mentira, com atividades e streams fixos."""

    def __init__(self, activities: list[dict], streams: dict | None = None) -> None:
        self._activities = activities
        self._streams = streams or {}
        self.stream_calls: list[int] = []

    def iter_activities(self, after=None, before=None):
        yield from self._activities

    def get_activity_streams(self, activity_id: int) -> dict:
        self.stream_calls.append(activity_id)
        return self._streams


def summary(strava_id: int, started_at: datetime, **overrides) -> dict:
    """Monta um resumo de atividade no formato do Strava."""
    payload = {
        "id": strava_id,
        "sport_type": "Ride",
        "start_date": started_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_time": 3600,
        "moving_time": 3500,
        "distance": 40000.0,
        "total_elevation_gain": 500.0,
        "average_watts": 180.0,
        "max_watts": 620.0,
        "average_heartrate": 142.0,
        "max_heartrate": 178,
        "average_cadence": 84.0,
        "average_speed": 11.1,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def store() -> CatalogStore:
    return CatalogStore.open(":memory:")


# ---------------------------------------------------------------------------
# Mapeamento
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("strava", "expected"),
    [
        ("Ride", "cycling"),
        ("VirtualRide", "cycling"),
        ("GravelRide", "cycling"),
        ("MountainBikeRide", "cycling"),
        ("Run", "running"),
        ("TrailRun", "running"),
        ("Swim", "swimming"),
        ("Hike", "walking"),
        ("WeightTraining", "training"),
        (None, "unknown"),
    ],
)
def test_normalize_sport(strava, expected):
    """O vocabulário tem de bater com o que os `.fit` já gravaram."""
    assert normalize_sport(strava) == expected


def test_parse_start_is_timezone_aware():
    parsed = parse_start("2026-09-01T10:24:31Z")
    assert parsed.tzinfo is not None
    assert parsed == datetime(2026, 9, 1, 10, 24, 31, tzinfo=timezone.utc)


def test_activity_from_strava_leaves_derived_metrics_empty():
    """NP/IF/VI/TSS são da analytics, não do Strava — o critério precisa ser um só."""
    activity = activity_from_strava(summary(1, datetime(2026, 9, 1, 10, tzinfo=timezone.utc)))

    assert activity.source == "strava"
    assert activity.strava_id == 1
    assert activity.avg_power_w == 180.0
    assert activity.normalized_power_w is None
    assert activity.tss is None
    assert activity.intensity_factor is None
    assert activity.variability_index is None


def test_streams_from_strava_maps_channels():
    points = streams_from_strava(
        {
            "time": {"data": [0, 1, 2]},
            "watts": {"data": [200, 210, 220]},
            "heartrate": {"data": [130, 132, 134]},
            "latlng": {"data": [[-22.9, -43.2], [-22.91, -43.21], [-22.92, -43.22]]},
            "altitude": {"data": [10.0, 12.0, 14.0]},
        }
    )

    assert len(points) == 3
    assert points[1].power_w == 210
    assert points[1].hr_bpm == 132
    assert points[1].lat == pytest.approx(-22.91)
    assert points[1].lon == pytest.approx(-43.21)
    assert points[2].altitude_m == 14.0


def test_streams_tolerate_shorter_channel():
    """Canal mais curto que o de tempo não pode estourar índice."""
    points = streams_from_strava(
        {"time": {"data": [0, 1, 2]}, "watts": {"data": [200]}}
    )

    assert len(points) == 3
    assert points[0].power_w == 200
    assert points[2].power_w is None


def test_streams_without_time_channel_is_empty():
    assert streams_from_strava({"watts": {"data": [1, 2, 3]}}) == []


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------


def _insert_fit_activity(store: CatalogStore, started_at: datetime) -> str:
    """Grava uma atividade como se tivesse vindo de um arquivo `.fit`."""
    athlete_id = store.resolve_athlete_id()
    return store.upsert_activity(
        Activity(
            source="fit",
            sport_type="cycling",
            started_at=started_at,
            elapsed_time_s=3600,
        ),
        athlete_id,
        garmin_id=started_at.strftime("%Y%m%d_%H%M%S"),
    )


def test_new_activity_is_inserted(store: CatalogStore):
    started = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    client = FakeStravaClient([summary(555, started)], {"time": {"data": [0, 1]}})

    report = StravaSync(client, store).sync()

    assert report.inserted == 1
    assert report.linked == 0
    assert store.find_activity_by_strava_id(555) is not None


def test_existing_fit_activity_is_linked_not_duplicated(store: CatalogStore):
    """O caso central: a mesma pedalada já está no acervo, vinda do `.fit`."""
    started = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    fit_id = _insert_fit_activity(store, started)
    client = FakeStravaClient([summary(555, started)])

    report = StravaSync(client, store).sync(with_streams=False)

    assert report.linked == 1
    assert report.inserted == 0
    total = store.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    assert total == 1, "a atividade não pode entrar duas vezes"
    assert store.find_activity_by_strava_id(555) == fit_id


def test_link_matches_within_tolerance(store: CatalogStore):
    """Garmin e Strava divergem por segundos no início do mesmo treino."""
    started = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    _insert_fit_activity(store, started)
    drifted = started + timedelta(seconds=MATCH_TOLERANCE_S - 10)
    client = FakeStravaClient([summary(555, drifted)])

    report = StravaSync(client, store).sync(with_streams=False)

    assert report.linked == 1


def test_distinct_activities_outside_tolerance_are_separate(store: CatalogStore):
    """Dois treinos no mesmo dia, distantes o bastante, não podem se fundir."""
    started = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    _insert_fit_activity(store, started)
    later = started + timedelta(hours=6)
    client = FakeStravaClient([summary(555, later)])

    report = StravaSync(client, store).sync(with_streams=False)

    assert report.inserted == 1
    assert report.linked == 0
    assert store.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 2


def test_already_synced_activity_is_skipped(store: CatalogStore):
    """Rodar duas vezes seguidas não muda nada — a sincronização é idempotente."""
    started = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    client = FakeStravaClient([summary(555, started)], {"time": {"data": [0, 1]}})
    sync = StravaSync(client, store)

    sync.sync()
    second = sync.sync()

    assert second.skipped == 1
    assert second.inserted == 0
    assert store.conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 1


def test_linked_activity_keeps_existing_streams(store: CatalogStore):
    """Os streams do `.fit` são mais ricos; não se sobrepõem com os do Strava."""
    started = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    fit_id = _insert_fit_activity(store, started)
    from storage.models import ActivityStream

    store.insert_streams(fit_id, [ActivityStream(time_s=t) for t in range(10)])
    client = FakeStravaClient([summary(555, started)], {"time": {"data": [0, 1]}})

    StravaSync(client, store).sync()

    assert store.count_streams(fit_id) == 10
    assert client.stream_calls == [], "não devia nem pedir os streams ao Strava"


def test_linked_activity_without_streams_gets_them(store: CatalogStore):
    """Se o registro local está sem série temporal, o Strava preenche a lacuna."""
    started = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    fit_id = _insert_fit_activity(store, started)
    client = FakeStravaClient([summary(555, started)], {"time": {"data": [0, 1, 2]}})

    StravaSync(client, store).sync()

    assert store.count_streams(fit_id) == 3


def test_limit_stops_early(store: CatalogStore):
    base = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    activities = [summary(i, base + timedelta(days=i)) for i in range(1, 6)]
    client = FakeStravaClient(activities)

    report = StravaSync(client, store).sync(limit=2, with_streams=False)

    assert report.fetched == 2
    assert report.inserted == 2


def test_broken_activity_does_not_abort_batch(store: CatalogStore):
    """Um payload ruim vira erro registrado, não um lote perdido."""
    base = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    good = summary(1, base)
    broken = summary(2, base + timedelta(days=1))
    del broken["start_date"]
    client = FakeStravaClient([good, broken, summary(3, base + timedelta(days=2))])

    report = StravaSync(client, store).sync(with_streams=False)

    assert report.inserted == 2
    assert len(report.errors) == 1
    assert "atividade 2" in report.errors[0]
