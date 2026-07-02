# tests/test_dbt_models.py — TC-18 a TC-24: validação dos modelos dbt Gold

import subprocess
import pytest
import duckdb
from pathlib import Path

DBT_PROJECT_DIR = Path(__file__).parent.parent / "dbt"
DB_PATH = Path(__file__).parent.parent / "data" / "trend_radar_test.duckdb"

WEEK_DATES = [
    "2026-01-05",
    "2026-01-12",
    "2026-01-19",
    "2026-01-26",
    "2026-02-02",
    "2026-02-09",
]

# DDL das tabelas bronze (para smoke test TC-18)
_BRONZE_DDLS = [
    """CREATE TABLE IF NOT EXISTS bronze_lastfm_artist_weekly (
        id VARCHAR PRIMARY KEY, week_start DATE NOT NULL,
        artist_name VARCHAR NOT NULL, mbid VARCHAR, listeners BIGINT,
        playcount BIGINT, chart_rank INTEGER, tags VARCHAR[],
        bio_summary VARCHAR, lastfm_url VARCHAR,
        source VARCHAR NOT NULL DEFAULT 'lastfm', ingested_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS bronze_youtube_channel_weekly (
        id VARCHAR PRIMARY KEY, week_start DATE NOT NULL,
        artist_name VARCHAR NOT NULL, channel_id VARCHAR, channel_title VARCHAR,
        subscriber_count BIGINT, video_count BIGINT, view_count BIGINT,
        weekly_views BIGINT, topic_categories VARCHAR[], thumbnail_url VARCHAR,
        source VARCHAR NOT NULL DEFAULT 'youtube', ingested_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS bronze_deezer_artist_weekly (
        id VARCHAR PRIMARY KEY, week_start DATE NOT NULL,
        artist_name VARCHAR NOT NULL, deezer_id BIGINT NOT NULL,
        nb_fan BIGINT, nb_album INTEGER, chart_position INTEGER,
        radio BOOLEAN, tracklist_url VARCHAR, deezer_url VARCHAR,
        picture_url VARCHAR, source VARCHAR NOT NULL DEFAULT 'deezer',
        ingested_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS bronze_musicbrainz_artist_weekly (
        id VARCHAR PRIMARY KEY, week_start DATE NOT NULL,
        artist_name VARCHAR NOT NULL, mbid VARCHAR NOT NULL,
        sort_name VARCHAR, disambiguation VARCHAR, artist_type VARCHAR,
        gender VARCHAR, country VARCHAR, area VARCHAR, begin_date DATE,
        end_date DATE, tags VARCHAR[],
        source VARCHAR NOT NULL DEFAULT 'musicbrainz', ingested_at TIMESTAMPTZ NOT NULL
    )""",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_dbt(args: list[str]) -> subprocess.CompletedProcess:
    """Executa dbt com target 'test' (trend_radar_test.duckdb)."""
    return subprocess.run(
        ["dbt", *args,
         "--project-dir", str(DBT_PROJECT_DIR),
         "--profiles-dir", str(DBT_PROJECT_DIR),
         "--target", "test"],
        capture_output=True,
        text=True,
    )


def _init_bronze_tables(conn: duckdb.DuckDBPyConnection) -> None:
    for ddl in _BRONZE_DDLS:
        conn.execute(ddl)


def _seed_silver_weekly_plays(
    conn: duckdb.DuckDBPyConnection,
    artist_mbid: str,
    weeks: list[str],
    lastfm_plays: list[int],
    yt_views: list[int],
    dz_fans: list[int],
) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS silver_weekly_plays (
            artist_mbid   VARCHAR NOT NULL,
            week_start    DATE    NOT NULL,
            lastfm_plays  BIGINT,
            youtube_views BIGINT,
            deezer_fans   BIGINT,
            PRIMARY KEY (artist_mbid, week_start)
        )
    """)
    rows = list(zip([artist_mbid] * len(weeks), weeks, lastfm_plays, yt_views, dz_fans))
    conn.executemany("INSERT INTO silver_weekly_plays VALUES (?, ?, ?, ?, ?)", rows)


def _seed_silver_artists(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple],  # (mbid, name, country, tags)
) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS silver_artists (
            mbid    VARCHAR,
            name    VARCHAR,
            country VARCHAR,
            tags    VARCHAR[]
        )
    """)
    conn.executemany("INSERT INTO silver_artists VALUES (?, ?, ?, ?)", rows)


