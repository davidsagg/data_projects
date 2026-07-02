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
  ctl DOUBLE, atl DOUBLE, tsb DOUBLE, ftp_w DOUBLE,
  w_prime_kj DOUBLE, readiness_score DOUBLE, calculated_at TIMESTAMP DEFAULT now());

CREATE TABLE IF NOT EXISTS power_curve (curve_id VARCHAR PRIMARY KEY,
  calculated_date DATE NOT NULL, duration_s INTEGER NOT NULL,
  best_power_w DOUBLE NOT NULL, activity_id VARCHAR REFERENCES activities(activity_id),
  is_all_time BOOLEAN DEFAULT false);
