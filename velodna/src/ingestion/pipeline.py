"""
Pipeline de ingestão — arquivo `.fit` para atividade persistida no catálogo.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from ingestion.fit_parser import FITParser
from storage.catalog_store import CatalogStore
from storage.models import activity_from_fit


class IngestionPipeline:
    """Orquestra parse, conversão para o modelo de domínio e persistência."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Args:
            conn: conexão DuckDB já aberta sobre o catálogo.
        """
        self._conn = conn
        self._store = CatalogStore(conn)

    def ingest_fit(self, path: Path, athlete_id: str | None = None) -> str:
        """Parseia um arquivo FIT e persiste atividade + streams.

        Args:
            path: caminho do arquivo `.fit`.
            athlete_id: dono da atividade; resolvido automaticamente se omitido.

        Returns:
            UUID da atividade persistida.

        Raises:
            ValueError: se não houver atleta cadastrado para associar a atividade.
        """
        athlete_id = athlete_id or self._store.resolve_athlete_id()
        activity = activity_from_fit(FITParser().parse(path))

        activity_id = self._store.upsert_activity(
            activity, athlete_id, garmin_id=activity.garmin_id
        )
        self._store.insert_streams(activity_id, activity.streams)
        return activity_id
