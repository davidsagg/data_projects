# tests/test_api.py
# TDD RED phase — TC-35 a TC-42: FastAPI endpoints + Streamlit helper.

import pytest
import duckdb

# Imports lazy — módulos ainda não existem
try:
    from src.api.main import app, get_db
except ModuleNotFoundError:
    app = None  # type: ignore[assignment]
    get_db = None  # type: ignore[assignment]

try:
    from src.report.dashboard import build_ranking_df
except ModuleNotFoundError:
    build_ranking_df = None  # type: ignore[assignment]

if app is not None:
    from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# DDL e seed helpers
# ---------------------------------------------------------------------------

_DDL_RISING = """
CREATE TABLE IF NOT EXISTS gold_rising_artists (
    artist_mbid         VARCHAR NOT NULL,
    name                VARCHAR NOT NULL,
    genres              VARCHAR[],
    country             VARCHAR DEFAULT 'BR',
    trending_direction  VARCHAR,
    trend_score         DOUBLE,
    week_start          DATE NOT NULL,
    PRIMARY KEY (artist_mbid, week_start)
);
"""

_DDL_TREND_SCORES = """
CREATE TABLE IF NOT EXISTS gold_trend_scores (
    artist_mbid     VARCHAR NOT NULL,
    week_start      DATE    NOT NULL,
    trend_score     DOUBLE,
    score_lastfm    DOUBLE,
    score_youtube   DOUBLE,
    score_deezer    DOUBLE,
    PRIMARY KEY (artist_mbid, week_start)
);
"""

_DDL_SILVER_ARTISTS = """
CREATE TABLE IF NOT EXISTS silver_artists (
    mbid    VARCHAR NOT NULL PRIMARY KEY,
    name    VARCHAR NOT NULL
);
"""


