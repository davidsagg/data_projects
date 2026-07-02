"""Catalog Store for MusicDNA AI — Module M4.

Provides structured filtering and CSV export over the DuckDB track catalog.
"""

from __future__ import annotations

import csv
from typing import Optional

import duckdb


class CatalogStore:
    """Manages the DuckDB catalog of ingested tracks.

    Attributes:
        db: Open DuckDB connection used for all catalog operations.
    """

    def __init__(self, db_path: str) -> None:
        """Initialises the catalog store and creates the table if absent.

        Args:
            db_path: DuckDB database path, or ``':memory:'`` for an in-memory
                database (useful in tests).
        """
        self.db = duckdb.connect(db_path)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS catalog (
                job_id       VARCHAR PRIMARY KEY,
                file_path    VARCHAR,
                title        VARCHAR,
                artist       VARCHAR,
                genre        VARCHAR,
                bpm          FLOAT,
                mood         VARCHAR,
                key          VARCHAR,
                duration_sec FLOAT,
                sample_rate  INTEGER,
                status       VARCHAR,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter(
        self,
        genre: Optional[str] = None,
        mood: Optional[str] = None,
        bpm_min: Optional[float] = None,
        bpm_max: Optional[float] = None,
        key: Optional[str] = None,
    ) -> list[dict]:
        """Returns catalog rows matching the given filters.

        All parameters are optional and combined with AND logic.  Omitted
        parameters are not applied.

        Args:
            genre: Exact genre match (e.g. ``'jazz'``).
            mood: Exact mood match (e.g. ``'melancolico'``).
            bpm_min: Minimum BPM (inclusive).
            bpm_max: Maximum BPM (inclusive).
            key: Exact musical key match (e.g. ``'C major'``).

        Returns:
            List of dicts with all catalog columns.  Empty list when no rows
            match.
        """
        conditions: list[str] = []
        params: list = []

        if genre is not None:
            conditions.append("genre = ?")
            params.append(genre)
        if mood is not None:
            conditions.append("mood = ?")
            params.append(mood)
        if bpm_min is not None:
            conditions.append("bpm >= ?")
            params.append(float(bpm_min))
        if bpm_max is not None:
            conditions.append("bpm <= ?")
            params.append(float(bpm_max))
        if key is not None:
            conditions.append("key = ?")
            params.append(key)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM catalog {where}"

        cursor = self.db.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def export_csv(self, output_path: str) -> None:
        """Exports the full catalog to a CSV file.

        Args:
            output_path: Filesystem path for the output ``.csv`` file.
        """
        cursor = self.db.execute("SELECT * FROM catalog")
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)
