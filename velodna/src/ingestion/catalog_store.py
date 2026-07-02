import uuid
import duckdb
from datetime import date, datetime
from src.ingestion.fit_parser import Activity
from src.ingestion.garmin_health_client import HealthDaily

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS activities (activity_id VARCHAR PRIMARY KEY,
  strava_id BIGINT, garmin_id VARCHAR UNIQUE, sport_type VARCHAR NOT NULL,
  start_time TIMESTAMP NOT NULL, duration_s INTEGER NOT NULL,
  distance_m DOUBLE, elevation_m DOUBLE, avg_power_w DOUBLE,
  max_power_w DOUBLE, avg_hr_bpm DOUBLE, max_hr_bpm INTEGER,
  tss DOUBLE, np_w DOUBLE, ftp_w_at_time DOUBLE,
  fit_file_path VARCHAR, created_at TIMESTAMP DEFAULT now());
CREATE TABLE IF NOT EXISTS activity_streams (stream_id VARCHAR PRIMARY KEY,
  activity_id VARCHAR NOT NULL REFERENCES activities(activity_id),
  timestamp TIMESTAMP NOT NULL, power_w INTEGER, heart_rate_bpm INTEGER,
  cadence_rpm INTEGER, speed_ms DOUBLE, altitude_m DOUBLE,
  lat DOUBLE, lon DOUBLE, distance_m DOUBLE, temperature_c DOUBLE);
CREATE TABLE IF NOT EXISTS health_daily (date DATE PRIMARY KEY,
  sleep_duration_h DOUBLE, sleep_score INTEGER, deep_sleep_min INTEGER,
  rem_sleep_min INTEGER, hrv_rmssd_ms DOUBLE, hrv_status VARCHAR,
  resting_hr_bpm INTEGER, stress_avg INTEGER, body_battery_max INTEGER,
  body_battery_min INTEGER, steps INTEGER, vo2max_estimated DOUBLE,
  weight_kg DOUBLE, source VARCHAR DEFAULT 'garmin_connect');
CREATE TABLE IF NOT EXISTS routes (route_id VARCHAR PRIMARY KEY,
  name VARCHAR NOT NULL, source VARCHAR NOT NULL, gpx_file_path VARCHAR,
  distance_m DOUBLE, elevation_gain_m DOUBLE, elevation_loss_m DOUBLE,
  max_gradient_pct DOUBLE, avg_gradient_pct DOUBLE, difficulty_score DOUBLE,
  created_at TIMESTAMP DEFAULT now());
CREATE TABLE IF NOT EXISTS route_segments (segment_id VARCHAR PRIMARY KEY,
  route_id VARCHAR NOT NULL REFERENCES routes(route_id),
  sequence INTEGER NOT NULL, segment_type VARCHAR, length_m DOUBLE,
  elevation_delta_m DOUBLE, avg_gradient_pct DOUBLE, recommended_power_w DOUBLE);
CREATE TABLE IF NOT EXISTS athlete_metrics (date DATE PRIMARY KEY,
  ctl DOUBLE, atl DOUBLE, tsb DOUBLE, ftp_w DOUBLE, w_prime_kj DOUBLE,
  readiness_score DOUBLE, calculated_at TIMESTAMP DEFAULT now());
CREATE TABLE IF NOT EXISTS power_curve (curve_id VARCHAR PRIMARY KEY,
  calculated_date DATE NOT NULL, duration_s INTEGER NOT NULL,
  best_power_w DOUBLE NOT NULL,
  activity_id VARCHAR REFERENCES activities(activity_id),
  is_all_time BOOLEAN DEFAULT false);
