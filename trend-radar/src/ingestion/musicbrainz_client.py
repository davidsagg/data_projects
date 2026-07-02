# src/ingestion/musicbrainz_client.py — Cliente MusicBrainz para enriquecimento de artistas

import logging
import time
from datetime import datetime, timezone
from typing import Any

import duckdb
import musicbrainzngs

from .base import BaseAPIClient

logger = logging.getLogger(__name__)

RATE_LIMIT_SLEEP = 1.1  # MusicBrainz: máximo 1 req/s por política

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bronze_musicbrainz_artist_weekly (
    id              VARCHAR PRIMARY KEY,
    week_start      DATE        NOT NULL,
    artist_name     VARCHAR     NOT NULL,
    mbid            VARCHAR     NOT NULL,
    sort_name       VARCHAR,
    disambiguation  VARCHAR,
    artist_type     VARCHAR,
    gender          VARCHAR,
    country         VARCHAR,
    area            VARCHAR,
    begin_date      DATE,
    end_date        DATE,
    tags            VARCHAR[],
    source          VARCHAR     NOT NULL DEFAULT 'musicbrainz',
    ingested_at     TIMESTAMPTZ NOT NULL
);
"""


class MusicBrainzClient(BaseAPIClient):
    SOURCE = "musicbrainz"

    def __init__(self) -> None:
        musicbrainzngs.set_useragent("TrendRadar", "1.0", "trend-radar@portfolio.dev")
        logger.info("[MusicBrainz] Cliente inicializado.")

    # ------------------------------------------------------------------
    # Contrato BaseAPIClient
    # ------------------------------------------------------------------

    def fetch_artists(self, week_start: str, mbids: list[str] | None = None) -> list[dict[str, Any]]:
        if not mbids:
            logger.warning("[MusicBrainz] Nenhum mbid fornecido.")
            return []

        ingested_at = datetime.now(tz=timezone.utc).isoformat()
        records: list[dict[str, Any]] = []

        for mbid in mbids:
            time.sleep(RATE_LIMIT_SLEEP)   # respeita rate limit MusicBrainz (1 req/s)
            try:
                result = musicbrainzngs.get_artist_by_id(mbid, includes=["tags", "aliases"])
                artist = result.get("artist", {})
            except Exception:
                logger.warning("[MusicBrainz] Falha ao buscar mbid '%s'. Pulando.", mbid)
                continue

            tags = [t["name"] for t in (artist.get("tag-list") or [])][:5]

            life_span = artist.get("life-span", {})
            begin_raw = life_span.get("begin")
            end_raw   = life_span.get("end")

            records.append({
                "id":             f"{mbid}::{week_start}",
                "week_start":     week_start,
                "artist_name":    artist.get("name", ""),
                "mbid":           mbid,
                "sort_name":      artist.get("sort-name"),
                "disambiguation": artist.get("disambiguation"),
                "artist_type":    artist.get("type"),
                "gender":         artist.get("gender"),
                "country":        artist.get("country"),
                "area":           (artist.get("area") or {}).get("name"),
                "begin_date":     begin_raw if begin_raw and len(begin_raw) == 10 else None,
                "end_date":       end_raw   if end_raw   and len(end_raw)   == 10 else None,
                "tags":           tags,
                "source":         self.SOURCE,
                "ingested_at":    ingested_at,
            })

        logger.info("[MusicBrainz] %d registros montados para semana %s.", len(records), week_start)
        return records

    def run(self, week_start: str, conn: duckdb.DuckDBPyConnection,
            mbids: list[str] | None = None) -> int:
        """Override do template para aceitar mbids."""
        records = self.fetch_artists(week_start, mbids=mbids)
        return self.save_to_bronze(records, conn)

    def save_to_bronze(self, records: list[dict], conn: duckdb.DuckDBPyConnection) -> int:
        if not records:
            logger.warning("[MusicBrainz] Nenhum registro para salvar.")
            return 0

        conn.execute(CREATE_TABLE_SQL)

        insert_sql = """
            INSERT OR REPLACE INTO bronze_musicbrainz_artist_weekly
                (id, week_start, artist_name, mbid, sort_name, disambiguation,
                 artist_type, gender, country, area, begin_date, end_date,
                 tags, source, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = [
            (r["id"], r["week_start"], r["artist_name"], r["mbid"],
             r["sort_name"], r["disambiguation"], r["artist_type"], r["gender"],
             r["country"], r["area"], r["begin_date"], r["end_date"],
             r["tags"], r["source"], r["ingested_at"])
            for r in records
        ]
        conn.executemany(insert_sql, rows)
        logger.info("[MusicBrainz] %d registros salvos.", len(rows))
        return len(rows)
