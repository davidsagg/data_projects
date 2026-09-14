"""
Auxiliar de consulta — linhas como dicionários, com os nomes de coluna certos.

Ler `conn.description` depois de um `execute` é frágil: o atributo pertence à
conexão e reflete o **último** comando executado nela, não o resultado que se
tem em mãos. Com requisições concorrentes sobre a mesma conexão, uma consulta
monta a resposta com os nomes de coluna de outra — silenciosamente, sem erro.

Passando pelo objeto de resultado devolvido por `execute`, os nomes vêm sempre
da consulta certa. Este módulo mora em `storage/` para que tanto a API quanto
`planning/` possam usá-lo sem inverter a direção das dependências.
"""
from __future__ import annotations

from typing import Any


def rows(db, sql: str, params: list | None = None) -> list[dict[str, Any]]:
    """Executa uma consulta e devolve as linhas como dicionários.

    Args:
        db: conexão ou cursor DuckDB.
        sql: comando SQL.
        params: parâmetros posicionais.

    Returns:
        Uma lista de dicionários {coluna: valor}.
    """
    result = db.execute(sql, params or [])
    columns = [d[0] for d in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def row(db, sql: str, params: list | None = None) -> dict[str, Any] | None:
    """Executa uma consulta e devolve a primeira linha como dicionário.

    Args:
        db: conexão ou cursor DuckDB.
        sql: comando SQL.
        params: parâmetros posicionais.

    Returns:
        Dicionário da primeira linha, ou None se não houver resultado.
    """
    result = db.execute(sql, params or [])
    columns = [d[0] for d in result.description]
    found = result.fetchone()
    return dict(zip(columns, found)) if found else None
