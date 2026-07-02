# src/ingestion/lastfm_client.py — Cliente Last.fm para ingestão semanal de artistas

import logging
from datetime import datetime, timezone
from typing import Any

import duckdb
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from .base import BaseAPIClient
from .circuit_breakers import lastfm_breaker

logger = logging.getLogger(__name__)

LASTFM_BASE_URL = "https://ws.audioscrobbler.com/2.0/"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bronze_lastfm_artist_weekly (
    id                  VARCHAR PRIMARY KEY,
    week_start          DATE        NOT NULL,
    artist_name         VARCHAR     NOT NULL,
    mbid                VARCHAR,
    listeners           BIGINT,
    playcount           BIGINT,
    chart_rank          INTEGER,
    tags                VARCHAR[],
    bio_summary         VARCHAR,
    lastfm_url          VARCHAR,
    source              VARCHAR     NOT NULL DEFAULT 'lastfm',
    ingested_at         TIMESTAMPTZ NOT NULL
);
"""


class LastFmAuthError(Exception):
    """Levantada quando a API retorna 403 — api_key inválida ou sem permissão."""


def _is_retryable(exc: BaseException) -> bool:
    """Retry em 429 e erros de rede; não retenta outros 4xx."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


class LastFmClient(BaseAPIClient):
    SOURCE = "lastfm"
    BASE_URL = LASTFM_BASE_URL

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("[LastFM] api_key não pode ser vazio.")
        self._api_key = api_key
        self._http = httpx.Client(timeout=30.0)
        logger.info("[LastFM] Cliente inicializado.")

    # ------------------------------------------------------------------
    # Chamadas HTTP
    # ------------------------------------------------------------------

    @lastfm_breaker
    def _call_api(self, params: dict[str, Any]):
        """Chamada HTTP protegida pelo circuit breaker."""
        return self._http.get(self.BASE_URL, params=params)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=5, max=60),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    def _get(self, params: dict[str, Any]) -> dict:
        full_params = {**params, "api_key": self._api_key, "format": "json"}
        response = self._call_api(full_params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                raise LastFmAuthError(
                    "[LastFM] API key inválida ou sem permissão (HTTP 403)."
                ) from exc
            raise  # 429 → tenacity faz retry; outros → propagam
        return response.json()

    def _fetch_top_artists(self, limit: int = 200) -> list[dict]:
        logger.info("[LastFM] Buscando top %d artistas (chart.getTopArtists).", limit)
        data = self._get({"method": "chart.getTopArtists", "limit": limit})
        artists = data.get("artists", {}).get("artist", [])
        logger.info("[LastFM] %d artistas recebidos do chart.", len(artists))
        return artists

    def _fetch_artist_detail(self, artist_name: str) -> dict:
        logger.debug("[LastFM] Buscando info de '%s' (artist.getInfo).", artist_name)
        try:
            data = self._get({"method": "artist.getInfo", "artist": artist_name, "autocorrect": 1})
            return data.get("artist", {})
        except Exception:
            logger.warning("[LastFM] Falha ao buscar detalhes de '%s'. Usando {}.", artist_name)
            return {}

    # ------------------------------------------------------------------
    # Contrato BaseAPIClient
    # ------------------------------------------------------------------

    def fetch_artists(self, week_start: str) -> list[dict[str, Any]]:
        logger.info("[LastFM] Iniciando fetch para semana %s.", week_start)
        top_artists = self._fetch_top_artists(limit=200)
        ingested_at = datetime.now(tz=timezone.utc).isoformat()
        records: list[dict[str, Any]] = []

        for rank, artist in enumerate(top_artists, start=1):
            name = artist.get("name", "")
            info = self._fetch_artist_detail(name)
            tags = [t["name"] for t in (info.get("tags", {}).get("tag") or [])][:5]

            records.append({
                "id":          f"{name}::{week_start}",
                "week_start":  week_start,
                "artist_name": name,
                "mbid":        info.get("mbid") or artist.get("mbid") or None,
                "listeners":   int(info.get("stats", {}).get("listeners", 0) or 0),
                "playcount":   int(info.get("stats", {}).get("playcount", 0) or 0),
                "chart_rank":  rank,
                "tags":        tags,
                "bio_summary": (info.get("bio", {}).get("summary") or "").strip() or None,
                "lastfm_url":  info.get("url") or artist.get("url") or None,
                "source":      self.SOURCE,
                "ingested_at": ingested_at,
            })

        logger.info("[LastFM] %d registros montados para semana %s.", len(records), week_start)
        return records

    def save_to_bronze(self, records: list[dict], conn: duckdb.DuckDBPyConnection) -> int:
        if not records:
            logger.warning("[LastFM] Nenhum registro para salvar.")
            return 0

        conn.execute(CREATE_TABLE_SQL)

        insert_sql = """
            INSERT OR REPLACE INTO bronze_lastfm_artist_weekly
                (id, week_start, artist_name, mbid, listeners, playcount,
                 chart_rank, tags, bio_summary, lastfm_url, source, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = [
            (
                r["id"], r["week_start"], r["artist_name"], r["mbid"],
                r["listeners"], r["playcount"], r["chart_rank"], r["tags"],
                r["bio_summary"], r["lastfm_url"], r["source"], r["ingested_at"],
            )
            for r in records
        ]
        conn.executemany(insert_sql, rows)
        logger.info("[LastFM] inseridos=%d", len(rows))
        return len(rows)
