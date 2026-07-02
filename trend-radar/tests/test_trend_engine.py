# tests/test_trend_engine.py
# TDD RED phase — TC-25 a TC-34: AnomalyDetector, GenreHeatmap, TrendForecaster.

import pytest
import duckdb
from datetime import date, timedelta

# Imports lazy — módulos ainda não existem
try:
    from src.trend_engine.anomaly import AnomalyDetector
except ModuleNotFoundError:
    AnomalyDetector = None  # type: ignore[assignment,misc]

try:
    from src.trend_engine.genre_heatmap import GenreHeatmap
except ModuleNotFoundError:
    GenreHeatmap = None  # type: ignore[assignment,misc]

try:
    from src.trend_engine.forecaster import TrendForecaster
except ModuleNotFoundError:
    TrendForecaster = None  # type: ignore[assignment,misc]

WEEK_START = "2026-04-14"

# ---------------------------------------------------------------------------
# DDL compartilhado
# ---------------------------------------------------------------------------

_DDL_WEEKLY_PLAYS = """
CREATE TABLE IF NOT EXISTS silver_weekly_plays (
    artist_mbid     VARCHAR NOT NULL,
    artist_name     VARCHAR NOT NULL,
    week_start      DATE    NOT NULL,
    lastfm_plays    BIGINT  DEFAULT 0,
    youtube_views   BIGINT  DEFAULT 0,
    deezer_fans     BIGINT  DEFAULT 0,
    PRIMARY KEY (artist_mbid, week_start)
);
"""

_DDL_ARTIST_GENRES = """
CREATE TABLE IF NOT EXISTS silver_artists (
    artist_mbid     VARCHAR PRIMARY KEY,
    artist_name     VARCHAR NOT NULL,
    genre           VARCHAR
);
"""

