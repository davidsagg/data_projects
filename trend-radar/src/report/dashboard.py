# src/report/dashboard.py — Helper Streamlit para o Trend Radar

import logging
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


def build_ranking_df(conn: duckdb.DuckDBPyConnection):
    """Retorna DataFrame com o ranking de artistas em ascensão.

    Colunas garantidas: artist_name, genre, trend_score, trending_direction.
    """
    import pandas as pd

    rows = conn.execute(
        """
        SELECT artist_mbid,
               name                             AS artist_name,
               array_to_string(genres, ', ')    AS genre,
               country,
               trend_score,
               trending_direction,
               week_start
        FROM gold_rising_artists
        ORDER BY trend_score DESC
        """
    ).fetchall()

    cols = [
        "artist_mbid", "artist_name", "genre", "country",
        "trend_score", "trending_direction", "week_start",
    ]
    df = pd.DataFrame(rows, columns=cols)
    logger.info("[Dashboard] build_ranking_df: %d artistas carregados.", len(df))
    return df
