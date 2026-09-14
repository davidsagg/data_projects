"""
Tracker MLflow do VeloDNA.

O backend de arquivos (`./mlruns`) foi bloqueado pelo MLflow em 2026 — usar
SQLite local mantém o rastreamento offline, sem servidor, e sem depender de
uma feature em fim de vida.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import mlflow

DEFAULT_TRACKING_DB = Path("mlflow/mlflow.db")


def _resolve_tracking_uri() -> str:
    """Retorna a URI de tracking, criando o diretório do SQLite se preciso.

    Returns:
        Valor de `MLFLOW_TRACKING_URI` quando definido; senão um SQLite local.
    """
    uri = os.getenv("MLFLOW_TRACKING_URI")
    if uri:
        return uri
    DEFAULT_TRACKING_DB.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_TRACKING_DB}"


class VeloDNATracker:
    """Wrapper MLflow para rastreamento de métricas e experimentos do VeloDNA."""

    def __init__(self, tracking_uri: str | None = None) -> None:
        """Args:
            tracking_uri: backend de tracking; resolvido do ambiente se omitido.
        """
        mlflow.set_tracking_uri(tracking_uri or _resolve_tracking_uri())

    def log_ftp(self, ftp_w: float, method: str = "best_20min_95pct") -> None:
        """Registra uma detecção de FTP como experimento MLflow.

        Args:
            ftp_w: Potência FTP estimada em watts.
            method: Método utilizado para a estimativa.
        """
        mlflow.set_experiment("velodna_ftp_detection")
        with mlflow.start_run():
            mlflow.log_param("method", method)
            mlflow.log_metric("ftp_w", ftp_w)

    def log_power_curve(self, curve: dict[int, float], d: date) -> None:
        """Registra a curva de potência (MMP) de uma data específica.

        Args:
            curve: Dicionário {duração_s: melhor_potência_w}.
            d: Data da curva.
        """
        mlflow.set_experiment("velodna_power_curve")
        with mlflow.start_run():
            mlflow.log_param("date", str(d))
            for dur, pw in curve.items():
                mlflow.log_metric(f"power_{dur}s", pw)

    def log_pmc(self, ctl: float, atl: float, tsb: float, d: date) -> None:
        """Registra as métricas PMC (CTL, ATL, TSB) de uma data.

        Args:
            ctl: Carga de treino crônica (fitness).
            atl: Carga de treino aguda (fadiga).
            tsb: Balance de stress de treino (forma).
            d: Data das métricas.
        """
        mlflow.set_experiment("velodna_pmc")
        with mlflow.start_run():
            mlflow.log_param("date", str(d))
            mlflow.log_metric("ctl", ctl)
            mlflow.log_metric("atl", atl)
            mlflow.log_metric("tsb", tsb)
