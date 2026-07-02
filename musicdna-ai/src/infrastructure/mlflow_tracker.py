"""MLflow tracking utilities for MusicDNA AI — Module M13.

Provides a class-based wrapper around the MLflow fluent API so all pipeline
modules log experiments to a consistent location without repeating boilerplate.
"""

from __future__ import annotations

from typing import Optional

import mlflow


class MLflowTracker:
    """Thin wrapper around the MLflow fluent API.

    Attributes:
        experiment_name: Name of the MLflow experiment.
    """

    EXPERIMENT = "musicdna-ai"
    DEFAULT_URI = "/workspace/mlflow/mlruns"

    def __init__(
        self,
        experiment_name: str = EXPERIMENT,
        tracking_uri: Optional[str] = None,
    ) -> None:
        """Initialises the tracker and configures the MLflow experiment.

        Args:
            experiment_name: Name of the experiment to log runs under.
            tracking_uri: Optional custom tracking URI. Defaults to a local
                file-based store under :attr:`DEFAULT_URI`.
        """
        uri = tracking_uri or f"file://{self.DEFAULT_URI}"
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment_name)
        self.experiment_name = experiment_name

    def start_run(
        self,
        run_name: str,
        params: Optional[dict] = None,
    ) -> None:
        """Inicia um run MLflow com nome e parametros opcionais.

        Args:
            run_name: Human-readable name shown in the MLflow UI.
            params: Optional dict of parameters logged via
                :func:`mlflow.log_params` (values coerced to ``str``).
        """
        active = mlflow.start_run(run_name=run_name)
        if params:
            str_params = {str(k): str(v) for k, v in params.items()}
            mlflow.log_params(str_params)
            # Refresh the ActiveRun snapshot so last_active_run().data reflects
            # the logged params (MLflow stores a static snapshot at start time).
            active._data = mlflow.get_run(active.info.run_id).data

    def log_metrics(self, metrics: dict) -> None:
        """Loga metricas numericas no run ativo.

        Args:
            metrics: Mapping of metric name to numeric value.
        """
        mlflow.log_metrics({k: float(v) for k, v in metrics.items()})
        active = mlflow.active_run()
        if active:
            active._data = mlflow.get_run(active.info.run_id).data

    def log_bpm_comparison(
        self,
        bpm_manual: float,
        bpm_detected: float,
    ) -> None:
        """Loga comparacao entre BPM manual e detectado.

        Args:
            bpm_manual: BPM informado manualmente pelo usuario.
            bpm_detected: BPM detectado automaticamente pelo pipeline.
        """
        self.log_metrics(
            {
                "bpm_manual": bpm_manual,
                "bpm_detected": bpm_detected,
                "bpm_diff": abs(bpm_manual - bpm_detected),
            }
        )

    def end_run(self, status: str = "FINISHED") -> None:
        """Encerra o run ativo com status informado.

        Args:
            status: MLflow run status string (e.g. ``'FINISHED'``,
                ``'FAILED'``, ``'KILLED'``).
        """
        mlflow.end_run(status=status)

    @staticmethod
    def get_or_create() -> "MLflowTracker":
        """Factory singleton para uso no pipeline.

        Returns:
            A new :class:`MLflowTracker` wired to production defaults.
        """
        return MLflowTracker()
