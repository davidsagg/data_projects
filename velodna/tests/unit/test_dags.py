import pytest

airflow = pytest.importorskip("airflow", reason="apache-airflow não instalado — skipping DAG tests")


def test_dag_fit_sync_tasks():
    from airflow.models import DagBag
    db = DagBag(dag_folder="dags/", include_examples=False)
    assert "velodna_fit_sync" in db.dags
    ids = {t.task_id for t in db.dags["velodna_fit_sync"].tasks}
    assert "scan_fit_dir" in ids and "parse_fit_files" in ids and "update_metrics" in ids


def test_dag_fit_sync_daily():
    from airflow.models import DagBag
    dag = DagBag("dags/", include_examples=False).dags["velodna_fit_sync"]
    sched = str(getattr(dag, "schedule", None) or getattr(dag, "schedule_interval", None))
    assert sched in ["@daily", "0 0 * * *", "<Cron '0 0 * * *'>"]


def test_dag_health_sync_exists():
    from airflow.models import DagBag
    db = DagBag("dags/", include_examples=False)
    assert "velodna_health_sync" in db.dags
    assert db.dags["velodna_health_sync"].dag_id == "velodna_health_sync"
