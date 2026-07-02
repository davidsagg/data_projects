# src/ingestion/youtube_client.py — Cliente YouTube Data API v3

import logging
from datetime import datetime, timezone
from typing import Any

import duckdb
import googleapiclient.discovery
from googleapiclient.errors import HttpError

from .base import BaseAPIClient
from .circuit_breakers import youtube_breaker

logger = logging.getLogger(__name__)

QUOTA_SEARCH   = 100   # unidades por search.list
QUOTA_CHANNELS = 1     # unidades por channels.list (batch de até 50)

CREATE_CHANNEL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bronze_youtube_channel_weekly (
    id                  VARCHAR PRIMARY KEY,
    week_start          DATE        NOT NULL,
    artist_name         VARCHAR     NOT NULL,
    channel_id          VARCHAR,
    channel_title       VARCHAR,
    subscriber_count    BIGINT,
    video_count         BIGINT,
    view_count          BIGINT,
    weekly_views        BIGINT,
    topic_categories    VARCHAR[],
    thumbnail_url       VARCHAR,
    source              VARCHAR     NOT NULL DEFAULT 'youtube',
    ingested_at         TIMESTAMPTZ NOT NULL
);
"""

CREATE_CACHE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bronze_youtube_artist_channel_cache (
    artist_name     VARCHAR PRIMARY KEY,
    channel_id      VARCHAR,
    cached_at       TIMESTAMPTZ NOT NULL
);
"""


class QuotaExceededError(Exception):
    """Levantada quando a quota diária estimada seria ultrapassada."""


