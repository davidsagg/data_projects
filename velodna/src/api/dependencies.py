"""
Dependencies FastAPI — gerencia conexão singleton com DuckDB.
"""
from __future__ import annotations

import duckdb
import os

_conn = None


def get_db():
    """Retorna (e inicializa se necessário) a conexão singleton com DuckDB."""
    global _conn
    if _conn is None:
        _conn = duckdb.connect(os.getenv("DB_PATH", "/workspace/data/velodna.duckdb"))
        from src.ingestion.catalog_store import CatalogStore
        CatalogStore(_conn).initialize_schema()
    return _conn
