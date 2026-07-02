from datetime import datetime
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def sync_health(**ctx):
    import duckdb
    import os
    from datetime import date
    from src.ingestion.catalog_store import CatalogStore
    from src.ingestion.garmin_health_client import GarminHealthClient
    e = os.getenv("GARMIN_EMAIL", "")
    pw = os.getenv("GARMIN_PASSWORD", "")
    if not e or not pw:
        print("Garmin creds not set")
        return
    conn = duckdb.connect(os.getenv("DB_PATH", "/workspace/data/velodna.duckdb"))
    CatalogStore(conn).upsert_health_daily(
        GarminHealthClient(e, pw).get_health_daily(date.today())
    )


with DAG(
    "velodna_health_sync",
    default_args={"owner": "velodna", "retries": 1},
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    PythonOperator(task_id="sync_garmin_health", python_callable=sync_health)
