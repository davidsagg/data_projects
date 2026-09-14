"""
Testes dos modelos dbt.

Verificar que o arquivo existe e contém a palavra "select" não prova nada: os
dois modelos ficaram meses referenciando colunas do schema legado (`start_time`,
`athlete_metrics`, `health_daily`) sem que nenhum teste notasse. Aqui o SQL roda
de verdade contra o schema canônico, em DuckDB in-memory.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from storage.catalog_store import CatalogStore

DBT = Path("dbt")


@pytest.fixture
def store() -> CatalogStore:
    """Catálogo em memória com o schema canônico já criado."""
    return CatalogStore.open(":memory:")


def _model_sql(name: str) -> str:
    return (DBT / "models" / f"{name}.sql").read_text()


def test_dbt_project_valid():
    config = yaml.safe_load((DBT / "dbt_project.yml").read_text())
    assert "name" in config and "version" in config
    assert "model-paths" in config or "models" in config


def test_weekly_summary_runs_against_schema(store: CatalogStore):
    """O modelo roda e agrupa por semana começando na segunda-feira."""
    athlete_id = store.resolve_athlete_id()

    # Quarta e sexta da mesma semana ISO, mais uma da semana seguinte.
    for started_at, tss, distance_m in [
        (datetime(2026, 9, 2, 7, 0), 80.0, 40_000.0),
        (datetime(2026, 9, 4, 7, 0), 120.0, 60_000.0),
        (datetime(2026, 9, 9, 7, 0), 50.0, 25_000.0),
    ]:
        store.conn.execute(
            """
            INSERT INTO activities (
                id, athlete_id, source, sport_type, started_at,
                elapsed_time_s, moving_time_s, distance_m, elevation_gain_m,
                tss, intensity_factor
            ) VALUES (uuid(), ?, 'fit', 'cycling', ?, 3600, 3500, ?, 300, ?, 0.75)
            """,
            [athlete_id, started_at, distance_m, tss],
        )

    weeks = store.conn.execute(_model_sql("weekly_summary")).fetchall()
    columns = [d[0] for d in store.conn.execute(_model_sql("weekly_summary")).description]

    assert "week_start" in columns
    assert len(weeks) == 2, "duas semanas distintas"

    by_week = {row[columns.index("week_start")]: row for row in weeks}
    first = by_week[date(2026, 8, 31)]  # segunda-feira da primeira semana
    assert first[columns.index("activity_count")] == 2
    assert first[columns.index("total_tss")] == pytest.approx(200.0)
    assert first[columns.index("total_km")] == pytest.approx(100.0)


def test_athlete_profile_runs_against_schema(store: CatalogStore):
    """O modelo junta carga e saúde pelo dia, mantendo dias sem saúde."""
    athlete_id = store.resolve_athlete_id()
    today = date(2026, 9, 10)

    for offset, ctl in [(0, 60.0), (1, 61.0)]:
        store.conn.execute(
            """
            INSERT INTO training_load (id, athlete_id, date, ctl, atl, tsb, daily_tss)
            VALUES (uuid(), ?, ?, ?, 70.0, -10.0, 90.0)
            """,
            [athlete_id, today + timedelta(days=offset), ctl],
        )

    # Saúde só no primeiro dia — o segundo precisa sobreviver ao LEFT JOIN.
    store.insert_health_daily(athlete_id, today, hrv_rmssd_ms=68.0, sleep_hours=7.5)

    rows = store.conn.execute(_model_sql("athlete_profile")).fetchall()
    columns = [
        d[0] for d in store.conn.execute(_model_sql("athlete_profile")).description
    ]

    assert len(rows) == 2, "nenhum dia de carga pode sumir no join"
    assert {"ctl", "atl", "tsb", "hrv_rmssd_ms", "sleep_hours"} <= set(columns)

    by_date = {row[columns.index("date")]: row for row in rows}
    assert by_date[today][columns.index("hrv_rmssd_ms")] == pytest.approx(68.0)
    assert by_date[today + timedelta(days=1)][columns.index("hrv_rmssd_ms")] is None
