"""DAG: Ingestão Last.fm — semanal toda segunda-feira às 02:00."""

import sys
from datetime import datetime, timedelta

from airflow.decorators import dag, task


@dag(
    dag_id="ingest_lastfm",
    schedule="0 2 * * 1",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ingestion", "lastfm"],
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
)
def ingest_lastfm():
    @task
    def fetch_and_save():
        sys.path.insert(0, "/opt/airflow")

        import duckdb
        from src.config import settings
        from src.ingestion.lastfm_client import LastFmClient

        conn = duckdb.connect(settings.duckdb_path)
        client = LastFmClient(api_key=settings.lastfm_api_key)
        week_start = datetime.now().strftime("%Y-%m-%d")
        count = client.run(week_start, conn)
        print(f"[LastFM] Inseridos: {count} registros para semana {week_start}")
        conn.close()

    fetch_and_save()


dag = ingest_lastfm()
