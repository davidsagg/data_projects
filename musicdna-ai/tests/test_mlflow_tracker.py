"""TDD tests for src/infrastructure/mlflow_tracker.py — MLflow Tracker.

Test cases TC-MLF-001 to TC-MLF-004.
Production module not yet implemented — these tests are expected to fail
until MLflowTracker is created.
"""

import os
import tempfile

import mlflow
import pytest


@pytest.fixture(autouse=True)
def mlflow_test_env(tmp_path):
    """Isola cada teste em um tracking URI temporario."""
    tracking_uri = f"file://{tmp_path}/mlruns"
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("test-experiment")
    yield tracking_uri
    # Garantir que nao ha run ativo apos o teste:
    if mlflow.active_run():
        mlflow.end_run()


# ---------------------------------------------------------------------------
# TC-MLF-001: log run with params
# ---------------------------------------------------------------------------


def test_tracker_logs_run_with_params():
    """TC-MLF-001: start_run must log params as strings in MLflow."""
    from src.infrastructure.mlflow_tracker import MLflowTracker

    tracker = MLflowTracker(experiment_name="test-experiment")
    tracker.start_run("test_ingest", params={"sample_rate": 22050, "n_mfcc": 20})
    run = mlflow.last_active_run()
    assert run is not None
    assert run.data.params.get("sample_rate") == "22050"
    assert run.data.params.get("n_mfcc") == "20"
    tracker.end_run()


# ---------------------------------------------------------------------------
# TC-MLF-002: log metrics
# ---------------------------------------------------------------------------


def test_tracker_logs_metrics():
    """TC-MLF-002: log_metrics must persist float metrics in the active run."""
    from src.infrastructure.mlflow_tracker import MLflowTracker

    tracker = MLflowTracker(experiment_name="test-experiment")
    tracker.start_run("test_metrics")
    tracker.log_metrics({"processing_time_sec": 2.5, "embedding_dim": 512})
    run = mlflow.last_active_run()
    assert run.data.metrics.get("processing_time_sec") == 2.5
    assert run.data.metrics.get("embedding_dim") == 512
    tracker.end_run()


# ---------------------------------------------------------------------------
# TC-MLF-003: log BPM comparison
# ---------------------------------------------------------------------------


def test_tracker_logs_bpm_comparison():
    """TC-MLF-003: log_bpm_comparison must log bpm_manual, bpm_detected and
    bpm_diff (absolute difference)."""
    from src.infrastructure.mlflow_tracker import MLflowTracker

    tracker = MLflowTracker(experiment_name="test-experiment")
    tracker.start_run("test_bpm")
    tracker.log_bpm_comparison(bpm_manual=120.0, bpm_detected=118.5)
    run = mlflow.last_active_run()
    assert "bpm_manual" in run.data.metrics
    assert "bpm_detected" in run.data.metrics
    assert "bpm_diff" in run.data.metrics
    assert abs(run.data.metrics["bpm_diff"] - 1.5) < 0.01
    tracker.end_run()


# ---------------------------------------------------------------------------
# TC-MLF-004: end run sets status
# ---------------------------------------------------------------------------


def test_tracker_end_run_sets_status():
    """TC-MLF-004: end_run must close the active run with the given status."""
    from src.infrastructure.mlflow_tracker import MLflowTracker

    tracker = MLflowTracker(experiment_name="test-experiment")
    tracker.start_run("test_end")
    run_id = mlflow.active_run().info.run_id
    tracker.end_run(status="FINISHED")
    assert mlflow.active_run() is None
    finished = mlflow.get_run(run_id)
    assert finished.info.status == "FINISHED"
