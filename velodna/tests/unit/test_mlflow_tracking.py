import pytest
import mlflow
import json
from pathlib import Path


@pytest.fixture(autouse=True)
def mlenv(tmp_path):
    mlflow.set_tracking_uri(f"file://{tmp_path}/mlruns")
    yield
    mlflow.end_run()


def test_mlflow_logs_ftp():
    mlflow.set_experiment("velodna_ftp_detection")
    with mlflow.start_run():
        mlflow.log_metric("ftp_w", 285.5)
    runs = mlflow.search_runs(experiment_names=["velodna_ftp_detection"])
    assert len(runs) >= 1 and runs.iloc[0]["metrics.ftp_w"] == pytest.approx(285.5)


def test_mlflow_logs_artifact(tmp_path):
    mlflow.set_experiment("velodna_power_curve")
    with mlflow.start_run():
        f = tmp_path / "pc.json"
        f.write_text(json.dumps({300: 320.0}))
        mlflow.log_artifact(str(f))
        rid = mlflow.active_run().info.run_id
    assert any("pc" in a.path for a in mlflow.tracking.MlflowClient().list_artifacts(rid))


def test_mlflow_experiment_by_name():
    mlflow.set_experiment("velodna_pmc")
    with mlflow.start_run():
        mlflow.log_metric("ctl", 55.2)
    exp = mlflow.get_experiment_by_name("velodna_pmc")
    assert exp is not None and exp.experiment_id is not None