CREATE TABLE IF NOT EXISTS ai_insights (
  id VARCHAR PRIMARY KEY, athlete_id VARCHAR, activity_id VARCHAR,
  insight_type VARCHAR, content TEXT, model VARCHAR,
  confidence_score DOUBLE, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS ai_conversations (
  id VARCHAR PRIMARY KEY, athlete_id VARCHAR, session_id VARCHAR,
  role VARCHAR, content TEXT, model VARCHAR,
  created_at TIMESTAMPTZ DEFAULT now());
"""


class CatalogStore:
    def __init__(self, conn): self.conn = conn

    def initialize_schema(self):
        for stmt in SCHEMA_SQL.strip().split(";"):
            if stmt.strip(): self.conn.execute(stmt.strip())

    def upsert_activity(self, activity: Activity, activity_id: str):
        # DuckDB exige ON CONFLICT (col) explícito quando há múltiplos constraints únicos
        self.conn.execute("""INSERT INTO activities
            (activity_id,garmin_id,sport_type,start_time,duration_s,
             distance_m,elevation_m,avg_power_w,max_power_w,
             avg_hr_bpm,max_hr_bpm,fit_file_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (activity_id) DO UPDATE SET
                garmin_id=EXCLUDED.garmin_id,
                sport_type=EXCLUDED.sport_type,
                start_time=EXCLUDED.start_time,
                duration_s=EXCLUDED.duration_s,
                distance_m=EXCLUDED.distance_m,
                elevation_m=EXCLUDED.elevation_m,
                avg_power_w=EXCLUDED.avg_power_w,
                max_power_w=EXCLUDED.max_power_w,
                avg_hr_bpm=EXCLUDED.avg_hr_bpm,
                max_hr_bpm=EXCLUDED.max_hr_bpm,
                fit_file_path=EXCLUDED.fit_file_path""",
            [activity_id, activity.garmin_id, activity.sport_type,
             activity.start_time, activity.duration_s, activity.distance_m,
             activity.elevation_m, activity.avg_power_w, activity.max_power_w,
             activity.avg_hr_bpm, activity.max_hr_bpm, activity.fit_file_path])

        # Correção 1: inserir streams se existirem (necessário para o teste de integração)
        if activity.streams:
            rows = [
                (str(uuid.uuid4()), activity_id,
                 s.timestamp, s.power_w, s.heart_rate_bpm, s.cadence_rpm,
                 s.speed_ms, s.altitude_m, s.lat, s.lon,
                 s.distance_m, s.temperature_c)
                for s in activity.streams
            ]
            self.conn.executemany("""INSERT INTO activity_streams
                (stream_id,activity_id,timestamp,power_w,heart_rate_bpm,
                 cadence_rpm,speed_ms,altitude_m,lat,lon,distance_m,temperature_c)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", rows)

    def upsert_health_daily(self, health: HealthDaily):
        self.conn.execute("""INSERT OR REPLACE INTO health_daily
            (date,sleep_duration_h,sleep_score,deep_sleep_min,rem_sleep_min,
             hrv_rmssd_ms,hrv_status,resting_hr_bpm,stress_avg,
             body_battery_max,body_battery_min,vo2max_estimated,source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [health.date, health.sleep_duration_h, health.sleep_score,
             health.deep_sleep_min, health.rem_sleep_min, health.hrv_rmssd_ms,
             health.hrv_status, health.resting_hr_bpm, health.stress_avg,
             health.body_battery_max, health.body_battery_min,
             health.vo2max_estimated, health.source])

    def upsert_route(self, route_data: dict, segments: list = None):
        self.conn.execute("""INSERT OR REPLACE INTO routes
            (route_id,name,source,distance_m,elevation_gain_m,elevation_loss_m)
            VALUES (?,?,?,?,?,?)""",
            [route_data["route_id"], route_data["name"], route_data["source"],
             route_data.get("distance_m"), route_data.get("elevation_gain_m"),
             route_data.get("elevation_loss_m")])
        for seg in (segments or []):
            self.insert_segment(seg)

    def insert_segment(self, seg: dict):
        # Correção 2: DuckDB 1.5.2 enforça FK constraints — exceção levantada automaticamente
        # quando route_id não existe em routes. Nenhuma validação manual necessária.
        self.conn.execute("""INSERT INTO route_segments
            (segment_id,route_id,sequence,segment_type,length_m,
             elevation_delta_m,avg_gradient_pct)
            VALUES (?,?,?,?,?,?,?)""",
            [seg["segment_id"], seg["route_id"], seg["sequence"],
             seg.get("segment_type"), seg.get("length_m"),
             seg.get("elevation_delta_m"), seg.get("avg_gradient_pct")])

    def upsert_athlete_metrics(self, target_date, ctl, atl, tsb,
                               ftp_w=None, w_prime_kj=None):
        self.conn.execute("""INSERT OR REPLACE INTO athlete_metrics
            (date,ctl,atl,tsb,ftp_w,w_prime_kj) VALUES (?,?,?,?,?,?)""",
            [target_date, ctl, atl, tsb, ftp_w, w_prime_kj])

    def upsert_power_curve(self, calculated_date, duration_s,
                           best_power_w, activity_id=None):
        self.conn.execute("""INSERT OR REPLACE INTO power_curve
            (curve_id,calculated_date,duration_s,best_power_w,activity_id)
            VALUES (?,?,?,?,?)""",
            [str(uuid.uuid4()), calculated_date, duration_s,
             best_power_w, activity_id])

    def get_activities(self, start: date = None, end: date = None) -> list:
        q, params = "SELECT * FROM activities WHERE 1=1", []
        if start:
            q += " AND start_time >= ?"
            params.append(datetime.combine(start, datetime.min.time()))
        if end:
            q += " AND start_time <= ?"
            params.append(datetime.combine(end, datetime.max.time()))
        q += " ORDER BY start_time DESC"
        rows = self.conn.execute(q, params).fetchall()
        cols = [d[0] for d in self.conn.description]
        return [dict(zip(cols, r)) for r in rows]

    def get_weekly_tss(self, year: int, month: int) -> dict:
        rows = self.conn.execute("""
            SELECT WEEK(start_time) AS w, SUM(tss)
            FROM activities
            WHERE YEAR(start_time)=? AND MONTH(start_time)=? AND tss IS NOT NULL
            GROUP BY w ORDER BY w""", [year, month]).fetchall()
        return {str(r[0]): r[1] for r in rows}
