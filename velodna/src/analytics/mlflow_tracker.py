from __future__ import annotations

import mlflow
from datetime import date


class VeloDNATracker:
    """Wrapper MLflow para rastreamento de métricas e experimentos do VeloDNA."""

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
