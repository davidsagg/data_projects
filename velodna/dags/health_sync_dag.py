from datetime import datetime
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def sync_health(**ctx):
    """Sincroniza as métricas de saúde do dia a partir do Garmin Connect."""
    import os
    from datetime import date

    import duckdb

    from ingestion.garmin_health_client import GarminHealthClient
    from storage.catalog_store import CatalogStore

    email = os.getenv("GARMIN_EMAIL", "")
    password = os.getenv("GARMIN_PASSWORD", "")
    if not email or not password:
        print("Credenciais do Garmin não configuradas — nada a sincronizar")
        return

    conn = duckdb.connect(os.getenv("DB_PATH", "data/velodna.duckdb"))
    row = conn.execute("SELECT id FROM athletes ORDER BY created_at LIMIT 1").fetchone()
    if row is None:
        print("Nenhum atleta cadastrado — nada a sincronizar")
        return

    daily = GarminHealthClient(email, password).get_health_daily(date.today())
    CatalogStore(conn).insert_health_daily(
        str(row[0]),
        daily.date,
        hrv_rmssd_ms=daily.hrv_rmssd_ms,
        hrv_status=daily.hrv_status,
        resting_hr_bpm=daily.resting_hr_bpm,
        sleep_hours=daily.sleep_duration_h,
        sleep_quality_score=daily.sleep_score,
        deep_sleep_min=daily.deep_sleep_min,
        rem_sleep_min=daily.rem_sleep_min,
        body_battery=daily.body_battery_max,
        body_battery_min=daily.body_battery_min,
        stress_level=daily.stress_avg,
        vo2max_estimated=daily.vo2max_estimated,
        source=daily.source,
    )


with DAG(
    "velodna_health_sync",
    default_args={"owner": "velodna", "retries": 1},
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    PythonOperator(task_id="sync_garmin_health", python_callable=sync_health)