class YouTubeClient(BaseAPIClient):
    SOURCE = "youtube"
    QUOTA_LIMIT = 8_000

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("[YouTube] api_key não pode ser vazio.")
        self._service = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=api_key, cache_discovery=False
        )
        self._quota_used = 0
        logger.info("[YouTube] Cliente inicializado.")

    @property
    def quota_used(self) -> int:
        return self._quota_used

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _ensure_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(CREATE_CHANNEL_TABLE_SQL)
        conn.execute(CREATE_CACHE_TABLE_SQL)

    def _cache_get(self, conn: duckdb.DuckDBPyConnection, artist_name: str) -> tuple[bool, str | None]:
        """Retorna (found, channel_id). found=True mesmo quando channel_id é None (artist sem canal cacheado)."""
        row = conn.execute(
            "SELECT channel_id FROM bronze_youtube_artist_channel_cache WHERE artist_name = ?",
            [artist_name],
        ).fetchone()
        if row is None:
            return False, None
        return True, row[0]

    def _cache_set(self, conn: duckdb.DuckDBPyConnection, artist_name: str, channel_id: str | None) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO bronze_youtube_artist_channel_cache VALUES (?, ?, ?)",
            [artist_name, channel_id, datetime.now(tz=timezone.utc).isoformat()],
        )

    # ------------------------------------------------------------------
    # Chamadas HTTP protegidas pelo circuit breaker
    # ------------------------------------------------------------------

    @youtube_breaker
    def _call_search(self, artist_name: str) -> dict:
        """search.list protegido pelo circuit breaker (100 unidades/req)."""
        return (
            self._service.search()
            .list(q=artist_name, part="snippet", type="channel",
                  videoCategoryId="10", maxResults=1)
            .execute()
        )

    @youtube_breaker
    def _call_channels(self, channel_ids: list[str]) -> dict:
        """channels.list protegido pelo circuit breaker."""
        return (
            self._service.channels()
            .list(id=",".join(channel_ids), part="snippet,statistics,topicDetails")
            .execute()
        )

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def _search_channel(self, artist_name: str) -> str | None:
        """Busca channel_id via search.list (100 unidades). Retorna None se não encontrado."""
        if self._quota_used + QUOTA_SEARCH > self.QUOTA_LIMIT:
            raise QuotaExceededError(
                f"[YouTube] Quota de {self.QUOTA_LIMIT} unidades seria excedida."
            )
        self._quota_used += QUOTA_SEARCH
        try:
            resp = self._call_search(artist_name)
        except HttpError as exc:
            logger.warning("[YouTube] Erro na search para '%s': %s", artist_name, exc)
            return None

        items = resp.get("items", [])
        if not items:
            return None
        return items[0]["snippet"]["channelId"]

    def _fetch_channels_stats(self, channel_ids: list[str]) -> dict[str, dict]:
        """Busca stats de até 50 canais por chamada (1 unidade cada batch)."""
        result: dict[str, dict] = {}
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i: i + 50]
            # channels.list custa 1u por batch — não contabilizado no tracker de quota
            # para simplificar o controle (search.list a 100u/req é o custo dominante)
            try:
                resp = self._call_channels(batch)
            except HttpError as exc:
                logger.warning("[YouTube] Erro ao buscar stats de canais: %s", exc)
                continue
            for item in resp.get("items", []):
                result[item["id"]] = item
        return result

    # ------------------------------------------------------------------
    # Contrato BaseAPIClient
    # ------------------------------------------------------------------

    def fetch_artists(self, week_start: str, artist_names: list[str] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError("Use run() diretamente — fetch_artists requer conn para o cache.")

    def run(self, week_start: str, conn: duckdb.DuckDBPyConnection,
            artist_names: list[str] | None = None) -> int:
        """Override do template: resolve cache → search → stats → save."""
        self._ensure_tables(conn)

        if not artist_names:
            logger.warning("[YouTube] run() chamado sem artist_names.")
            return 0

        ingested_at = datetime.now(tz=timezone.utc).isoformat()
        records: list[dict[str, Any]] = []

        # Fase 1: resolver channel_ids (cache ou search)
        artist_to_channel: dict[str, str | None] = {}
        for name in artist_names:
            cached, channel_id = self._cache_get(conn, name)
            if cached:
                logger.debug("[YouTube] Cache hit para '%s' → %s", name, channel_id)
                artist_to_channel[name] = channel_id
                continue
            try:
                channel_id = self._search_channel(name)
            except QuotaExceededError:
                logger.warning("[YouTube] Quota esgotada após %d artistas.", len(artist_to_channel))
                break
            self._cache_set(conn, name, channel_id)
            artist_to_channel[name] = channel_id

        # Fase 2: buscar stats dos canais encontrados em batch
        found_channels = {n: cid for n, cid in artist_to_channel.items() if cid}
        stats_by_channel: dict[str, dict] = {}
        if found_channels:
            stats_by_channel = self._fetch_channels_stats(list(found_channels.values()))

        # Fase 3: montar registros (incluindo artistas sem canal)
        channel_to_artist = {cid: name for name, cid in found_channels.items()}

        for artist_name, channel_id in artist_to_channel.items():
            if channel_id and channel_id in stats_by_channel:
                item       = stats_by_channel[channel_id]
                snippet    = item.get("snippet", {})
                stats      = item.get("statistics", {})
                topics     = item.get("topicDetails", {})
                view_count = int(stats.get("viewCount", 0) or 0)
                thumbnail  = (snippet.get("thumbnails", {}).get("high") or {}).get("url")
                records.append({
                    "id":               f"{channel_id}::{week_start}",
                    "week_start":       week_start,
                    "artist_name":      artist_name,
                    "channel_id":       channel_id,
                    "channel_title":    snippet.get("title"),
                    "subscriber_count": int(stats.get("subscriberCount", 0) or 0),
                    "video_count":      int(stats.get("videoCount", 0) or 0),
                    "view_count":       view_count,
                    "weekly_views":     view_count,   # baseline na 1ª semana
                    "topic_categories": topics.get("topicCategories", []),
                    "thumbnail_url":    thumbnail,
                    "source":           self.SOURCE,
                    "ingested_at":      ingested_at,
                })
            else:
                # Artista sem canal → placeholder com nulls
                records.append({
                    "id":               f"{artist_name}::{week_start}",
                    "week_start":       week_start,
                    "artist_name":      artist_name,
                    "channel_id":       None,
                    "channel_title":    None,
                    "subscriber_count": 0,
                    "video_count":      0,
                    "view_count":       0,
                    "weekly_views":     0,
                    "topic_categories": [],
                    "thumbnail_url":    None,
                    "source":           self.SOURCE,
                    "ingested_at":      ingested_at,
                })

        logger.info("[YouTube] %d registros montados. Quota usada: %d u.", len(records), self._quota_used)
        return self.save_to_bronze(records, conn)

    def save_to_bronze(self, records: list[dict], conn: duckdb.DuckDBPyConnection) -> int:
        if not records:
            return 0

        conn.execute(CREATE_CHANNEL_TABLE_SQL)

        insert_sql = """
            INSERT OR REPLACE INTO bronze_youtube_channel_weekly
                (id, week_start, artist_name, channel_id, channel_title,
                 subscriber_count, video_count, view_count, weekly_views,
                 topic_categories, thumbnail_url, source, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = [
            (r["id"], r["week_start"], r["artist_name"], r["channel_id"],
             r["channel_title"], r["subscriber_count"], r["video_count"],
             r["view_count"], r["weekly_views"], r["topic_categories"],
             r["thumbnail_url"], r["source"], r["ingested_at"])
            for r in records
        ]
        conn.executemany(insert_sql, rows)
        logger.info("[YouTube] %d registros salvos.", len(rows))
        return len(rows)
