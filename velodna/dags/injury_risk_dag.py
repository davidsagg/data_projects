"""
DAG: velodna_injury_risk — avalia risco de lesão por overuse semanalmente.

Executa toda segunda-feira e persiste o resultado em ai_insights.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def assess_injury_risk(**ctx):
    import os
    import uuid

    import duckdb
    import requests

    db_path = os.getenv("DB_PATH", "/workspace/data/velodna.duckdb")
    conn = duckdb.connect(db_path)

    from src.storage.catalog_store import CatalogStore

    CatalogStore(conn).initialize_schema()

    from datetime import date, timedelta

    today = date.today()

    metrics_row = conn.execute(
        "SELECT tsb FROM athlete_metrics ORDER BY date DESC LIMIT 1"
    ).fetchone()
    tsb = float(metrics_row[0]) if metrics_row else 0.0

    tss_by_week: list[float] = []
    dist_by_week: list[float] = []
    for week_offset in range(4, -1, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * week_offset)
        week_end = week_start + timedelta(days=6)
        row = conn.execute(
            "SELECT COALESCE(SUM(tss), 0), COALESCE(SUM(distance_m), 0) / 1000.0 "
            "FROM activities "
            "WHERE CAST(start_time AS DATE) BETWEEN ? AND ? AND tss IS NOT NULL",
            [week_start, week_end],
        ).fetchone()
        tss_by_week.append(float(row[0]) if row else 0.0)
        dist_by_week.append(float(row[1]) if row else 0.0)

    from src.ai.injury_risk_coach import InjuryRiskCoach
    from src.ai.ollama_client import OllamaClient, OllamaUnavailableError

    coach = InjuryRiskCoach(OllamaClient())
    factors = coach.assess_factors(tss_by_week, dist_by_week, tsb)

    try:
        assessment = coach.generate_assessment(factors)
    except OllamaUnavailableError:
        assessment = (
            f"[Ollama indisponível] Risco: {factors.risk_level}. "
            f"Fatores: {'; '.join(factors.triggered_factors) or 'nenhum'}"
        )

    insight_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO ai_insights (id, insight_type, content, model, created_at) "
        "VALUES (?, 'injury_risk', ?, 'llama3', now())",
        [insight_id, assessment],
    )
    conn.close()

    print(f"Injury risk assessment saved: {insight_id} | level={factors.risk_level}")
    return {"risk_level": factors.risk_level, "insight_id": insight_id}


with DAG(
    dag_id="velodna_injury_risk",
    description="Avalia risco de lesão por overuse semanalmente",
    schedule="0 7 * * 1",  # toda segunda-feira às 07:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["velodna", "health", "ai"],
) as dag:
    assess = PythonOperator(
        task_id="assess_injury_risk",
        python_callable=assess_injury_risk,
    )
