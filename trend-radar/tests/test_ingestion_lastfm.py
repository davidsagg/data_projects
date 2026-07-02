# tests/test_ingestion_lastfm.py
# TDD RED phase — os testes falham até LastFmClient e LastFmAuthError serem implementados.

import pytest
import httpx

from src.ingestion.lastfm_client import LastFmClient, LastFmAuthError

WEEK_START = "2026-04-14"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_chart_response(artists_data: dict) -> dict:
    """Monta payload de chart.getTopArtists a partir do sample_lastfm_response."""
    return {
        "artists": {
            "artist": [
                {"name": name, "mbid": info["mbid"], "url": info["url"]}
                for name, info in artists_data.items()
            ]
        }
    }


def _build_artist_info_response(name: str, info: dict) -> dict:
    """Monta payload de artist.getInfo para um artista."""
    return {
        "artist": {
            "name": name,
            "mbid": info["mbid"],
            "url": info["url"],
            "stats": {"listeners": info["listeners"], "playcount": info["playcount"]},
            "tags": {"tag": [{"name": t} for t in info["tags"]]},
            "bio": {"summary": info["bio_summary"]},
        }
    }


# ---------------------------------------------------------------------------
# TC-01: campos obrigatórios persistidos corretamente
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_lastfm_fetch_saves_required_fields(mocker, duckdb_conn, sample_lastfm_response):
    """TC-01: run() insere 3 registros com week_start, listeners e playcount NOT NULL."""
    artists = sample_lastfm_response
    artist_names = list(artists.keys())

    # Sequência de respostas: 1 chart + 1 getInfo por artista
    responses = [_build_chart_response(artists)] + [
        _build_artist_info_response(name, artists[name]) for name in artist_names
    ]
    response_iter = iter(responses)

    mock_response = mocker.MagicMock()
    mock_response.raise_for_status = mocker.MagicMock()
    mock_response.json.side_effect = lambda: next(response_iter)

    mocker.patch("httpx.Client.get", return_value=mock_response)

    client = LastFmClient(api_key="test-key")
    count = client.run(week_start=WEEK_START, conn=duckdb_conn)

    assert count == 3

    rows = duckdb_conn.execute(
        "SELECT COUNT(*) FROM bronze_lastfm_artist_weekly"
    ).fetchone()[0]
    assert rows == 3

    nulls = duckdb_conn.execute(
        """
        SELECT COUNT(*) FROM bronze_lastfm_artist_weekly
        WHERE week_start IS NULL OR listeners IS NULL OR playcount IS NULL
        """
    ).fetchone()[0]
    assert nulls == 0


# ---------------------------------------------------------------------------
# TC-02: chave de API inválida levanta LastFmAuthError
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_lastfm_invalid_api_key_raises_error(mocker, duckdb_conn):
    """TC-02: resposta 403 da API deve levantar LastFmAuthError."""
    mock_response = mocker.MagicMock(spec=httpx.Response)
    mock_response.status_code = 403
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="403 Forbidden",
        request=mocker.MagicMock(),
        response=mock_response,
    )

    mocker.patch("httpx.Client.get", return_value=mock_response)

    client = LastFmClient(api_key="invalid-key")

    with pytest.raises(LastFmAuthError):
        client.run(week_start=WEEK_START, conn=duckdb_conn)


# ---------------------------------------------------------------------------
# TC-03: retry em rate limit (429 × 2 → 200 na 3ª tentativa)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_lastfm_retry_on_rate_limit(mocker, duckdb_conn, sample_lastfm_response):
    """TC-03: 429 nas 2 primeiras chamadas do chart; 200 na 3ª. Mock chamado 3 vezes."""
    artists = sample_lastfm_response
    artist_names = list(artists.keys())

    # Respostas do chart: falha, falha, sucesso
    chart_payload = _build_chart_response(artists)
    artist_info_payloads = [
        _build_artist_info_response(name, artists[name]) for name in artist_names
    ]

    rate_limit_response = mocker.MagicMock(spec=httpx.Response)
    rate_limit_response.status_code = 429
    rate_limit_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="429 Too Many Requests",
        request=mocker.MagicMock(),
        response=rate_limit_response,
    )

    success_chart = mocker.MagicMock()
    success_chart.raise_for_status = mocker.MagicMock()
    success_chart.json.return_value = chart_payload

    info_responses = [
        mocker.MagicMock(**{"raise_for_status": mocker.MagicMock(), "json.return_value": p})
        for p in artist_info_payloads
    ]

    mock_get = mocker.patch(
        "httpx.Client.get",
        side_effect=[rate_limit_response, rate_limit_response, success_chart, *info_responses],
    )

    # Desabilita o sleep do tenacity para o teste não demorar
    mocker.patch("tenacity.nap.sleep")

    client = LastFmClient(api_key="test-key")
    count = client.run(week_start=WEEK_START, conn=duckdb_conn)

    # chart foi chamado 3 vezes (2 rate-limit + 1 sucesso) + 3 getInfo
    assert mock_get.call_count == 3 + len(artist_names)
    assert count == 3


# ---------------------------------------------------------------------------
# TC-04: run() duas vezes com os mesmos dados — idempotência
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_lastfm_save_is_idempotent(mocker, duckdb_conn, sample_lastfm_response):
    """TC-04: duas chamadas run() com week_start idêntico resultam em COUNT(*) == 3."""
    artists = sample_lastfm_response
    artist_names = list(artists.keys())

    def make_side_effects():
        payloads = [_build_chart_response(artists)] + [
            _build_artist_info_response(name, artists[name]) for name in artist_names
        ]
        responses = []
        for p in payloads:
            m = mocker.MagicMock()
            m.raise_for_status = mocker.MagicMock()
            m.json.return_value = p
            responses.append(m)
        return responses

    mocker.patch(
        "httpx.Client.get",
        side_effect=make_side_effects() + make_side_effects(),
    )

    client = LastFmClient(api_key="test-key")
    client.run(week_start=WEEK_START, conn=duckdb_conn)
    client.run(week_start=WEEK_START, conn=duckdb_conn)

    rows = duckdb_conn.execute(
        "SELECT COUNT(*) FROM bronze_lastfm_artist_weekly"
    ).fetchone()[0]
    assert rows == 3, f"Esperado 3 registros (idempotente), obtido {rows}"
