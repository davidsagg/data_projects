"""profile_baseline.py — Medição de performance baseline do Trend Radar.

Execute:
    python scripts/profile_baseline.py

O JSON gerado é o baseline para comparação pós-otimização.
"""

import json
import os
import sys
import time

# Garante que src/ está no path quando executado da raiz do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb

from src.db.connection import get_optimized_connection
from src.trend_engine.anomaly import AnomalyDetector
from src.trend_engine.genre_heatmap import GenreHeatmap

# Em produção (Docker): /workspace/data/trend_radar.duckdb
# Localmente: ajuste para o path real
DB_PATH = os.environ.get(
    "TREND_RADAR_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "trend_radar.duckdb"),
)

conn = get_optimized_connection(DB_PATH, read_only=False)
results: dict = {}

# 1. Query gold_trend_scores (query mais pesada)
start = time.perf_counter()
conn.execute("SELECT * FROM gold_trend_scores ORDER BY trend_score DESC").fetchall()
results["gold_trend_scores_ms"] = round((time.perf_counter() - start) * 1000, 1)

# 2. Query gold_rising_artists com JOIN silver_artists
start = time.perf_counter()
conn.execute(
    """
    SELECT a.name, s.trend_score, a.tags, a.country
    FROM gold_rising_artists s
    JOIN silver_artists a ON s.artist_mbid = a.mbid
    ORDER BY s.trend_score DESC
    LIMIT 20
    """
).fetchall()
results["rising_artists_join_ms"] = round((time.perf_counter() - start) * 1000, 1)

# 3. GenreHeatmap.compute()
start = time.perf_counter()
GenreHeatmap(conn).compute(weeks=12)
results["heatmap_compute_ms"] = round((time.perf_counter() - start) * 1000, 1)

# 4. AnomalyDetector.run() com dados reais
start = time.perf_counter()
AnomalyDetector(conn).run(week_start="2026-04-14")
results["anomaly_detection_ms"] = round((time.perf_counter() - start) * 1000, 1)

# 5. Tamanho do arquivo DuckDB
results["db_size_mb"] = round(os.path.getsize(DB_PATH) / 1024**2, 1)

conn.close()

print(json.dumps(results, indent=2))
