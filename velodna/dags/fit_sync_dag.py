from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def scan(**ctx):
    import os
    d = os.getenv("FIT_DATA_DIR", "/data/fit")
    files = [f for f in os.listdir(d) if f.endswith(".fit")] if os.path.exists(d) else []
    ctx["ti"].xcom_push(key="files", value=files)
    return files


def parse(**ctx):
    files = ctx["ti"].xcom_pull(key="files")
    if not files:
        return
    import duckdb
    import os
    from pathlib import Path
    from src.ingestion.pipeline import IngestionPipeline
    from src.ingestion.catalog_store import CatalogStore
    conn = duckdb.connect(os.getenv("DB_PATH", "/workspace/data/velodna.duckdb"))
    CatalogStore(conn).initialize_schema()
    p = IngestionPipeline(conn)
    for f in files:
        try:
            p.ingest_fit(Path(os.getenv("FIT_DATA_DIR", "/data/fit")) / f)
        except Exception as e:
            print(f"Skip {f}: {e}")


def update(**ctx):
    import duckdb
    import os
    from datetime import date
    from src.ingestion.catalog_store import CatalogStore
    from src.analytics.pmc_calculator import PMCCalculator
    conn = duckdb.connect(os.getenv("DB_PATH", "/workspace/data/velodna.duckdb"))
    PMCCalculator().run_and_store(CatalogStore(conn), date.today())


with DAG(
    "velodna_fit_sync",
    default_args={
        "owner": "velodna",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    s = PythonOperator(task_id="scan_fit_dir", python_callable=scan)
    p = PythonOperator(task_id="parse_fit_files", python_callable=parse)
    u = PythonOperator(task_id="update_metrics", python_callable=update)
    s >> p >> u
