"""DAG: Ingestão YouTube — semanal toda segunda-feira às 03:00."""

import sys
from datetime import datetime, timedelta

from airflow.decorators import dag, task


@dag(
    dag_id="ingest_youtube",
    schedule="0 3 * * 1",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ingestion", "youtube"],
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
)
def ingest_youtube():
    @task
    def fetch_and_save():
        sys.path.insert(0, "/opt/airflow")

        import duckdb
        from src.config import settings
        from src.ingestion.youtube_client import YouTubeClient

        conn = duckdb.connect(settings.duckdb_path)
        client = YouTubeClient(api_key=settings.youtube_api_key)
        week_start = datetime.now().strftime("%Y-%m-%d")
        count = client.run(week_start, conn)
        print(f"[YouTube] Inseridos: {count} registros para semana {week_start}")
        conn.close()

    fetch_and_save()


dag = ingest_youtube()
