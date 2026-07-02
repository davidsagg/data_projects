"""DAG: Ingestão Deezer — semanal toda segunda-feira às 04:00."""

import sys
from datetime import datetime, timedelta

from airflow.decorators import dag, task


@dag(
    dag_id="ingest_deezer",
    schedule="0 4 * * 1",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ingestion", "deezer"],
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
)
def ingest_deezer():
    @task
    def fetch_and_save():
        sys.path.insert(0, "/opt/airflow")

        import duckdb
        from src.ingestion.deezer_client import DeezerClient

        conn = duckdb.connect("/workspace/data/trend_radar.duckdb")
        client = DeezerClient()
        week_start = datetime.now().strftime("%Y-%m-%d")
        count = client.run(week_start, conn)
        print(f"[Deezer] Inseridos: {count} registros para semana {week_start}")
        conn.close()

    fetch_and_save()


dag = ingest_deezer()
