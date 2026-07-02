"""DAG: Pipeline completo do Trend Radar — toda segunda-feira às 06:00.
Logging estruturado JSON ativado via setup_logging() em cada task.

Dependência de agendamento (não sensor):
  - ingest_lastfm   02:00
  - ingest_youtube  03:00
  - ingest_deezer   04:00
  → run_dbt_pipeline 06:00  (2h de margem após a última ingestão)
"""

import subprocess
import sys
from datetime import datetime, timedelta

from airflow.decorators import dag, task

_DBT_DIR = "/opt/airflow/dbt"
_DB_PATH = "/workspace/data/trend_radar.duckdb"
_MLFLOW_URI = "http://trend-radar-mlflow:5000"
_REPORTS_DIR = "/workspace/data/reports"


def _dbt(select: str) -> None:
    result = subprocess.run(
        [
            "dbt", "run",
            "--select", select,
            "--project-dir", _DBT_DIR,
            "--profiles-dir", _DBT_DIR,
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"dbt run --select {select} falhou (rc={result.returncode})")


@dag(
    dag_id="run_dbt_pipeline",
    schedule="0 6 * * 1",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["pipeline", "dbt", "gold"],
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=10),
        "retry_exponential_backoff": True,
    },
)
def run_dbt_pipeline():

    @task
    def dbt_run_bronze():
        _dbt("bronze")

    @task
    def dbt_run_silver():
        _dbt("silver")

    @task
    def dbt_run_gold():
        _dbt("gold")

    @task
    def dbt_test():
        result = subprocess.run(
            [
                "dbt", "test",
                "--project-dir", _DBT_DIR,
                "--profiles-dir", _DBT_DIR,
            ],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            raise RuntimeError(f"dbt test falhou (rc={result.returncode})")

    @task
    def run_anomaly_detection():
        sys.path.insert(0, "/opt/airflow")
        from src.utils.logging_config import setup_logging
        setup_logging()
        import duckdb
        from src.trend_engine.anomaly import AnomalyDetector

        week_start = datetime.now().strftime("%Y-%m-%d")
        conn = duckdb.connect(_DB_PATH)
        count = AnomalyDetector(conn).run(week_start)
        print(f"[AnomalyDetector] {count} anomalias detectadas para {week_start}")
        conn.close()

    @task
    def generate_alerts():
        sys.path.insert(0, "/opt/airflow")
        import duckdb
        from pathlib import Path
        from src.report.alerts import AlertEngine

        week_start = datetime.now().strftime("%Y-%m-%d")
        conn = duckdb.connect(_DB_PATH)
        alert_path = Path(f"/workspace/data/alerts/{week_start}_alerts.json")
        alerts = AlertEngine(conn, output_path=alert_path).run(week_start)
        print(f"[AlertEngine] {len(alerts)} alertas gerados para {week_start}")
        conn.close()

    @task
    def generate_report():
        sys.path.insert(0, "/opt/airflow")
        import duckdb
        from src.report.generator import ReportGenerator

        week_start = datetime.now().strftime("%Y-%m-%d")
        conn = duckdb.connect(_DB_PATH)
        generator = ReportGenerator(conn)
        generator.generate_and_save(week_start=week_start, data_dir=_REPORTS_DIR)
        generator.generate_html_report(week_start=week_start, data_dir=_REPORTS_DIR)
        print(f"[ReportGenerator] Relatório MD + HTML salvos para semana {week_start}")
        conn.close()

    @task
    def validate_data_quality():
        sys.path.insert(0, "/opt/airflow")
        from src.db.connection import get_optimized_connection
        from src.quality.expectations import validate_bronze_lastfm

        week_start = datetime.now().strftime("%Y-%m-%d")
        conn = get_optimized_connection(_DB_PATH)
        result = validate_bronze_lastfm(conn, week_start)
        conn.close()

        if not result["success"]:
            raise ValueError(f"[GE] Data quality failed: {result['failed']}")
        print(f"[GE] Qualidade OK — {result['stats']}")

    @task
    def log_mlflow():
        sys.path.insert(0, "/opt/airflow")
        import duckdb
        from src.report.mlflow_tracking import run_pipeline_with_tracking

        week_start = datetime.now().strftime("%Y-%m-%d")
        conn = duckdb.connect(_DB_PATH)
        run_pipeline_with_tracking(
            conn=conn,
            mlflow_uri=_MLFLOW_URI,
            week_start=week_start,
        )
        print(f"[MLflow] Run registrado para semana {week_start}")
        conn.close()

    # ------------------------------------------------------------------
    # Grafo de dependências
    # ------------------------------------------------------------------

    bronze  = dbt_run_bronze()
    silver  = dbt_run_silver()
    gold    = dbt_run_gold()
    tests   = dbt_test()
    dq      = validate_data_quality()
    anomaly = run_anomaly_detection()
    alerts  = generate_alerts()
    report  = generate_report()
    mlflow_ = log_mlflow()

    bronze >> silver >> gold >> tests >> dq >> [anomaly, alerts, report] >> mlflow_


dag = run_dbt_pipeline()
