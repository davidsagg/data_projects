# src/ingestion/base.py — Interface que todos os clientes implementam

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    SOURCE: str  # 'lastfm' | 'youtube' | 'deezer' | 'musicbrainz'

    @abstractmethod
    def fetch_artists(self, week_start: str) -> list[dict[str, Any]]:
        """Busca artistas/métricas para a semana especificada."""
        ...

    @abstractmethod
    def save_to_bronze(self, records: list[dict], conn: duckdb.DuckDBPyConnection) -> int:
        """Salva registros na tabela bronze. Retorna count de registros salvos."""
        ...

    def run(self, week_start: str, conn: duckdb.DuckDBPyConnection) -> int:
        """Método template: fetch → save. Emite log estruturado com timing."""
        t0 = time.perf_counter()
        records = self.fetch_artists(week_start)
        count = self.save_to_bronze(records, conn)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

        # Estado do circuit breaker deste cliente (se existir)
        circuit_state = "n/a"
        try:
            from .circuit_breakers import (
                lastfm_breaker, youtube_breaker, deezer_breaker,
            )
            breakers = {
                "lastfm":      lastfm_breaker,
                "youtube":     youtube_breaker,
                "deezer":      deezer_breaker,
                "musicbrainz": None,
            }
            breaker = breakers.get(getattr(self, "SOURCE", ""))
            if breaker is not None:
                circuit_state = breaker.current_state
        except Exception:
            pass

        logger.info(
            "ingestion_completed",
            extra={
                "source":            getattr(self, "SOURCE", "unknown"),
                "week_start":        week_start,
                "records_fetched":   len(records),
                "records_inserted":  count,
                "duration_ms":       elapsed_ms,
                "circuit_state":     circuit_state,
            },
        )
        return count