def _seed_db(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(_DDL_RISING)
    conn.execute(_DDL_TREND_SCORES)
    conn.execute(_DDL_SILVER_ARTISTS)
    conn.execute("INSERT INTO silver_artists VALUES ('uuid-1', 'Artista MPB 1')")

    # 5 artistas em gold_rising_artists: MPB=3, Funk=2
    artists = [
        ("uuid-1", "Artista MPB 1",  ["mpb"],  "up",     92.0),
        ("uuid-2", "Artista MPB 2",  ["mpb"],  "up",     85.0),
        ("uuid-3", "Artista MPB 3",  ["mpb"],  "stable", 78.0),
        ("uuid-4", "Artista Funk 1", ["funk"], "up",     70.0),
        ("uuid-5", "Artista Funk 2", ["funk"], "down",   55.0),
    ]
    conn.executemany(
        "INSERT INTO gold_rising_artists VALUES (?, ?, ?, 'BR', ?, ?, '2026-04-14')",
        artists,
    )

    # 12 semanas de gold_trend_scores para uuid-1
    from datetime import date, timedelta
    base = date(2026, 4, 14)
    for i in range(12):
        week = (base - timedelta(weeks=11 - i)).isoformat()
        score = 60.0 + i * 2.5
        conn.execute(
            "INSERT INTO gold_trend_scores VALUES (?, ?, ?, ?, ?, ?)",
            ["uuid-1", week, score,
             score * 0.4, score * 0.35, score * 0.25],
        )


# ---------------------------------------------------------------------------
# Fixture principal
# ---------------------------------------------------------------------------

@pytest.fixture
def app_with_data():
    """
    Cria DuckDB in-memory preenchido, injeta no app via dependency_overrides
    e retorna TestClient(app).
    """
    if app is None or get_db is None:
        pytest.fail("src.api.main (app / get_db) não implementado — RED phase")

    conn = duckdb.connect(":memory:")
    _seed_db(conn)

    def _override_get_db():
        yield conn

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    conn.close()


# ---------------------------------------------------------------------------
# TC-35: /api/v1/trending retorna 5 resultados ordenados por score desc
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_trending_returns_sorted_by_score(app_with_data):
    resp = app_with_data.get("/api/v1/trending")
    assert resp.status_code == 200

    data = resp.json()
    results = data["results"]
    assert len(results) == 5, f"Esperado 5 resultados, obteve {len(results)}"

    scores = [r["trend_score"] for r in results]
    assert scores == sorted(scores, reverse=True), (
        f"Resultados não estão ordenados por trend_score desc: {scores}"
    )


# ---------------------------------------------------------------------------
# TC-36: filtro ?genre=mpb retorna 3 artistas MPB
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_trending_filter_by_genre(app_with_data):
    resp = app_with_data.get("/api/v1/trending?genre=mpb")
    assert resp.status_code == 200

    results = resp.json()["results"]
    assert len(results) == 3, f"Esperado 3 artistas MPB, obteve {len(results)}"
    for r in results:
        assert "mpb" in r["genre"].lower(), (
            f"Artista '{r['artist_name']}' retornado com genre='{r['genre']}'"
        )


# ---------------------------------------------------------------------------
# TC-37: gênero inexistente → 404
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_trending_no_results_returns_404(app_with_data):
    resp = app_with_data.get("/api/v1/trending?genre=kpop&country=BR")
    assert resp.status_code == 404, (
        f"Esperado 404 para gênero inexistente, obteve {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# TC-38: segunda chamada ao /trending usa cache (X-Cache: HIT)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_trending_response_is_cached(app_with_data):
    app_with_data.get("/api/v1/trending")           # popula cache
    resp2 = app_with_data.get("/api/v1/trending")   # deve vir do cache

    assert resp2.status_code == 200
    assert resp2.headers.get("X-Cache") == "HIT", (
        f"Header X-Cache esperado 'HIT', obteve '{resp2.headers.get('X-Cache')}'"
    )


# ---------------------------------------------------------------------------
# TC-39: histórico de uuid-1 com ?weeks=4 retorna 4 itens com campos certos
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_artist_history_returns_correct_weeks(app_with_data):
    resp = app_with_data.get("/api/v1/artists/uuid-1/history?weeks=4")
    assert resp.status_code == 200

    data = resp.json()
    history = data["history"]
    assert len(history) == 4, f"Esperado 4 semanas, obteve {len(history)}"

    required = {"week_start", "trend_score", "score_lastfm"}
    for item in history:
        missing = required - item.keys()
        assert not missing, f"Item do histórico faltando campos: {missing}"


# ---------------------------------------------------------------------------
# TC-40: artista inexistente → 404
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_artist_not_found_returns_404(app_with_data):
    resp = app_with_data.get("/api/v1/artists/uuid-inexistente/history")
    assert resp.status_code == 404, (
        f"Esperado 404 para artista inexistente, obteve {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# TC-41: build_ranking_df() retorna DataFrame com colunas esperadas
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_dashboard_loads_without_error(duckdb_conn):
    if build_ranking_df is None:
        pytest.fail("src.report.dashboard.build_ranking_df não implementado — RED phase")

    # Cria estrutura mínima esperada
    duckdb_conn.execute(_DDL_RISING)
    _seed_db(duckdb_conn)

    df = build_ranking_df(conn=duckdb_conn)

    assert df is not None, "build_ranking_df() não deve retornar None"
    assert len(df) > 0, "DataFrame não deve estar vazio"

    expected_cols = {"artist_name", "genre", "trend_score", "trending_direction"}
    missing = expected_cols - set(df.columns)
    assert not missing, f"Colunas ausentes no DataFrame: {missing}"


# ---------------------------------------------------------------------------
# TC-42: GET /health retorna 200 com duckdb == 'ok'
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_health_endpoint(app_with_data):
    resp = app_with_data.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data.get("duckdb") == "ok", (
        f"Esperado duckdb='ok' no /health, obteve: {data}"
    )
