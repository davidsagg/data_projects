"""DAG: Ingestão MusicBrainz — mensal no dia 1 de cada mês às 00:00."""

import sys
from datetime import datetime, timedelta

from airflow.decorators import dag, task


@dag(
    dag_id="ingest_musicbrainz",
    schedule="0 0 1 * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ingestion", "musicbrainz"],
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
)
def ingest_musicbrainz():
    @task
    def fetch_and_save():
        sys.path.insert(0, "/opt/airflow")

        import duckdb
        from src.ingestion.musicbrainz_client import MusicBrainzClient

        conn = duckdb.connect("/workspace/data/trend_radar.duckdb")
        client = MusicBrainzClient()
        week_start = datetime.now().strftime("%Y-%m-%d")
        count = client.run(week_start, conn)
        print(f"[MusicBrainz] Inseridos: {count} registros para referência {week_start}")
        conn.close()

    fetch_and_save()


dag = ingest_musicbrainz()
