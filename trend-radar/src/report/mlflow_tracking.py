# src/report/mlflow_tracking.py — MLflow tracking do Trend Radar

import logging
from pathlib import Path

import duckdb
import mlflow

logger = logging.getLogger(__name__)


def run_pipeline_with_tracking(
    conn: duckdb.DuckDBPyConnection,
    mlflow_uri: str,
    week_start: str,
) -> None:
    """Registra params, métricas e tags de uma execução da pipeline no MLflow."""

    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment("trend_radar")

    with mlflow.start_run():
        # Params: pesos e thresholds do modelo
        mlflow.log_params(
            {
                "weight_lastfm":     0.40,
                "weight_youtube":    0.35,
                "weight_deezer":     0.25,
                "anomaly_threshold": 2.5,
                "trend_threshold":   65,
            }
        )

        # Tags de contexto
        mlflow.set_tags(
            {
                "week_start":    week_start,
                "data_sources":  "lastfm,youtube,deezer",
            }
        )

        # Métricas: contagem de artistas em ascensão
        rising_count = conn.execute(
            "SELECT COUNT(*) FROM gold_rising_artists"
        ).fetchone()[0]

        # Contagem de anomalias — tabela pode não existir
        anomalies_count = 0
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM gold_anomalies WHERE week_start = ?",
                [week_start],
            ).fetchone()
            anomalies_count = row[0] if row else 0
        except Exception:
            pass

        mlflow.log_metrics(
            {
                "rising_artists_count": float(rising_count),
                "anomalies_detected":   float(anomalies_count),
            }
        )

        # Artefatos: Markdown e HTML — ignora se arquivos ainda não existem
        for suffix in ("_report.md", "_report.html"):
            artifact_path = Path(f"data/reports/{week_start}{suffix}")
            if artifact_path.exists():
                mlflow.log_artifact(str(artifact_path))
            else:
                logger.warning(
                    "[MLflow] Artefato não encontrado, pulando: %s", artifact_path
                )

    logger.info("[MLflow] Run registrado para semana %s.", week_start)
