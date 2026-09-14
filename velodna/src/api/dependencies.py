"""
Dependencies FastAPI — conexão singleton com DuckDB e atleta corrente.
"""
from __future__ import annotations

import os

import duckdb

DEFAULT_DB_PATH = "data/velodna.duckdb"

_conn: duckdb.DuckDBPyConnection | None = None


def get_db() -> duckdb.DuckDBPyConnection:
    """Retorna um cursor próprio da requisição sobre o catálogo.

    **Não devolver a conexão compartilhada.** Os routers montam os nomes das
    colunas lendo `db.description` depois do `execute`, e esse atributo pertence
    à conexão, não ao resultado: com uma conexão só, duas requisições
    simultâneas se intercalam e uma monta o dicionário com as colunas da outra —
    a resposta sai com os dados de um endpoint sob os nomes de campo de outro,
    silenciosamente. `cursor()` cria uma conexão-filha independente sobre o
    mesmo banco, o que isola cada requisição.
    """
    global _conn
    if _conn is None:
        _conn = duckdb.connect(os.getenv("DB_PATH", DEFAULT_DB_PATH))
        from storage.catalog_store import CatalogStore

        CatalogStore(_conn).initialize_schema()
    return _conn.cursor()


def get_athlete_id(db: duckdb.DuckDBPyConnection | None = None) -> str | None:
    """Retorna o UUID do atleta corrente.

    Usa `VELODNA_ATHLETE_ID` quando definido; caso contrário, cai para o único
    atleta cadastrado. A plataforma é single-user por design (privacidade
    primeiro), mas o schema é multi-atleta — este é o ponto de amarração.

    Args:
        db: conexão a consultar quando a variável de ambiente não está definida.

    Returns:
        UUID do atleta, ou None se não houver atleta cadastrado.
    """
    env_id = os.getenv("VELODNA_ATHLETE_ID")
    if env_id:
        return env_id

    conn = db or get_db()
    row = conn.execute("SELECT id FROM athletes ORDER BY created_at LIMIT 1").fetchone()
    return str(row[0]) if row else None


def reset_connection() -> None:
    """Descarta a conexão singleton — usado pelos testes entre fixtures."""
    global _conn
    _conn = None