_DDL_TREND_SCORES = """
CREATE TABLE IF NOT EXISTS gold_trend_scores (
    artist_mbid     VARCHAR NOT NULL,
    artist_name     VARCHAR NOT NULL,
    week_start      DATE    NOT NULL,
    trend_score     DOUBLE,
    PRIMARY KEY (artist_mbid, week_start)
);
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _monday(offset_weeks: int = 0) -> str:
    """Retorna a data da segunda-feira com offset em semanas a partir de WEEK_START."""
    base = date.fromisoformat(WEEK_START)
    return (base - timedelta(weeks=offset_weeks)).isoformat()


@pytest.fixture
def weekly_plays_8w():
    """
    Conexão DuckDB em memória com 8 semanas de silver_weekly_plays para 3 artistas.

    - 'Viral'    (mbid-viral):    baseline ~1000 plays/semana, spike de 300% na última.
    - 'Estavel'  (mbid-estavel):  baseline ~1000 plays/semana, variação < 10%.
    - 'Declinio' (mbid-declinio): baseline decrescente suave, variação < 10% relativa.
    """
    conn = duckdb.connect(":memory:")
    conn.execute(_DDL_WEEKLY_PLAYS)
    conn.execute(_DDL_ARTIST_GENRES)

    weeks = [_monday(i) for i in range(7, -1, -1)]  # semana 8 a semana 1 (mais recente)

    artists = [
        ("mbid-viral",    "Viral"),
        ("mbid-estavel",  "Estavel"),
        ("mbid-declinio", "Declinio"),
    ]

    for mbid, name in artists:
        conn.execute(
            "INSERT INTO silver_artists VALUES (?, ?, ?)",
            [mbid, name, "MPB"],
        )

    rows = []
    for i, week in enumerate(weeks):
        is_last = i == len(weeks) - 1

        # Viral: 1000 base, 4000 na última semana (spike 300%)
        rows.append(("mbid-viral", "Viral", week,
                     4000 if is_last else 1000,
                     8000 if is_last else 2000,
                     500  if is_last else 150))

        # Estavel: ~1000 com ruído < 10%
        rows.append(("mbid-estavel", "Estavel", week,
                     1000 + (i * 5),
                     2000 + (i * 10),
                     150 + i))

        # Declinio: queda suave < 10%
        rows.append(("mbid-declinio", "Declinio", week,
                     1000 - (i * 8),
                     2000 - (i * 15),
                     150 - i))

    conn.executemany(
        "INSERT INTO silver_weekly_plays VALUES (?, ?, ?, ?, ?, ?)", rows
    )
    yield conn
    conn.close()


@pytest.fixture
def weekly_plays_multi_source():
    """Artista 'MultiViral' com spike simultâneo em lastfm E youtube."""
    conn = duckdb.connect(":memory:")
    conn.execute(_DDL_WEEKLY_PLAYS)
    conn.execute(_DDL_ARTIST_GENRES)

    conn.execute("INSERT INTO silver_artists VALUES ('mbid-multi', 'MultiViral', 'Pop')")

    weeks = [_monday(i) for i in range(7, -1, -1)]
    for i, week in enumerate(weeks):
        is_last = i == len(weeks) - 1
        conn.execute(
            "INSERT INTO silver_weekly_plays VALUES (?, ?, ?, ?, ?, ?)",
            ["mbid-multi", "MultiViral", week,
             5000 if is_last else 1000,   # lastfm spike 400%
             9000 if is_last else 2000,   # youtube spike 350%
             150],
        )
    yield conn
    conn.close()


@pytest.fixture
def genre_data():
    """
    DuckDB com 4 semanas de gold_trend_scores por artista/gênero.
    MPB → 'up', Funk → 'down', Rock → 'stable', Axé → apenas 2 artistas (excluído).
    """
    conn = duckdb.connect(":memory:")
    conn.execute(_DDL_TREND_SCORES)
    conn.execute(_DDL_ARTIST_GENRES)

    genres_config = {
        # genre: [(artist_mbid, artist_name, [score_w4, w3, w2, w1])]
        "MPB":  [
            ("mbid-mpb-1", "Artista MPB 1", [48, 49, 50, 58]),
            ("mbid-mpb-2", "Artista MPB 2", [47, 49, 50, 58]),
            ("mbid-mpb-3", "Artista MPB 3", [50, 51, 50, 58]),
        ],
        "Funk": [
            ("mbid-funk-1", "Artista Funk 1", [62, 60, 60, 52]),
            ("mbid-funk-2", "Artista Funk 2", [60, 61, 60, 52]),
            ("mbid-funk-3", "Artista Funk 3", [58, 59, 60, 52]),
        ],
        "Rock": [
            ("mbid-rock-1", "Artista Rock 1", [44, 44, 45, 46]),
            ("mbid-rock-2", "Artista Rock 2", [45, 45, 45, 46]),
            ("mbid-rock-3", "Artista Rock 3", [46, 45, 45, 46]),
        ],
        "Axé":  [
            ("mbid-axe-1", "Artista Axé 1", [40, 41, 42, 43]),
            ("mbid-axe-2", "Artista Axé 2", [39, 40, 41, 42]),
            # apenas 2 — deve ser excluído com min_artists=3
        ],
    }

    weeks = [_monday(i) for i in range(3, -1, -1)]  # w4 ... w1 (atual)

    for genre, artists in genres_config.items():
        for mbid, name, scores in artists:
            conn.execute(
                "INSERT INTO silver_artists VALUES (?, ?, ?)",
                [mbid, name, genre],
            )
            for week, score in zip(weeks, scores):
                conn.execute(
                    "INSERT INTO gold_trend_scores VALUES (?, ?, ?, ?)",
                    [mbid, name, week, float(score)],
                )

    yield conn
    conn.close()


@pytest.fixture
def weekly_plays_12w():
    """12 semanas de dados para um artista — ativa método 'prophet' no forecaster."""
    conn = duckdb.connect(":memory:")
    conn.execute(_DDL_WEEKLY_PLAYS)
    conn.execute(_DDL_ARTIST_GENRES)
    conn.execute(_DDL_TREND_SCORES)

    conn.execute("INSERT INTO silver_artists VALUES ('mbid-forecast', 'ArtistForecast', 'MPB')")

    weeks = [_monday(i) for i in range(11, -1, -1)]
    for i, week in enumerate(weeks):
        conn.execute(
            "INSERT INTO silver_weekly_plays VALUES (?, ?, ?, ?, ?, ?)",
            ["mbid-forecast", "ArtistForecast", week,
             1000 + i * 50, 2000 + i * 80, 150 + i * 5],
        )
        conn.execute(
            "INSERT INTO gold_trend_scores VALUES (?, ?, ?, ?)",
            ["mbid-forecast", "ArtistForecast", week, 40.0 + i * 2.5],
        )
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# TC-25: z-score alto → anomalia detectada para 'Viral'
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_high_zscore_creates_anomaly(weekly_plays_8w):
    if AnomalyDetector is None:
        pytest.fail("AnomalyDetector não implementado — RED phase")

    detector = AnomalyDetector(threshold=2.5, conn=weekly_plays_8w)
    detector.run(week_start=WEEK_START)

    row = weekly_plays_8w.execute(
        "SELECT anomaly_score FROM gold_anomalies WHERE artist_name = 'Viral' AND week_start = ?",
        [WEEK_START],
    ).fetchone()
    assert row is not None, "Viral deveria estar em gold_anomalies"
    assert row[0] > 2.5, f"anomaly_score esperado > 2.5, obteve {row[0]}"


# ---------------------------------------------------------------------------
# TC-26: z-score baixo → sem anomalia para artistas estáveis
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_low_zscore_no_anomaly(weekly_plays_8w):
    if AnomalyDetector is None:
        pytest.fail("AnomalyDetector não implementado — RED phase")

    detector = AnomalyDetector(threshold=2.5, conn=weekly_plays_8w)
    detector.run(week_start=WEEK_START)

    for name in ("Estavel", "Declinio"):
        row = weekly_plays_8w.execute(
            "SELECT 1 FROM gold_anomalies WHERE artist_name = ? AND week_start = ?",
            [name, WEEK_START],
        ).fetchone()
        assert row is None, f"'{name}' não deveria estar em gold_anomalies"


# ---------------------------------------------------------------------------
# TC-27: idempotência — duas execuções não duplicam registros
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_anomaly_idempotent(weekly_plays_8w):
    if AnomalyDetector is None:
        pytest.fail("AnomalyDetector não implementado — RED phase")

    detector = AnomalyDetector(threshold=2.5, conn=weekly_plays_8w)
    detector.run(week_start=WEEK_START)
    detector.run(week_start=WEEK_START)

    count = weekly_plays_8w.execute(
        "SELECT COUNT(*) FROM gold_anomalies WHERE week_start = ?", [WEEK_START]
    ).fetchone()[0]
    assert count == 1, f"Esperado 1 anomalia (idempotente), obteve {count}"


# ---------------------------------------------------------------------------
# TC-28: spike em múltiplas fontes → trigger_source == 'multi'
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_multi_source_trigger(weekly_plays_multi_source):
    if AnomalyDetector is None:
        pytest.fail("AnomalyDetector não implementado — RED phase")

    detector = AnomalyDetector(threshold=2.5, conn=weekly_plays_multi_source)
    detector.run(week_start=WEEK_START)

    row = weekly_plays_multi_source.execute(
        "SELECT trigger_source FROM gold_anomalies WHERE artist_name = 'MultiViral'",
    ).fetchone()
    assert row is not None, "MultiViral deveria estar em gold_anomalies"
    assert row[0] == "multi", f"trigger_source esperado 'multi', obteve '{row[0]}'"


# ---------------------------------------------------------------------------
# TC-29: heatmap exclui gêneros com poucos artistas
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_genre_heatmap_excludes_small_genres(genre_data):
    if GenreHeatmap is None:
        pytest.fail("GenreHeatmap não implementado — RED phase")

    heatmap = GenreHeatmap(min_artists=3, conn=genre_data)
    result = heatmap.compute(week_start=WEEK_START)

    genres = [row["genre"] for row in result]
    assert "Axé" not in genres, f"'Axé' (2 artistas) não deveria aparecer no heatmap: {genres}"


# ---------------------------------------------------------------------------
# TC-30: MPB trending_direction == 'up'
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_genre_trending_direction_up(genre_data):
    if GenreHeatmap is None:
        pytest.fail("GenreHeatmap não implementado — RED phase")

    heatmap = GenreHeatmap(min_artists=3, conn=genre_data)
    result = heatmap.compute(week_start=WEEK_START)

    mpb = next((r for r in result if r["genre"] == "MPB"), None)
    assert mpb is not None, "MPB deveria estar no resultado do heatmap"
    assert mpb["trending_direction"] == "up", (
        f"MPB: trending_direction esperado 'up', obteve '{mpb['trending_direction']}'"
    )


# ---------------------------------------------------------------------------
# TC-31: Funk trending_direction == 'down'
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_genre_trending_direction_down(genre_data):
    if GenreHeatmap is None:
        pytest.fail("GenreHeatmap não implementado — RED phase")

    heatmap = GenreHeatmap(min_artists=3, conn=genre_data)
    result = heatmap.compute(week_start=WEEK_START)

    funk = next((r for r in result if r["genre"] == "Funk"), None)
    assert funk is not None, "Funk deveria estar no resultado do heatmap"
    assert funk["trending_direction"] == "down", (
        f"Funk: trending_direction esperado 'down', obteve '{funk['trending_direction']}'"
    )


# ---------------------------------------------------------------------------
# TC-32: forecaster retorna 4 semanas com campos obrigatórios
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_forecast_returns_4_weeks(weekly_plays_8w):
    if TrendForecaster is None:
        pytest.fail("TrendForecaster não implementado — RED phase")

    forecaster = TrendForecaster(conn=weekly_plays_8w)
    result = forecaster.forecast(artist_mbid="mbid-viral", weeks_ahead=4)

    assert isinstance(result, list), "forecast() deve retornar uma lista"
    assert len(result) == 4, f"Esperado 4 semanas previstas, obteve {len(result)}"

    required_keys = {"week", "predicted_score", "lower_bound", "upper_bound"}
    for item in result:
        missing = required_keys - item.keys()
        assert not missing, f"Item do forecast faltando campos: {missing} — {item}"


# ---------------------------------------------------------------------------
# TC-33: 12+ semanas → método 'prophet'
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_forecast_uses_prophet_with_12_weeks(weekly_plays_12w):
    if TrendForecaster is None:
        pytest.fail("TrendForecaster não implementado — RED phase")

    forecaster = TrendForecaster(conn=weekly_plays_12w)
    forecaster.forecast(artist_mbid="mbid-forecast", weeks_ahead=4)

    assert forecaster.method == "prophet", (
        f"Com 12+ semanas, método esperado 'prophet', obteve '{forecaster.method}'"
    )


# ---------------------------------------------------------------------------
# TC-34: 8 semanas → método 'weighted_ma'
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_forecast_uses_weighted_ma_with_8_weeks(weekly_plays_8w):
    if TrendForecaster is None:
        pytest.fail("TrendForecaster não implementado — RED phase")

    forecaster = TrendForecaster(conn=weekly_plays_8w)
    forecaster.forecast(artist_mbid="mbid-viral", weeks_ahead=4)

    assert forecaster.method == "weighted_ma", (
        f"Com 8 semanas, método esperado 'weighted_ma', obteve '{forecaster.method}'"
    )
