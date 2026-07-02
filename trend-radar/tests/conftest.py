# tests/conftest.py — Fixtures globais do Trend Radar Musical BR

import pytest
import duckdb


# ---------------------------------------------------------------------------
# Schemas bronze (espelho dos CREATE TABLE dos clientes de ingestão)
# ---------------------------------------------------------------------------

_BRONZE_LASTFM = """
CREATE TABLE IF NOT EXISTS bronze_lastfm_artist_weekly (
    id              VARCHAR PRIMARY KEY,
    week_start      DATE        NOT NULL,
    artist_name     VARCHAR     NOT NULL,
    mbid            VARCHAR,
    listeners       BIGINT,
    playcount       BIGINT,
    chart_rank      INTEGER,
    tags            VARCHAR[],
    bio_summary     VARCHAR,
    lastfm_url      VARCHAR,
    source          VARCHAR     NOT NULL DEFAULT 'lastfm',
    ingested_at     TIMESTAMPTZ NOT NULL
);
"""

_BRONZE_YOUTUBE = """
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

_BRONZE_YOUTUBE_CACHE = """
CREATE TABLE IF NOT EXISTS bronze_youtube_artist_channel_cache (
    artist_name     VARCHAR PRIMARY KEY,
    channel_id      VARCHAR,
    cached_at       TIMESTAMPTZ NOT NULL
);
"""

_BRONZE_DEEZER = """
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

_BRONZE_MUSICBRAINZ = """
CREATE TABLE IF NOT EXISTS bronze_musicbrainz_artist_weekly (
    id              VARCHAR PRIMARY KEY,   -- {mbid}::{week_start}
    week_start      DATE        NOT NULL,
    artist_name     VARCHAR     NOT NULL,
    mbid            VARCHAR     NOT NULL,
    sort_name       VARCHAR,
    disambiguation  VARCHAR,
    artist_type     VARCHAR,
    gender          VARCHAR,
    country         VARCHAR,
    area            VARCHAR,
    begin_date      DATE,
    end_date        DATE,
    tags            VARCHAR[],
    source          VARCHAR     NOT NULL DEFAULT 'musicbrainz',
    ingested_at     TIMESTAMPTZ NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def duckdb_conn():
    """Conexão DuckDB em memória — nova instância por teste."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def bronze_tables(duckdb_conn):
    """Cria as 4 tabelas bronze + cache YouTube sem dados. Retorna a conexão pronta para uso."""
    for ddl in (_BRONZE_LASTFM, _BRONZE_YOUTUBE, _BRONZE_YOUTUBE_CACHE,
                _BRONZE_DEEZER, _BRONZE_MUSICBRAINZ):
        duckdb_conn.execute(ddl)
    return duckdb_conn


@pytest.fixture
def sample_lastfm_response():
    """
    Simula a resposta combinada de chart.getTopArtists + artist.getInfo
    para 3 artistas brasileiros.
    """
    return {
        "Emicida": {
            "mbid": "uuid-1",
            "listeners": 50_000,
            "playcount": 200_000,
            "tags": ["hip hop", "rap", "brasileiro"],
            "bio_summary": "Emicida é um rapper e produtor musical brasileiro.",
            "url": "https://www.last.fm/music/Emicida",
        },
        "Alcione": {
            "mbid": "uuid-2",
            "listeners": 30_000,
            "playcount": 120_000,
            "tags": ["samba", "mpb", "brasileiro"],
            "bio_summary": "Alcione é uma cantora de samba brasileira.",
            "url": "https://www.last.fm/music/Alcione",
        },
        "Criolo": {
            "mbid": "uuid-3",
            "listeners": 45_000,
            "playcount": 180_000,
            "tags": ["hip hop", "rap", "mpb"],
            "bio_summary": "Criolo é um rapper e cantor brasileiro.",
            "url": "https://www.last.fm/music/Criolo",
        },
    }


@pytest.fixture
def sample_youtube_response():
    """
    Simula a resposta de channels().list() para 2 artistas.
    Estrutura espelha o payload real da YouTube Data API v3.
    """
    return {
        "items": [
            {
                "id": "UC_emicida_channel_id",
                "snippet": {
                    "title": "Emicida",
                    "description": "Canal oficial do Emicida.",
                    "customUrl": "@emicida",
                    "country": "BR",
                    "publishedAt": "2010-05-15T00:00:00Z",
                    "thumbnails": {
                        "high": {"url": "https://yt3.ggpht.com/emicida_thumb.jpg"}
                    },
                },
                "statistics": {
                    "subscriberCount": "1200000",
                    "videoCount": "320",
                    "viewCount": "85000000",
                },
                "topicDetails": {
                    "topicCategories": [
                        "https://en.wikipedia.org/wiki/Music",
                        "https://en.wikipedia.org/wiki/Hip_hop_music",
                    ]
                },
            },
            {
                "id": "UC_criolo_channel_id",
                "snippet": {
                    "title": "Criolo Oficial",
                    "description": "Canal oficial do Criolo.",
                    "customUrl": "@criolo",
                    "country": "BR",
                    "publishedAt": "2012-03-20T00:00:00Z",
                    "thumbnails": {
                        "high": {"url": "https://yt3.ggpht.com/criolo_thumb.jpg"}
                    },
                },
                "statistics": {
                    "subscriberCount": "780000",
                    "videoCount": "210",
                    "viewCount": "52000000",
                },
                "topicDetails": {
                    "topicCategories": [
                        "https://en.wikipedia.org/wiki/Music",
                        "https://en.wikipedia.org/wiki/Hip_hop_music",
                    ]
                },
            },
        ]
    }


@pytest.fixture
def sample_deezer_response():
    """
    Simula a resposta de GET /chart/0/artists com 3 artistas.
    Estrutura espelha o payload real da Deezer API.
    """
    return {
        "data": [
            {
                "id": 1001,
                "name": "Emicida",
                "nb_fan": 520_000,
                "nb_album": 8,
                "radio": True,
                "tracklist": "https://api.deezer.com/artist/1001/top",
                "link": "https://www.deezer.com/artist/1001",
                "picture": "https://api.deezer.com/artist/1001/image",
                "picture_xl": "https://e-cdns-images.dzcdn.net/images/artist/1001/1000x1000.jpg",
            },
            {
                "id": 1002,
                "name": "Alcione",
                "nb_fan": 310_000,
                "nb_album": 42,
                "radio": True,
                "tracklist": "https://api.deezer.com/artist/1002/top",
                "link": "https://www.deezer.com/artist/1002",
                "picture": "https://api.deezer.com/artist/1002/image",
                "picture_xl": "https://e-cdns-images.dzcdn.net/images/artist/1002/1000x1000.jpg",
            },
            {
                "id": 1003,
                "name": "Criolo",
                "nb_fan": 445_000,
                "nb_album": 6,
                "radio": True,
                "tracklist": "https://api.deezer.com/artist/1003/top",
                "link": "https://www.deezer.com/artist/1003",
                "picture": "https://api.deezer.com/artist/1003/image",
                "picture_xl": "https://e-cdns-images.dzcdn.net/images/artist/1003/1000x1000.jpg",
            },
        ],
        "total": 3,
    }
