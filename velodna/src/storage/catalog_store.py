"""
CatalogStore — camada de persistência DuckDB do VeloDNA.

Responsabilidades:
  - Criar e manter o schema (DDL)
  - Upsert de Activity + ActivityStream
  - Upsert de HealthMetric por (athlete_id, date)
  - Inserção de Route + RouteWaypoints
  - Queries analíticas básicas
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from ingestion.fit_parser import Activity, ActivityStream

# ---------------------------------------------------------------------------
# DDL — todas as 13 tabelas do schema VeloDNA
# ---------------------------------------------------------------------------

_DDL = """
CREATE SEQUENCE IF NOT EXISTS seq_activity_streams START 1;
CREATE SEQUENCE IF NOT EXISTS seq_route_waypoints  START 1;

CREATE TABLE IF NOT EXISTS athletes (
    id          UUID PRIMARY KEY,
    name        VARCHAR,
    ftp_w       FLOAT,
    max_hr_bpm  INTEGER,
    weight_kg   FLOAT,
    birth_date  DATE,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS activities (
    id                  UUID PRIMARY KEY,
    athlete_id          UUID,
    garmin_id           VARCHAR UNIQUE,
    source              VARCHAR NOT NULL,
    sport_type          VARCHAR NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL,
    elapsed_time_s      INTEGER,
    moving_time_s       INTEGER,
    distance_m          FLOAT,
    elevation_gain_m    FLOAT,
    avg_power_w         FLOAT,
    normalized_power_w  FLOAT,
    avg_hr_bpm          FLOAT,
    avg_cadence_rpm     FLOAT,
    avg_speed_ms        FLOAT,
    tss                 FLOAT,
    intensity_factor    FLOAT,
    variability_index   FLOAT,
    raw_file_path       VARCHAR,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS activity_streams (
    id                  BIGINT PRIMARY KEY DEFAULT nextval('seq_activity_streams'),
    activity_id         UUID NOT NULL,
    time_s              INTEGER,
    lat                 DOUBLE,
    lon                 DOUBLE,
    altitude_m          FLOAT,
    distance_m          FLOAT,
    power_w             FLOAT,
    hr_bpm              FLOAT,
    cadence_rpm         FLOAT,
    speed_ms            FLOAT,
    temperature_c       FLOAT,
    left_right_balance  FLOAT
);

CREATE TABLE IF NOT EXISTS segments (
    id              UUID PRIMARY KEY,
    name            VARCHAR NOT NULL,
    start_lat       DOUBLE,
    start_lon       DOUBLE,
    end_lat         DOUBLE,
    end_lon         DOUBLE,
    distance_m      FLOAT,
    elevation_gain_m FLOAT,
    avg_grade_pct   FLOAT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS segment_efforts (
    id              UUID PRIMARY KEY,
    activity_id     UUID,
    segment_id      UUID,
    athlete_id      UUID,
    started_at      TIMESTAMPTZ,
    elapsed_time_s  INTEGER,
    avg_power_w     FLOAT,
    avg_hr_bpm      FLOAT,
    avg_speed_ms    FLOAT,
    is_pr           BOOLEAN,
    rank            INTEGER
);

CREATE TABLE IF NOT EXISTS routes (
    id                   UUID PRIMARY KEY,
    athlete_id           UUID,
    name                 VARCHAR NOT NULL,
    source_file_path     VARCHAR,
    distance_m           FLOAT,
    elevation_gain_m     FLOAT,
    estimated_duration_s FLOAT,
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS route_waypoints (
    id                    BIGINT PRIMARY KEY DEFAULT nextval('seq_route_waypoints'),
    route_id              UUID NOT NULL,
    sequence              INTEGER NOT NULL,
    lat                   DOUBLE,
    lon                   DOUBLE,
    altitude_m            FLOAT,
    distance_from_start_m FLOAT
);

CREATE TABLE IF NOT EXISTS health_metrics (
    id                  UUID PRIMARY KEY,
    athlete_id          UUID NOT NULL,
    date                DATE NOT NULL,
    hrv_rmssd_ms        FLOAT,
    resting_hr_bpm      INTEGER,
    sleep_hours         FLOAT,
    sleep_quality_score INTEGER,
    recovery_score      INTEGER,
    body_battery        INTEGER,
    stress_level        INTEGER,
    source              VARCHAR,
    UNIQUE (athlete_id, date)
);

CREATE TABLE IF NOT EXISTS training_load (
    id          UUID PRIMARY KEY,
    athlete_id  UUID NOT NULL,
    date        DATE NOT NULL,
    ctl         FLOAT,
    atl         FLOAT,
    tsb         FLOAT,
    daily_tss   FLOAT
);

CREATE TABLE IF NOT EXISTS power_zones (
    id             UUID PRIMARY KEY,
    athlete_id     UUID,
    zone           INTEGER,
    label          VARCHAR,
    min_w          FLOAT,
    max_w          FLOAT,
    effective_from DATE
);

CREATE TABLE IF NOT EXISTS hr_zones (
    id             UUID PRIMARY KEY,
    athlete_id     UUID,
    zone           INTEGER,
    label          VARCHAR,
    min_bpm        INTEGER,
    max_bpm        INTEGER,
    effective_from DATE
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id          UUID PRIMARY KEY,
    athlete_id  UUID,
    session_id  UUID,
    role        VARCHAR,
    content     TEXT,
    model       VARCHAR,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_insights (
    id               UUID PRIMARY KEY,
    athlete_id       UUID,
    activity_id      UUID,
    insight_type     VARCHAR,
    content          TEXT,
    model            VARCHAR,
    confidence_score FLOAT,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS power_curves (
    id          UUID PRIMARY KEY,
    activity_id UUID NOT NULL,
    date        DATE NOT NULL,
    duration_s  INTEGER NOT NULL,
    power_w     FLOAT NOT NULL,
    UNIQUE (activity_id, duration_s)
);
"""

# Campos permitidos em insert_health_daily para evitar injeção de coluna
_HEALTH_METRIC_FIELDS = frozenset({
    "hrv_rmssd_ms", "resting_hr_bpm", "sleep_hours", "sleep_quality_score",
    "recovery_score", "body_battery", "stress_level", "source",
})


def _new_id() -> str:
    return str(uuid.uuid4())


def _iter_statements(sql: str):
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            yield stmt


# ---------------------------------------------------------------------------
# CatalogStore
# ---------------------------------------------------------------------------

class CatalogStore:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    @classmethod
    def open(cls, path: str | Path = ":memory:") -> "CatalogStore":
        conn = duckdb.connect(str(path))
        store = cls(conn)
        store.initialize_schema()
        return store

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def initialize_schema(self) -> None:
        for stmt in _iter_statements(_DDL):
            self._conn.execute(stmt)

    # ------------------------------------------------------------------
    # Activities
    # ------------------------------------------------------------------

    def upsert_activity(
        self,
        activity: Activity,
        athlete_id: str,
        garmin_id: str | None = None,
    ) -> str:
        """Insere nova atividade ou atualiza registro existente pelo garmin_id."""
        if garmin_id is not None:
            existing = self._find_activity_by_garmin_id(garmin_id)
            if existing:
                self._conn.execute(
                    self._sql_update_activity(),
                    self._activity_update_params(activity, existing),
                )
                return existing

        activity_id = activity.id or _new_id()
        self._conn.execute(
            self._sql_insert_activity(),
            self._activity_insert_params(activity_id, athlete_id, garmin_id, activity),
        )
        return activity_id

    def insert_streams(
        self, activity_id: str, streams: list[ActivityStream]
    ) -> None:
        """Insere streams segundo a segundo de uma atividade."""
        rows = [
            (
                activity_id, s.time_s, s.lat, s.lon, s.altitude_m,
                s.distance_m, s.power_w, s.hr_bpm, s.cadence_rpm,
                s.speed_ms, s.temperature_c, s.left_right_balance,
            )
            for s in streams
        ]
        self._conn.executemany(self._sql_insert_stream(), rows)

    # ------------------------------------------------------------------
    # Health metrics
    # ------------------------------------------------------------------

    def insert_health_daily(
        self,
        athlete_id: str,
        record_date: date,
        **metrics: Any,
    ) -> str:
        """Upsert de métricas diárias de saúde por (athlete_id, date)."""
        unknown = set(metrics) - _HEALTH_METRIC_FIELDS
        if unknown:
            raise ValueError(f"Campos de saúde desconhecidos: {unknown}")

        existing = self._find_health_by_date(athlete_id, record_date)
        if existing:
            self._update_health_row(existing, metrics)
            return existing

        health_id = _new_id()
        self._conn.execute(
            self._sql_insert_health(),
            [
                health_id, athlete_id, record_date,
                metrics.get("hrv_rmssd_ms"),
                metrics.get("resting_hr_bpm"),
                metrics.get("sleep_hours"),
                metrics.get("sleep_quality_score"),
                metrics.get("recovery_score"),
                metrics.get("body_battery"),
                metrics.get("stress_level"),
                metrics.get("source", "manual"),
            ],
        )
        return health_id

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def insert_route(
        self,
        athlete_id: str,
        name: str,
        waypoints: list[dict],
        **attrs: Any,
    ) -> str:
        """Insere rota e seus waypoints em transação."""
        route_id = _new_id()
        self._conn.execute(
            self._sql_insert_route(),
            [
                route_id, athlete_id, name,
                attrs.get("source_file_path"),
                attrs.get("distance_m"),
                attrs.get("elevation_gain_m"),
                attrs.get("estimated_duration_s"),
            ],
        )
        self._conn.executemany(
            self._sql_insert_waypoint(),
            [
                (route_id, i, wp.get("lat"), wp.get("lon"),
                 wp.get("altitude_m"), wp.get("distance_from_start_m"))
                for i, wp in enumerate(waypoints)
            ],
        )
        return route_id

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def query_activities_by_date_range(
        self,
        athlete_id: str,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        """Retorna atividades de um atleta no intervalo [start, end] ordenadas por data."""
        result = self._conn.execute(
            self._sql_activities_by_date_range(),
            [athlete_id, start, end],
        )
        cols = [d[0] for d in result.description]
        return [dict(zip(cols, row)) for row in result.fetchall()]

    def get_streams_for_activity(self, activity_id: str) -> list[ActivityStream]:
        """Carrega todos os streams de uma atividade ordenados por tempo."""
        rows = self._conn.execute(
            self._sql_streams_for_activity(), [activity_id]
        ).fetchall()
        return [
            ActivityStream(
                time_s=r[0], lat=r[1], lon=r[2], altitude_m=r[3],
                distance_m=r[4], power_w=r[5], hr_bpm=r[6],
                cadence_rpm=r[7], speed_ms=r[8], temperature_c=r[9],
                left_right_balance=r[10],
            )
            for r in rows
        ]

    def save_power_curve(
        self,
        activity_id: str,
        record_date: date,
        curve: dict[int, float],
    ) -> None:
        """Persiste curva de potência; upsert por (activity_id, duration_s)."""
        self._conn.executemany(
            self._sql_upsert_power_curve(),
            [
                (_new_id(), activity_id, record_date, duration_s, power_w)
                for duration_s, power_w in curve.items()
            ],
        )

    def get_power_curve(self, activity_id: str) -> dict[int, float]:
        """Retorna curva de potência armazenada como {duration_s: power_w}."""
        rows = self._conn.execute(
            "SELECT duration_s, power_w FROM power_curves WHERE activity_id = ? ORDER BY duration_s",
            [activity_id],
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    # ------------------------------------------------------------------
    # SQL privados (REFACTOR: queries extraídas em métodos nomeados)
    # ------------------------------------------------------------------

    def _sql_insert_activity(self) -> str:
        return """
            INSERT INTO activities (
                id, athlete_id, garmin_id, source, sport_type, started_at,
                elapsed_time_s, moving_time_s, distance_m, elevation_gain_m,
                avg_power_w, normalized_power_w, avg_hr_bpm, avg_cadence_rpm,
                avg_speed_ms, tss, intensity_factor, variability_index, raw_file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

    def _sql_update_activity(self) -> str:
        return """
            UPDATE activities SET
                source=?, sport_type=?, started_at=?,
                elapsed_time_s=?, moving_time_s=?, distance_m=?,
                elevation_gain_m=?, avg_power_w=?, normalized_power_w=?,
                avg_hr_bpm=?, avg_cadence_rpm=?, avg_speed_ms=?,
                tss=?, intensity_factor=?, variability_index=?, raw_file_path=?
            WHERE id=?
        """

    def _sql_insert_stream(self) -> str:
        return """
            INSERT INTO activity_streams (
                activity_id, time_s, lat, lon, altitude_m, distance_m,
                power_w, hr_bpm, cadence_rpm, speed_ms, temperature_c, left_right_balance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

    def _sql_insert_health(self) -> str:
        return """
            INSERT INTO health_metrics (
                id, athlete_id, date, hrv_rmssd_ms, resting_hr_bpm,
                sleep_hours, sleep_quality_score, recovery_score,
                body_battery, stress_level, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

    def _sql_insert_route(self) -> str:
        return """
            INSERT INTO routes (
                id, athlete_id, name, source_file_path,
                distance_m, elevation_gain_m, estimated_duration_s
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """

    def _sql_insert_waypoint(self) -> str:
        return """
            INSERT INTO route_waypoints (
                route_id, sequence, lat, lon, altitude_m, distance_from_start_m
            ) VALUES (?, ?, ?, ?, ?, ?)
        """

    def _sql_streams_for_activity(self) -> str:
        return """
            SELECT time_s, lat, lon, altitude_m, distance_m, power_w, hr_bpm,
                   cadence_rpm, speed_ms, temperature_c, left_right_balance
            FROM activity_streams
            WHERE activity_id = ?
            ORDER BY time_s ASC
        """

    def _sql_upsert_power_curve(self) -> str:
        return """
            INSERT INTO power_curves (id, activity_id, date, duration_s, power_w)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (activity_id, duration_s) DO UPDATE SET
                power_w = EXCLUDED.power_w,
                date    = EXCLUDED.date
        """

    def _sql_activities_by_date_range(self) -> str:
        return """
            SELECT * FROM activities
            WHERE athlete_id = ?
              AND started_at >= ?
              AND started_at <= ?
            ORDER BY started_at ASC
        """

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _find_activity_by_garmin_id(self, garmin_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT id FROM activities WHERE garmin_id = ?", [garmin_id]
        ).fetchone()
        return str(row[0]) if row else None

    def _find_health_by_date(self, athlete_id: str, record_date: date) -> str | None:
        row = self._conn.execute(
            "SELECT id FROM health_metrics WHERE athlete_id = ? AND date = ?",
            [athlete_id, record_date],
        ).fetchone()
        return str(row[0]) if row else None

    def _update_health_row(self, health_id: str, metrics: dict) -> None:
        for col, val in metrics.items():
            # col é validado contra _HEALTH_METRIC_FIELDS antes de chegar aqui
            self._conn.execute(
                f"UPDATE health_metrics SET {col} = ? WHERE id = ?",
                [val, health_id],
            )

    @staticmethod
    def _activity_insert_params(
        activity_id: str,
        athlete_id: str,
        garmin_id: str | None,
        a: Activity,
    ) -> list:
        return [
            activity_id, athlete_id, garmin_id,
            a.source, a.sport_type, a.started_at,
            a.elapsed_time_s, a.moving_time_s, a.distance_m,
            a.elevation_gain_m, a.avg_power_w, a.normalized_power_w,
            a.avg_hr_bpm, a.avg_cadence_rpm, a.avg_speed_ms,
            a.tss, a.intensity_factor, a.variability_index, a.raw_file_path,
        ]

    @staticmethod
    def _activity_update_params(a: Activity, activity_id: str) -> list:
        return [
            a.source, a.sport_type, a.started_at,
            a.elapsed_time_s, a.moving_time_s, a.distance_m,
            a.elevation_gain_m, a.avg_power_w, a.normalized_power_w,
            a.avg_hr_bpm, a.avg_cadence_rpm, a.avg_speed_ms,
            a.tss, a.intensity_factor, a.variability_index, a.raw_file_path,
            activity_id,
        ]
