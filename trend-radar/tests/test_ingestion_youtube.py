# tests/test_ingestion_youtube.py
# TDD RED phase — testes definem a interface desejada do YouTubeClient.

import pytest
from unittest.mock import MagicMock, patch

from src.ingestion.youtube_client import YouTubeClient, QuotaExceededError

WEEK_START = "2026-04-14"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_search_response(channel_id: str) -> dict:
    """Payload de search().list().execute() com 1 canal."""
    return {
        "items": [
            {"snippet": {"channelId": channel_id}}
        ]
    }


def _make_empty_search_response() -> dict:
    return {"items": []}


def _mock_service(mocker, search_side_effect=None, channels_response=None):
    """
    Monta um mock do googleapiclient service com search().list() e channels().list()
    configuráveis. Retorna (mock_service, mock_search_list, mock_channels_list).
    """
    mock_service = MagicMock()

    # search chain: service.search().list(**kw).execute()
    mock_search_execute = MagicMock()
    if search_side_effect is not None:
        mock_search_execute.side_effect = search_side_effect
    mock_service.search.return_value.list.return_value.execute = mock_search_execute

    # channels chain: service.channels().list(**kw).execute()
    mock_channels_execute = MagicMock(return_value=channels_response or {"items": []})
    mock_service.channels.return_value.list.return_value.execute = mock_channels_execute

    mocker.patch(
        "googleapiclient.discovery.build",
        return_value=mock_service,
    )
    return mock_service, mock_search_execute, mock_channels_execute


# ---------------------------------------------------------------------------
# TC-05: mapeamento correto e persistência no bronze
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_youtube_maps_artists_and_saves_bronze(mocker, duckdb_conn, sample_youtube_response):
    """TC-05: 2 artistas mapeados via search; stats inseridas com weekly_views > 0."""
    artist_names = ["Emicida", "Criolo"]

    search_responses = [
        _make_search_response("UC_emicida_channel_id"),
        _make_search_response("UC_criolo_channel_id"),
    ]

    mock_service, mock_search_exec, _ = _mock_service(
        mocker,
        search_side_effect=search_responses,
        channels_response=sample_youtube_response,
    )

    client = YouTubeClient(api_key="test-key")
    count = client.run(week_start=WEEK_START, conn=duckdb_conn, artist_names=artist_names)

    assert count == 2

    rows = duckdb_conn.execute(
        "SELECT COUNT(*) FROM bronze_youtube_channel_weekly"
    ).fetchone()[0]
    assert rows == 2

    zero_views = duckdb_conn.execute(
        "SELECT COUNT(*) FROM bronze_youtube_channel_weekly WHERE weekly_views <= 0"
    ).fetchone()[0]
    assert zero_views == 0


# ---------------------------------------------------------------------------
# TC-06: cliente para ao atingir o limite de quota
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_youtube_stops_at_quota_limit(mocker, duckdb_conn):
    """TC-06: com 100 artistas (100u/search), para antes de atingir 8000 unidades."""
    artist_names = [f"Artist_{i}" for i in range(100)]

    # Cada search retorna um canal distinto
    search_responses = [
        _make_search_response(f"UC_channel_{i}") for i in range(100)
    ]
    channels_response = {
        "items": [
            {
                "id": f"UC_channel_{i}",
                "snippet": {
                    "title": f"Artist_{i}",
                    "description": "",
                    "publishedAt": "2020-01-01T00:00:00Z",
                    "thumbnails": {},
                },
                "statistics": {"subscriberCount": "1000", "videoCount": "10", "viewCount": "5000"},
                "topicDetails": {"topicCategories": []},
            }
            for i in range(100)
        ]
    }

    _mock_service(
        mocker,
        search_side_effect=search_responses,
        channels_response=channels_response,
    )

    client = YouTubeClient(api_key="test-key")
    client.run(week_start=WEEK_START, conn=duckdb_conn, artist_names=artist_names)

    # Deve ter parado antes de processar todos os 100 artistas
    saved = duckdb_conn.execute(
        "SELECT COUNT(*) FROM bronze_youtube_channel_weekly"
    ).fetchone()[0]
    assert saved < 100, f"Esperava menos de 100 registros, obteve {saved}"

    # Unidades usadas não devem ultrapassar o limite de segurança
    assert client.quota_used <= 8_000, f"quota_used={client.quota_used} > 8000"


# ---------------------------------------------------------------------------
# TC-07: artista sem canal → registro salvo com channel_id NULL
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_youtube_artist_without_channel_saves_null(mocker, duckdb_conn):
    """TC-07: search retorna vazio → 1 registro com channel_id IS NULL e weekly_views == 0."""
    _mock_service(
        mocker,
        search_side_effect=[_make_empty_search_response()],
        channels_response={"items": []},
    )

    client = YouTubeClient(api_key="test-key")
    count = client.run(week_start=WEEK_START, conn=duckdb_conn, artist_names=["Artista Desconhecido"])

    assert count == 1

    row = duckdb_conn.execute(
        "SELECT channel_id, weekly_views FROM bronze_youtube_channel_weekly LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] is None, "channel_id deve ser NULL quando canal não encontrado"
    assert row[1] == 0, "weekly_views deve ser 0 quando canal não encontrado"


# ---------------------------------------------------------------------------
# TC-08: cache evita re-busca de artistas já mapeados
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_youtube_uses_cache_for_known_artists(mocker, bronze_tables):
    """TC-08: Emicida já está no cache → search().list() NÃO é chamado para ele."""
    conn = bronze_tables

    # Popula o cache diretamente no DuckDB
    conn.execute(
        """
        INSERT INTO bronze_youtube_artist_channel_cache (artist_name, channel_id, cached_at)
        VALUES ('Emicida', 'ch_123', '2026-04-07T00:00:00+00:00')
        """
    )

    channels_response = {
        "items": [
            {
                "id": "ch_123",
                "snippet": {
                    "title": "Emicida",
                    "description": "Canal Emicida",
                    "customUrl": "@emicida",
                    "country": "BR",
                    "publishedAt": "2010-01-01T00:00:00Z",
                    "thumbnails": {"high": {"url": "https://example.com/thumb.jpg"}},
                },
                "statistics": {
                    "subscriberCount": "1200000",
                    "videoCount": "320",
                    "viewCount": "85000000",
                },
                "topicDetails": {"topicCategories": []},
            }
        ]
    }

    mock_service, mock_search_exec, _ = _mock_service(
        mocker,
        search_side_effect=[],  # search não deve ser chamado
        channels_response=channels_response,
    )

    client = YouTubeClient(api_key="test-key")
    count = client.run(week_start=WEEK_START, conn=conn, artist_names=["Emicida"])

    # search não deve ter sido chamado nenhuma vez
    assert mock_search_exec.call_count == 0, (
        f"search.execute() chamado {mock_search_exec.call_count} vezes; esperado 0 (cache hit)"
    )

    assert count == 1

    row = duckdb_conn_channel = conn.execute(
        "SELECT channel_id FROM bronze_youtube_channel_weekly WHERE artist_name = 'Emicida'"
    ).fetchone()
    assert row is not None
    assert row[0] == "ch_123", f"channel_id esperado 'ch_123', obteve '{row[0]}'"
