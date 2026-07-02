# src/trend_engine/genre_heatmap.py — Heatmap de tendência por gênero

import logging
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


class GenreHeatmap:
    def __init__(self, conn: duckdb.DuckDBPyConnection, min_artists: int = 3) -> None:
        self.conn = conn
        self.min_artists = min_artists

    def compute(self, week_start: str | None = None, weeks: int = 12) -> list[dict[str, Any]]:
        """Calcula o heatmap de tendência por gênero para a semana informada.

        Caminho produção: lê de gold_genre_heatmap (calculado pelo dbt).
        Fallback (testes em memória): JOIN gold_trend_scores + silver_artists.

        Returns:
            Lista de dicts com genre, week_start, avg_trend_score, artist_count,
            trending_direction. Apenas gêneros com >= min_artists artistas distintos.
        """
        # ── Caminho produção ────────────────────────────────────────────────
        try:
            # Usa a semana mais recente disponível no gold, ou a solicitada
            gold_week_row = self.conn.execute(
                "SELECT MAX(week_start) FROM gold_genre_heatmap"
            ).fetchone()
            gold_week = (
                gold_week_row[0]
                if (gold_week_row and gold_week_row[0] is not None)
                else None
            )

            if gold_week is not None:
                effective_week = week_start if week_start is not None else gold_week
                gold_rows = self.conn.execute(
                    """
                    SELECT genre, avg_trend_score, artist_count, trending_direction
                    FROM gold_genre_heatmap
                    WHERE week_start = ? AND artist_count >= ?
                    """,
                    [effective_week, self.min_artists],
                ).fetchall()

                if not gold_rows:
                    # Semana solicitada não tem dados — usa a mais recente
                    gold_rows = self.conn.execute(
                        """
                        SELECT genre, avg_trend_score, artist_count, trending_direction
                        FROM gold_genre_heatmap
                        WHERE week_start = ? AND artist_count >= ?
                        """,
                        [gold_week, self.min_artists],
                    ).fetchall()
                    effective_week = gold_week

                if gold_rows:
                    logger.info(
                        "[GenreHeatmap] %d gêneros de gold_genre_heatmap para %s.",
                        len(gold_rows), effective_week,
                    )
                    return [
                        {
                            "genre":              r[0],
                            "week_start":         str(effective_week),
                            "avg_trend_score":    r[1],
                            "artist_count":       r[2],
                            "trending_direction": r[3],
                        }
                        for r in gold_rows
                    ]
        except Exception:
            pass  # tabela não existe em ambiente de testes — usa fallback abaixo

        # ── Fallback (testes em memória) ────────────────────────────────────
        # Resolve semana atual a partir de gold_trend_scores
        if week_start is None:
            row = self.conn.execute(
                "SELECT MAX(week_start) FROM gold_trend_scores"
            ).fetchone()
            week_start = row[0] if (row and row[0] is not None) else None
        if week_start is None:
            return []

        current_rows = self.conn.execute(
            """
            SELECT
                sa.genre,
                AVG(gt.trend_score)            AS avg_score,
                COUNT(DISTINCT gt.artist_mbid) AS artist_count
            FROM gold_trend_scores gt
            JOIN silver_artists sa ON sa.artist_mbid = gt.artist_mbid
            WHERE gt.week_start = ?
              AND gt.trend_score IS NOT NULL
              AND sa.genre IS NOT NULL
            GROUP BY sa.genre
            HAVING COUNT(DISTINCT gt.artist_mbid) >= ?
            """,
            [week_start, self.min_artists],
        ).fetchall()

        if not current_rows:
            return []

        prev_row = self.conn.execute(
            "SELECT MAX(week_start) FROM gold_trend_scores WHERE week_start < ?",
            [week_start],
        ).fetchone()
        prev_week_start = prev_row[0] if (prev_row and prev_row[0] is not None) else None

        prev_scores: dict[str, float] = {}
        if prev_week_start:
            for genre, avg_prev, _ in self.conn.execute(
                """
                SELECT sa.genre, AVG(gt.trend_score), COUNT(DISTINCT gt.artist_mbid)
                FROM gold_trend_scores gt
                JOIN silver_artists sa ON sa.artist_mbid = gt.artist_mbid
                WHERE gt.week_start = ? AND gt.trend_score IS NOT NULL AND sa.genre IS NOT NULL
                GROUP BY sa.genre
                """,
                [prev_week_start],
            ).fetchall():
                prev_scores[genre] = avg_prev

        results: list[dict[str, Any]] = []
        for genre, avg_score, artist_count in current_rows:
            prev = prev_scores.get(genre)
            if prev is None:
                direction = "stable"
            else:
                delta = avg_score - prev
                if delta > 5:
                    direction = "up"
                elif delta < -5:
                    direction = "down"
                else:
                    direction = "stable"

            results.append({
                "genre":              genre,
                "week_start":         str(week_start),
                "avg_trend_score":    avg_score,
                "artist_count":       artist_count,
                "trending_direction": direction,
            })

        logger.info(
            "[GenreHeatmap] %d gêneros computados para semana %s.", len(results), week_start
        )
        return results

    def to_dataframe(self, weeks: int = 12):
        """Pivot: index=genre, columns=week_start, values=avg_trend_score."""
        import pandas as pd

        records = self.compute(weeks=weeks)
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records).pivot(
            index="genre", columns="week_start", values="avg_trend_score"
        )
