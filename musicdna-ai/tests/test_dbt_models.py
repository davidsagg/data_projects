"""TDD validation tests for dbt models in /workspace/dbt.

Test cases TC-DBT-001 to TC-DBT-003.
Models already created in dbt/models/marts/ — these tests validate
compilation correctness and SQL structure.
"""

import os
import subprocess

import pytest

DBT_DIR = "/workspace/dbt"


DBT_BIN = "/home/developer/.local/bin/dbt"


def _dbt_run(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        f"cd {DBT_DIR} && {DBT_BIN} {cmd}",
        shell=True,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# TC-DBT-001: dbt project compiles without errors
# ---------------------------------------------------------------------------


def test_dbt_project_compiles_without_errors():
    """TC-DBT-001: dbt compile must exit 0 with no errors."""
    result = _dbt_run("compile")
    assert result.returncode == 0, f"dbt compile falhou:\n{result.stderr}"


# ---------------------------------------------------------------------------
# TC-DBT-002: faixas_por_genero model is valid SQL with GROUP BY
# ---------------------------------------------------------------------------


def test_model_faixas_por_genero_is_valid_sql():
    """TC-DBT-002: faixas_por_genero must compile and contain GROUP BY."""
    result = _dbt_run("compile --select faixas_por_genero")
    assert result.returncode == 0
    target = os.path.join(
        DBT_DIR,
        "target/compiled/musicdna/models/marts/faixas_por_genero.sql",
    )
    if os.path.exists(target):
        sql = open(target).read().upper()
        assert "GROUP BY" in sql


# ---------------------------------------------------------------------------
# TC-DBT-003: ultimas_indexacoes model has required columns and clauses
# ---------------------------------------------------------------------------


def test_model_ultimas_indexacoes_has_correct_columns():
    """TC-DBT-003: ultimas_indexacoes must compile and contain required
    columns, ORDER BY and LIMIT 10."""
    result = _dbt_run("compile --select ultimas_indexacoes")
    assert result.returncode == 0
    target = os.path.join(
        DBT_DIR,
        "target/compiled/musicdna/models/marts/ultimas_indexacoes.sql",
    )
    if os.path.exists(target):
        sql = open(target).read().upper()
        for col in ["JOB_ID", "TITLE", "ARTIST", "GENRE", "CREATED_AT"]:
            assert col in sql, f"Coluna ausente no modelo: {col}"
        assert "ORDER BY" in sql
        assert "LIMIT 10" in sql
