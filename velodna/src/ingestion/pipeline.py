import uuid
import duckdb
from pathlib import Path

from src.ingestion.fit_parser import FITParser
from src.ingestion.catalog_store import CatalogStore


class IngestionPipeline:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._store = CatalogStore(conn)

    def ingest_fit(self, path: Path) -> str:
        """Parseia arquivo FIT e persiste atividade + streams no DuckDB."""
        activity = FITParser().parse(path)
        activity_id = str(uuid.uuid4())
        self._store.upsert_activity(activity, activity_id)
        return activity_id
