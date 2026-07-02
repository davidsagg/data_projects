# src/db/connection.py — Factory de conexão DuckDB otimizada

import os
import logging

import duckdb

logger = logging.getLogger(__name__)

# Configuráveis via variável de ambiente para facilitar testes e ambientes distintos
_THREADS = int(os.environ.get("DUCKDB_THREADS", "8"))
_MEMORY_LIMIT = os.environ.get("DUCKDB_MEMORY_LIMIT", "8GB")
_TEMP_DIR = os.environ.get("DUCKDB_TEMP_DIR", "")


def get_optimized_connection(
    path: str,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Abre uma conexão DuckDB com pragmas otimizados para o Trend Radar.

    Configurações aplicadas:
    - threads=8         → usa todos os P-cores do M2
    - memory_limit=8GB  → evita spill desnecessário para disco
    - temp_directory    → diretório de trabalho para joins grandes (se configurado)

    Parâmetros via variáveis de ambiente:
        DUCKDB_THREADS       (padrão: 8)
        DUCKDB_MEMORY_LIMIT  (padrão: 8GB)
        DUCKDB_TEMP_DIR      (padrão: não configurado)
    """
    conn = duckdb.connect(path, read_only=read_only)
    conn.execute(f"PRAGMA threads={_THREADS}")
    conn.execute(f"PRAGMA memory_limit='{_MEMORY_LIMIT}'")
    if _TEMP_DIR:
        conn.execute(f"PRAGMA temp_directory='{_TEMP_DIR}'")
        os.makedirs(_TEMP_DIR, exist_ok=True)
    logger.debug(
        "[DB] Conexão otimizada: path=%s threads=%d memory=%s",
        path, _THREADS, _MEMORY_LIMIT,
    )
    return conn
