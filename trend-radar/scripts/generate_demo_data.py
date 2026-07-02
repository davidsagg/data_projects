"""generate_demo_data.py — Dados sintéticos realistas para demonstração.

Execute:
    python3.13 scripts/generate_demo_data.py
    make dbt-run dbt-test

Gera 12 semanas de histórico para 10 artistas brasileiros nas 3 fontes.
Emicida e Criolo têm spike viral nas últimas 2 semanas (demonstra anomalias).
"""

import json
import os
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import get_optimized_connection

random.seed(42)

# ---------------------------------------------------------------------------
# Artistas reais brasileiros
# ---------------------------------------------------------------------------

ARTISTS = [
    {"name": "Emicida",      "mbid": "mbid-001", "country": "BR", "genres": ["hip-hop", "rap"]},
    {"name": "Alcyone",      "mbid": "mbid-002", "country": "BR", "genres": ["samba", "mpb"]},
    {"name": "Criolo",       "mbid": "mbid-003", "country": "BR", "genres": ["hip-hop", "mpb"]},
    {"name": "Anitta",       "mbid": "mbid-004", "country": "BR", "genres": ["funk", "pop"]},
    {"name": "Gilberto Gil", "mbid": "mbid-005", "country": "BR", "genres": ["mpb", "axe"]},
    {"name": "Mc Hariel",    "mbid": "mbid-006", "country": "BR", "genres": ["funk"]},
    {"name": "BK",           "mbid": "mbid-007", "country": "BR", "genres": ["rap"]},
    {"name": "Luisa Sonza",  "mbid": "mbid-008", "country": "BR", "genres": ["pop"]},
    {"name": "Xamã",         "mbid": "mbid-009", "country": "BR", "genres": ["rap", "mpb"]},
    {"name": "Jão",          "mbid": "mbid-010", "country": "BR", "genres": ["pop", "indie"]},
]

# (semana de início do spike, multiplicador)
# Para score > 65: crescimento vs média 4 semanas anteriores precisa ser > 65%
# mult 2.0x starting at i=9 → growth ≈ 119% na semana do pico, 73% na seguinte
SPIKES = {
    "Emicida":      (10, 3.5),   # viral forte — 2 semanas no topo
    "Criolo":       (10, 3.5),   # viral forte — 2 semanas no topo
    "Anitta":       (8,  2.5),   # crescimento sustentado — 3-4 semanas acima
    "Mc Hariel":    (8,  2.5),   # crescimento sustentado — 3-4 semanas acima
    "Jão":          (9,  2.2),   # ascensão moderada — 2-3 semanas acima
    "Luisa Sonza":  (9,  2.2),   # ascensão moderada — 2-3 semanas acima
    "BK":           (9,  2.0),   # ascensão leve — 2 semanas acima
    "Xamã":         (9,  2.0),   # ascensão leve — 2 semanas acima
    # Alcyone e Gilberto Gil: crescimento linear estável, não entram no ranking
}

DB_PATH = os.environ.get(
    "TREND_RADAR_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "trend_radar.duckdb"),
)

# 12 semanas em ordem cronológica
weeks = [
    (date.today() - timedelta(weeks=i)).strftime("%Y-%m-%d")
    for i in range(11, -1, -1)
]

now = datetime.now(tz=timezone.utc)

conn = get_optimized_connection(DB_PATH)

# Limpa dados anteriores para evitar acúmulo entre execuções
conn.execute("DELETE FROM bronze_lastfm_artist_weekly")
conn.execute("DELETE FROM bronze_youtube_channel_weekly")
conn.execute("DELETE FROM bronze_deezer_artist_weekly")