def _seed_gold_trend_scores(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple],  # (artist_mbid, week_start, trend_score, score_lf, score_yt, score_dz, weeks_above)
) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gold_trend_scores (
            artist_mbid          VARCHAR NOT NULL,
            week_start           DATE    NOT NULL,
            trend_score          DOUBLE,
            score_lastfm         DOUBLE,
            score_youtube        DOUBLE,
            score_deezer         DOUBLE,
            weeks_above_threshold BIGINT
        )
    """)
    conn.executemany("INSERT INTO gold_trend_scores VALUES (?, ?, ?, ?, ?, ?, ?)", rows)


def _cleanup():
    if DB_PATH.exists():
        DB_PATH.unlink()


# ---------------------------------------------------------------------------
# TC-18: smoke — todos os modelos gold compilam com tabelas bronze vazias
# ---------------------------------------------------------------------------

@pytest.mark.dbt
def test_gold_builds_with_empty_bronze():
    """TC-18: dbt run bronze+ (silver + gold) compila sem erros com dados vazios."""
    _cleanup()
    conn = duckdb.connect(str(DB_PATH))
    _init_bronze_tables(conn)
    conn.close()

    try:
        result = _run_dbt(["run", "--select", "bronze+"])
        assert result.returncode == 0, (
            f"dbt run falhou com tabelas vazias:\n{result.stdout}\n{result.stderr}"
        )
        result2 = _run_dbt(["test", "--select", "gold"])
        assert result2.returncode == 0, (
            f"dbt test gold falhou com dados vazios:\n{result2.stdout}\n{result2.stderr}"
        )
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# TC-19: trend_score NULL quando histórico insuficiente (< 4 semanas)
# ---------------------------------------------------------------------------

@pytest.mark.dbt
def test_trend_score_null_for_insufficient_history():
    """TC-19: artista com apenas 2 semanas de dados → trend_score deve ser NULL."""
    _cleanup()
    conn = duckdb.connect(str(DB_PATH))
    _seed_silver_weekly_plays(
        conn,
        artist_mbid="mbid-artista-x",
        weeks=["2026-04-07", "2026-04-14"],
        lastfm_plays=[1000, 1100],
        yt_views=[5000, 5500],
        dz_fans=[300, 310],
    )
    conn.close()

    try:
        result = _run_dbt(["run", "--select", "gold_trend_scores"])
        assert result.returncode == 0, f"dbt run falhou:\n{result.stdout}\n{result.stderr}"

        conn = duckdb.connect(str(DB_PATH))
        row = conn.execute(
            "SELECT trend_score FROM gold_trend_scores WHERE artist_mbid = 'mbid-artista-x'"
        ).fetchone()
        conn.close()

        assert row is not None, "Nenhum registro encontrado para mbid-artista-x"
        assert row[0] is None, f"Esperado trend_score NULL, obteve {row[0]}"
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# TC-20: fórmula de trend_score ponderada corretamente
# ---------------------------------------------------------------------------

@pytest.mark.dbt
def test_trend_score_formula_weighted_correctly():
    """
    TC-20: crescimento controlado em 6 semanas.
    lastfm +50%, youtube +40%, deezer +30%.
    Score esperado = 0.40*50 + 0.35*40 + 0.25*30 = 41.5. Tolerância < 2.
    """
    _cleanup()
    conn = duckdb.connect(str(DB_PATH))
    _seed_silver_weekly_plays(
        conn,
        artist_mbid="mbid-artista-y",
        weeks=WEEK_DATES,
        lastfm_plays=[1000, 1000, 1000, 1000, 1000, 1500],
        yt_views=[5000, 5000, 5000, 5000, 5000, 7000],
        dz_fans=[500,  500,  500,  500,  500,  650],
    )
    conn.close()

    try:
        result = _run_dbt(["run", "--select", "gold_trend_scores"])
        assert result.returncode == 0, f"dbt run falhou:\n{result.stdout}\n{result.stderr}"

        conn = duckdb.connect(str(DB_PATH))
        row = conn.execute(
            "SELECT trend_score FROM gold_trend_scores WHERE artist_mbid = 'mbid-artista-y'"
        ).fetchone()
        conn.close()

        assert row is not None, "Nenhum registro encontrado para mbid-artista-y"
        assert row[0] is not None, "trend_score não deve ser NULL com 6 semanas de dados"

        score = float(row[0])
        assert abs(score - 41.5) < 2, (
            f"Score esperado ≈41.5, obteve {score} (diferença: {abs(score - 41.5):.2f})"
        )
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# TC-21: gold_rising_artists filtra apenas artistas acima do limiar
# ---------------------------------------------------------------------------

@pytest.mark.dbt
def test_rising_artists_filter():
    """TC-21: apenas artistas com weeks_above_threshold >= 2 aparecem em gold_rising_artists."""
    _cleanup()
    conn = duckdb.connect(str(DB_PATH))

    # mbid-rising: semanas 5 e 6 com 200% de crescimento → score=100 > 65 em ambas
    _seed_silver_weekly_plays(conn, "mbid-rising", WEEK_DATES,
        lastfm_plays=[100, 100, 100, 100, 300, 300],
        yt_views=    [100, 100, 100, 100, 300, 300],
        dz_fans=     [100, 100, 100, 100, 300, 300])

    # mbid-stable: crescimento zero → score=0 sempre
    _seed_silver_weekly_plays(conn, "mbid-stable", WEEK_DATES,
        lastfm_plays=[100, 100, 100, 100, 100, 100],
        yt_views=    [100, 100, 100, 100, 100, 100],
        dz_fans=     [100, 100, 100, 100, 100, 100])

    _seed_silver_artists(conn, [
        ("mbid-rising", "ArtistRising", "BR", ["samba"]),
        ("mbid-stable", "ArtistStable", "BR", ["mpb"]),
    ])
    conn.close()

    try:
        result = _run_dbt(["run", "--select", "gold_trend_scores", "gold_rising_artists"])
        assert result.returncode == 0, f"dbt run falhou:\n{result.stdout}\n{result.stderr}"

        conn = duckdb.connect(str(DB_PATH))
        rows = conn.execute("SELECT artist_mbid FROM gold_rising_artists").fetchall()
        conn.close()

        mbids = [r[0] for r in rows]
        assert "mbid-rising" in mbids, "Artista em ascensão deve aparecer em gold_rising_artists"
        assert "mbid-stable" not in mbids, "Artista estável não deve aparecer"
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# TC-22: gold_rising_artists tem rank_da_semana sequencial
# ---------------------------------------------------------------------------

@pytest.mark.dbt
def test_rising_artists_rank_column():
    """TC-22: gold_rising_artists tem coluna rank_da_semana com inteiro >= 1."""
    _cleanup()
    conn = duckdb.connect(str(DB_PATH))

    _seed_silver_weekly_plays(conn, "mbid-top", WEEK_DATES,
        lastfm_plays=[100, 100, 100, 100, 300, 300],
        yt_views=    [100, 100, 100, 100, 300, 300],
        dz_fans=     [100, 100, 100, 100, 300, 300])

    _seed_silver_artists(conn, [("mbid-top", "ArtistTop", "BR", ["samba"])])
    conn.close()

    try:
        result = _run_dbt(["run", "--select", "gold_trend_scores", "gold_rising_artists"])
        assert result.returncode == 0, f"dbt run falhou:\n{result.stdout}\n{result.stderr}"

        conn = duckdb.connect(str(DB_PATH))
        row = conn.execute(
            "SELECT rank_da_semana FROM gold_rising_artists WHERE artist_mbid = 'mbid-top'"
        ).fetchone()
        conn.close()

        assert row is not None, "Artista deve aparecer em gold_rising_artists"
        assert isinstance(row[0], int) and row[0] >= 1, (
            f"rank_da_semana deve ser inteiro >= 1, obteve {row[0]}"
        )
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# TC-23: gold_genre_heatmap agrega avg_trend_score por gênero
# ---------------------------------------------------------------------------

@pytest.mark.dbt
def test_genre_heatmap_aggregation():
    """TC-23: gold_genre_heatmap calcula avg_trend_score correto por gênero."""
    _cleanup()
    conn = duckdb.connect(str(DB_PATH))

    samba_artists = [f"mbid-samba-{i}" for i in range(4)]
    _seed_gold_trend_scores(conn, [
        (mbid, "2026-03-02", 70.0, 28.0, 24.5, 17.5, 1)
        for mbid in samba_artists
    ])
    _seed_silver_artists(conn, [
        (mbid, f"ArtistSamba{i}", "BR", ["samba"])
        for i, mbid in enumerate(samba_artists)
    ])
    conn.close()

    try:
        result = _run_dbt(["run", "--select", "gold_genre_heatmap"])
        assert result.returncode == 0, f"dbt run falhou:\n{result.stdout}\n{result.stderr}"

        conn = duckdb.connect(str(DB_PATH))
        row = conn.execute(
            "SELECT avg_trend_score, artist_count FROM gold_genre_heatmap WHERE genre = 'samba'"
        ).fetchone()
        conn.close()

        assert row is not None, "Gênero 'samba' deve aparecer no heatmap"
        assert abs(row[0] - 70.0) < 0.01, f"avg_trend_score esperado 70.0, obteve {row[0]}"
        assert row[1] >= 3, f"artist_count deve ser >= 3, obteve {row[1]}"
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# TC-24: gold_genre_heatmap trending_direction segue a lógica de delta
# ---------------------------------------------------------------------------

@pytest.mark.dbt
def test_genre_heatmap_trending_direction():
    """TC-24: trending_direction = 'up'/delta>5, 'down'/delta<-5, 'stable' caso contrário."""
    _cleanup()
    conn = duckdb.connect(str(DB_PATH))

    week1, week2 = "2026-03-02", "2026-03-09"
    # 4 artistas por gênero × 3 gêneros × 2 semanas = 24 linhas em gold_trend_scores
    genres_data = {
        # gênero: (score_w1, score_w2)  → delta = w2-w1
        "samba": (50.0, 62.0),   # delta=+12 → 'up'
        "funk":  (60.0, 48.0),   # delta=-12 → 'down'
        "mpb":   (50.0, 53.0),   # delta=+3  → 'stable'
    }
    trend_rows, silver_rows = [], []
    for genre, (s1, s2) in genres_data.items():
        for i in range(4):
            mbid = f"mbid-{genre}-{i}"
            trend_rows.append((mbid, week1, s1, s1 * 0.4, s1 * 0.35, s1 * 0.25, 0))
            trend_rows.append((mbid, week2, s2, s2 * 0.4, s2 * 0.35, s2 * 0.25, 1))
            silver_rows.append((mbid, f"Artist{genre.capitalize()}{i}", "BR", [genre]))

    _seed_gold_trend_scores(conn, trend_rows)
    _seed_silver_artists(conn, silver_rows)
    conn.close()

    try:
        result = _run_dbt(["run", "--select", "gold_genre_heatmap"])
        assert result.returncode == 0, f"dbt run falhou:\n{result.stdout}\n{result.stderr}"

        conn = duckdb.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT genre, trending_direction FROM gold_genre_heatmap WHERE week_start = ?",
            [week2],
        ).fetchall()
        conn.close()

        direction = {r[0]: r[1] for r in rows}
        assert direction.get("samba") == "up",    f"samba esperado 'up', obteve {direction.get('samba')}"
        assert direction.get("funk")  == "down",  f"funk esperado 'down', obteve {direction.get('funk')}"
        assert direction.get("mpb")   == "stable", f"mpb esperado 'stable', obteve {direction.get('mpb')}"
    finally:
        _cleanup()
