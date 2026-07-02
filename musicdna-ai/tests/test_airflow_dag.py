"""TDD structural tests for the MusicDNA AI Airflow DAG.

Test cases TC-DAG-001 to TC-DAG-003.
DAG not yet implemented — these tests are expected to fail
until airflow/dags/musicdna_pipeline.py is created.
"""

import os

import pytest

DAG_PATH = "/workspace/airflow/dags"


def _get_dag():
    from airflow.models import DagBag

    bag = DagBag(dag_folder=DAG_PATH, include_examples=False)
    return bag, bag.dags.get("musicdna_pipeline")


# ---------------------------------------------------------------------------
# TC-DAG-001: DAG loads without import errors
# ---------------------------------------------------------------------------


def test_dag_loads_without_errors():
    """TC-DAG-001: DagBag must load musicdna_pipeline with no import errors."""
    bag, dag = _get_dag()
    assert bag.import_errors == {}, f"Erros de importacao: {bag.import_errors}"
    assert dag is not None, "DAG musicdna_pipeline nao encontrada"


# ---------------------------------------------------------------------------
# TC-DAG-002: DAG contains all required tasks
# ---------------------------------------------------------------------------


def test_dag_has_required_tasks():
    """TC-DAG-002: DAG must contain all five required task IDs."""
    _, dag = _get_dag()
    required = {
        "scan_new_files",
        "ingest_audio",
        "extract_features",
        "index_embeddings",
        "update_catalog",
    }
    assert required.issubset(
        set(dag.task_ids)
    ), f"Tasks ausentes: {required - set(dag.task_ids)}"


# ---------------------------------------------------------------------------
# TC-DAG-003: task dependencies follow the expected linear chain
# ---------------------------------------------------------------------------


def test_dag_task_dependencies_correct():
    """TC-DAG-003: tasks must form a linear pipeline:
    scan_new_files >> ingest_audio >> extract_features >>
    index_embeddings >> update_catalog."""
    _, dag = _get_dag()
    deps = {t.task_id: [u.task_id for u in t.upstream_list] for t in dag.tasks}
    assert "scan_new_files" not in deps.get(
        "scan_new_files", []
    ), "scan_new_files nao deve ter upstream"
    assert "scan_new_files" in deps.get("ingest_audio", [])
    assert "ingest_audio" in deps.get("extract_features", [])
    assert "extract_features" in deps.get("index_embeddings", [])
    assert "index_embeddings" in deps.get("update_catalog", [])
