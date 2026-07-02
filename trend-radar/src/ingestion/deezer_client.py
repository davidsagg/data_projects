# src/ingestion/deezer_client.py — Cliente Deezer API para ingestão semanal de artistas

import logging
import time
from datetime import datetime, timezone
from typing import Any

import duckdb
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from .base import BaseAPIClient
from .circuit_breakers import deezer_breaker

logger = logging.getLogger(__name__)

DEEZER_BASE_URL = "https://api.deezer.com"
REQUEST_SLEEP   = 0.5   # segundos entre requests (API pública sem rate limit publicado)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bronze_deezer_artist_weekly (
    id              VARCHAR PRIMARY KEY,
    week_start      DATE        NOT NULL,
    artist_name     VARCHAR     NOT NULL,
    deezer_id       BIGINT      NOT NULL,
    nb_fan          BIGINT,
    nb_album        INTEGER,
    chart_position  INTEGER,
    radio           BOOLEAN,
    tracklist_url   VARCHAR,
    deezer_url      VARCHAR,
    picture_url     VARCHAR,
    source          VARCHAR     NOT NULL DEFAULT 'deezer',
    ingested_at     TIMESTAMPTZ NOT NULL
);
"""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


class DeezerClient(BaseAPIClient):
    SOURCE   = "deezer"
    BASE_URL = DEEZER_BASE_URL

    def __init__(self) -> None:
        self._http = httpx.Client(timeout=30.0)
        logger.info("[Deezer] Cliente inicializado (sem autenticação).")

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    @deezer_breaker
    def _call_api(self, url: str, params: dict[str, Any]):
        """Chamada HTTP protegida pelo circuit breaker."""
        return self._http.get(url, params=params)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=5, max=60),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        url  = f"{self.BASE_URL}{path}"
        resp = self._call_api(url, params or {})
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            code = data["error"].get("code")
            msg  = data["error"].get("message", "unknown")
            raise httpx.HTTPStatusError(
                message=f"[Deezer] API error {code}: {msg}",
                request=resp.request,
                response=resp,
            )
        return data

    def _fetch_global_chart(self, limit: int = 200) -> list[dict]:
        logger.info("[Deezer] Buscando chart global top %d.", limit)
        data = self._get("/chart/0/artists", params={"limit": limit})
        artists = data.get("data", [])
        logger.info("[Deezer] %d artistas recebidos do chart.", len(artists))
        return artists

    # ------------------------------------------------------------------
    # Contrato BaseAPIClient
    # ------------------------------------------------------------------

    def fetch_artists(self, week_start: str, artist_names: list[str] | None = None) -> list[dict[str, Any]]:
        ingested_at = datetime.now(tz=timezone.utc).isoformat()

        try:
            chart_artists = self._fetch_global_chart(limit=200)
        except Exception:
            logger.exception("[Deezer] Falha ao buscar chart. Retornando vazio.")
            return []

        records: list[dict[str, Any]] = []
        for position, artist in enumerate(chart_artists, start=1):
            # sleep respeitoso entre cada artista (TC-10 exige >= 2 sleeps com >= 0.5)
            time.sleep(REQUEST_SLEEP)

            records.append({
                "id":            f"{artist['id']}::{week_start}",
                "week_start":    week_start,
                "artist_name":   artist.get("name", ""),
                "deezer_id":     artist.get("id"),
                "nb_fan":        artist.get("nb_fan"),
                "nb_album":      artist.get("nb_album"),
                "chart_position": position,
                "radio":         artist.get("radio"),
                "tracklist_url": artist.get("tracklist"),
                "deezer_url":    artist.get("link"),
                "picture_url":   (artist.get("picture_xl")
                                  or artist.get("picture_big")
                                  or artist.get("picture")),
                "source":        self.SOURCE,
                "ingested_at":   ingested_at,
            })

        logger.info("[Deezer] %d registros montados para semana %s.", len(records), week_start)
        return records

    def save_to_bronze(self, records: list[dict], conn: duckdb.DuckDBPyConnection) -> int:
        if not records:
            logger.warning("[Deezer] Nenhum registro para salvar.")
            return 0

        conn.execute(CREATE_TABLE_SQL)

        insert_sql = """
            INSERT OR REPLACE INTO bronze_deezer_artist_weekly
                (id, week_start, artist_name, deezer_id, nb_fan, nb_album,
                 chart_position, radio, tracklist_url, deezer_url,
                 picture_url, source, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = [
            (r["id"], r["week_start"], r["artist_name"], r["deezer_id"],
             r["nb_fan"], r["nb_album"], r["chart_position"], r["radio"],
             r["tracklist_url"], r["deezer_url"], r["picture_url"],
             r["source"], r["ingested_at"])
            for r in records
        ]
        conn.executemany(insert_sql, rows)
        logger.info("[Deezer] %d registros salvos.", len(rows))
        return len(rows)
