# src/api/repository.py — Acesso aos dados para a API Trend Radar

import logging
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


class TrendRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self.conn = conn

    def get_trending(
        self,
        genre: str | None = None,
        country: str | None = None,
        limit: int = 20,
        week: str | None = None,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retorna (página de artistas, total_count) ordenados por trend_score DESC.

        Retorna ([], 0) se nenhum resultado.
        """
        conditions: list[str] = []
        params: list[Any] = []

        if genre:
            conditions.append("list_contains(genres, LOWER(?))")
            params.append(genre.lower())
        if country:
            conditions.append("country = ?")
            params.append(country)
        if week:
            conditions.append("week_start = ?")
            params.append(week)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # Contagem total para metadados de paginação
        count_row = self.conn.execute(
            f"SELECT COUNT(*) FROM gold_rising_artists {where}",
            params,
        ).fetchone()
        total_count: int = count_row[0] if count_row else 0

        sql = f"""
            SELECT artist_mbid,
                   name                                  AS artist_name,
                   array_to_string(genres, ', ')         AS genre,
                   country,
                   trend_score,
                   trending_direction,
                   week_start
            FROM gold_rising_artists
            {where}
            ORDER BY trend_score DESC
            LIMIT ? OFFSET ?
        """
        rows = self.conn.execute(sql, params + [limit, offset]).fetchall()
        cols = ["artist_mbid", "artist_name", "genre", "country",
                "trend_score", "trending_direction", "week_start"]
        return [dict(zip(cols, row)) for row in rows], total_count

    def get_artist_history(
        self, mbid: str, weeks: int = 12
    ) -> dict[str, Any] | None:
        """Retorna info do artista + histórico de trend_score.

        Retorna None se o artista não for encontrado.
        """
        # Verifica existência e busca nome via silver_artists
        artist_row = self.conn.execute(
            """
            SELECT sa.name
            FROM gold_trend_scores gts
            JOIN silver_artists sa ON sa.mbid = gts.artist_mbid
            WHERE gts.artist_mbid = ?
            LIMIT 1
            """,
            [mbid],
        ).fetchone()

        if not artist_row:
            return None

        history_rows = self.conn.execute(
            """
            SELECT week_start, trend_score, score_lastfm, score_youtube, score_deezer
            FROM gold_trend_scores
            WHERE artist_mbid = ?
            ORDER BY week_start DESC
            LIMIT ?
            """,
            [mbid, weeks],
        ).fetchall()

        history = [
            {
                "week_start":    str(r[0]),
                "trend_score":   r[1],
                "score_lastfm":  r[2],
                "score_youtube": r[3],
                "score_deezer":  r[4],
            }
            for r in history_rows
        ]

        return {
            "artist_mbid":        mbid,
            "artist_name":        artist_row[0],
            "history":            history,
            "forecast_available": len(history) >= 12,
        }