# ---------------------------------------------------------------------------
# bronze_lastfm_artist_weekly
# ---------------------------------------------------------------------------
lastfm_rows = 0
for artist in ARTISTS:
    base = random.randint(10_000, 200_000)
    spike = SPIKES.get(artist["name"])
    for i, week in enumerate(weeks):
        mult = 1.0 + i * 0.05
        if spike and i >= spike[0]:
            mult *= spike[1]
        listeners = int(base * mult * random.uniform(0.9, 1.1))
        conn.execute(
            """
            INSERT OR REPLACE INTO bronze_lastfm_artist_weekly
              (id, week_start, artist_name, mbid, listeners, playcount,
               chart_rank, tags, bio_summary, lastfm_url, source, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lastfm', ?)
            """,
            [
                str(uuid.uuid4()),
                week,
                artist["name"],
                artist["mbid"],
                listeners,
                int(listeners * 4.2),
                random.randint(1, 200),
                artist["genres"],
                f"Artista brasileiro de {', '.join(artist['genres'])}.",
                f"https://www.last.fm/music/{artist['name'].replace(' ', '+')}",
                now,
            ],
        )
        lastfm_rows += 1

# ---------------------------------------------------------------------------
# bronze_youtube_channel_weekly
# ---------------------------------------------------------------------------
yt_rows = 0
for artist in ARTISTS:
    base_subs = random.randint(50_000, 5_000_000)
    base_views = random.randint(1_000_000, 50_000_000)
    spike = SPIKES.get(artist["name"])
    for i, week in enumerate(weeks):
        mult = 1.0 + i * 0.04
        if spike and i >= spike[0]:
            mult *= spike[1]
        subs = int(base_subs * mult * random.uniform(0.95, 1.05))
        views = int(base_views * mult * random.uniform(0.9, 1.1))
        weekly = int(views * random.uniform(0.01, 0.05))
        conn.execute(
            """
            INSERT OR REPLACE INTO bronze_youtube_channel_weekly
              (id, week_start, artist_name, channel_id, channel_title,
               subscriber_count, video_count, view_count, weekly_views,
               topic_categories, thumbnail_url, source, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'youtube', ?)
            """,
            [
                str(uuid.uuid4()),
                week,
                artist["name"],
                f"UC{artist['mbid'][-3:]}demo",
                artist["name"],
                subs,
                random.randint(20, 500),
                views,
                weekly,
                artist["genres"],
                f"https://yt3.ggpht.com/demo/{artist['mbid']}",
                now,
            ],
        )
        yt_rows += 1

# ---------------------------------------------------------------------------
# bronze_deezer_artist_weekly
# ---------------------------------------------------------------------------
dz_rows = 0
for idx, artist in enumerate(ARTISTS):
    base_fans = random.randint(20_000, 3_000_000)
    spike = SPIKES.get(artist["name"])
    for i, week in enumerate(weeks):
        mult = 1.0 + i * 0.03
        if spike and i >= spike[0]:
            mult *= spike[1]
        fans = int(base_fans * mult * random.uniform(0.92, 1.08))
        conn.execute(
            """
            INSERT OR REPLACE INTO bronze_deezer_artist_weekly
              (id, week_start, artist_name, deezer_id, nb_fan, nb_album,
               chart_position, radio, tracklist_url, deezer_url, picture_url,
               source, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'deezer', ?)
            """,
            [
                str(uuid.uuid4()),
                week,
                artist["name"],
                1000 + idx,
                fans,
                random.randint(1, 30),
                random.randint(1, 100),
                True,
                f"https://api.deezer.com/artist/{1000+idx}/top",
                f"https://www.deezer.com/artist/{1000+idx}",
                f"https://api.deezer.com/artist/{1000+idx}/image",
                now,
            ],
        )
        dz_rows += 1

conn.close()

total = lastfm_rows + yt_rows + dz_rows
print(f"Demo data gerada: {len(ARTISTS)} artistas × {len(weeks)} semanas")
print(f"  bronze_lastfm_artist_weekly:   {lastfm_rows} linhas")
print(f"  bronze_youtube_channel_weekly: {yt_rows} linhas")
print(f"  bronze_deezer_artist_weekly:   {dz_rows} linhas")
print(f"  Total: {total} registros inseridos")
print(f"\nAgora execute: make dbt-run dbt-test")
