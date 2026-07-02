# tests/test_ingestion_deezer_mbz.py
# TDD RED phase — TC-09 a TC-12

import pytest
from unittest.mock import patch, call
import httpx

from src.ingestion.deezer_client import DeezerClient

# Import lazy — módulo ainda não existe; testes TC-11/TC-12 falham em FAILED, não em ERROR
try:
    from src.ingestion.musicbrainz_client import MusicBrainzClient
except ModuleNotFoundError:
    MusicBrainzClient = None  # type: ignore[assignment,misc]

WEEK_START = "2026-04-14"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deezer_mock_response(mocker, chart_payload: dict, search_payload: dict | None = None):
    """
    Mocka httpx.Client.get para a DeezerClient.
    chart_payload  → primeira chamada (/chart/0/artists)
    search_payload → chamadas subsequentes (/search/artist)
    """
    responses = []

    chart_resp = mocker.MagicMock(spec=httpx.Response)
    chart_resp.raise_for_status = mocker.MagicMock()
    chart_resp.json.return_value = chart_payload
    responses.append(chart_resp)

    if search_payload:
        search_resp = mocker.MagicMock(spec=httpx.Response)
        search_resp.raise_for_status = mocker.MagicMock()
        search_resp.json.return_value = search_payload
        responses.append(search_resp)

    return mocker.patch("httpx.Client.get", side_effect=responses)


# ---------------------------------------------------------------------------
# TC-09: chart salvo com nb_fan NOT NULL
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_deezer_chart_saves_nb_fan(mocker, duckdb_conn, sample_deezer_response):
    """TC-09: 3 artistas do chart inseridos com nb_fan NOT NULL."""
    _deezer_mock_response(mocker, chart_payload=sample_deezer_response)

    client = DeezerClient()
    count = client.run(week_start=WEEK_START, conn=duckdb_conn)

    assert count == 3

    rows = duckdb_conn.execute(
        "SELECT COUNT(*) FROM bronze_deezer_artist_weekly"
    ).fetchone()[0]
    assert rows == 3

    null_fans = duckdb_conn.execute(
        "SELECT COUNT(*) FROM bronze_deezer_artist_weekly WHERE nb_fan IS NULL"
    ).fetchone()[0]
    assert null_fans == 0


# ---------------------------------------------------------------------------
# TC-10: sleep entre requests respeitado
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_deezer_respects_sleep_between_requests(mocker, duckdb_conn, sample_deezer_response):
    """TC-10: time.sleep chamado >= 2 vezes com argumento >= 0.5 ao processar 3 artistas."""
    _deezer_mock_response(mocker, chart_payload=sample_deezer_response)

    mock_sleep = mocker.patch("time.sleep")

    client = DeezerClient()
    client.run(week_start=WEEK_START, conn=duckdb_conn)

    sleep_calls = [c for c in mock_sleep.call_args_list if c.args[0] >= 0.5]
    assert len(sleep_calls) >= 2, (
        f"Esperado >= 2 chamadas de time.sleep(>= 0.5), obteve: {mock_sleep.call_args_list}"
    )


# ---------------------------------------------------------------------------
# TC-11: MusicBrainz salva country e tags
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_musicbrainz_saves_country_and_tags(mocker, duckdb_conn):
    """TC-11: get_artist_by_id mockado com country='BR' e tags=['mpb','samba']."""
    if MusicBrainzClient is None:
        pytest.fail("MusicBrainzClient não implementado — RED phase")
    mbid = "uuid-emicida-mbz"
    artist_mbz_payload = {
        "artist": {
            "id": mbid,
            "name": "Emicida",
            "sort-name": "Emicida",
            "disambiguation": "Brazilian rapper",
            "type": "Person",
            "gender": "Male",
            "country": "BR",
            "area": {"name": "Brazil"},
            "life-span": {"begin": "1985-08-17", "ended": False},
            "tag-list": [
                {"name": "mpb", "count": "10"},
                {"name": "samba", "count": "7"},
            ],
        }
    }

    mocker.patch(
        "musicbrainzngs.get_artist_by_id",
        return_value=artist_mbz_payload,
    )
    mocker.patch("time.sleep")  # evita rate-limit real no teste

    client = MusicBrainzClient()
    count = client.run(week_start=WEEK_START, conn=duckdb_conn, mbids=[mbid])

    assert count == 1

    row = duckdb_conn.execute(
        "SELECT country, tags FROM bronze_musicbrainz_artist_weekly WHERE mbid = ?",
        [mbid],
    ).fetchone()
    assert row is not None, "Nenhum registro encontrado para o mbid informado"
    assert row[0] == "BR", f"country esperado 'BR', obteve '{row[0]}'"
    assert "mpb" in row[1], f"'mpb' não encontrado nas tags: {row[1]}"


# ---------------------------------------------------------------------------
# TC-12: MusicBrainz respeita rate limit de 1 req/s
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_musicbrainz_respects_rate_limit(mocker, duckdb_conn):
    """TC-12: time.sleep chamado >= 2 vezes com arg >= 1.0 ao processar 3 artistas."""
    if MusicBrainzClient is None:
        pytest.fail("MusicBrainzClient não implementado — RED phase")
    mbids = ["uuid-1", "uuid-2", "uuid-3"]

    def _fake_get_artist(mbid, **kwargs):
        return {
            "artist": {
                "id": mbid,
                "name": f"Artist {mbid}",
                "sort-name": f"Artist {mbid}",
                "country": "BR",
                "tag-list": [],
            }
        }

    mocker.patch("musicbrainzngs.get_artist_by_id", side_effect=_fake_get_artist)
    mock_sleep = mocker.patch("time.sleep")

    client = MusicBrainzClient()
    client.run(week_start=WEEK_START, conn=duckdb_conn, mbids=mbids)

    rate_limit_calls = [c for c in mock_sleep.call_args_list if c.args[0] >= 1.0]
    assert len(rate_limit_calls) >= 2, (
        f"Esperado >= 2 chamadas de time.sleep(>= 1.0), obteve: {mock_sleep.call_args_list}"
    )
