"""
Testes do cliente HTTP do Strava e da autenticação OAuth.

A rotação do refresh token é o ponto que mais merece teste: o Strava invalida o
token anterior a cada renovação, então uma falha em persistir o novo não quebra
a execução atual — quebra a próxima, com um erro que parece de configuração.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import pytest

from ingestion.strava_auth import (
    StravaAuth,
    StravaAuthError,
    StravaTokens,
    StravaTokenStore,
)
from ingestion.strava_client import (
    StravaClient,
    StravaRateLimitError,
)

MOCK_ACTIVITIES = [
    {
        "id": 1,
        "sport_type": "Ride",
        "start_date": "2024-01-01T08:00:00Z",
        "distance": 50000.0,
        "elapsed_time": 7200,
    },
    {
        "id": 2,
        "sport_type": "Ride",
        "start_date": "2024-01-03T08:00:00Z",
        "distance": 30000.0,
        "elapsed_time": 4500,
    },
]
MOCK_STREAMS = {"time": {"data": [0, 1, 2, 3]}, "watts": {"data": [200, 210, 195, 220]}}


def _response(status_code: int = 200, payload=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = json.dumps(payload) if payload is not None else ""
    return resp


def _client(session, **kwargs) -> StravaClient:
    return StravaClient(access_token="test_token", session=session, **kwargs)


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------


def test_get_activities_returns_list():
    session = MagicMock()
    session.get.return_value = _response(200, MOCK_ACTIVITIES)

    activities = _client(session).get_activities(limit=2)

    assert len(activities) == 2
    assert activities[0]["id"] == 1
    assert "distance" in activities[0]


def test_get_activity_streams_returns_power():
    session = MagicMock()
    session.get.return_value = _response(200, MOCK_STREAMS)

    streams = _client(session).get_activity_streams(activity_id=123)

    assert "time" in streams and "watts" in streams


def test_streams_missing_activity_returns_empty():
    """O Strava devolve 404 para atividade sem série temporal."""
    session = MagicMock()
    session.get.return_value = _response(404)

    assert _client(session).get_activity_streams(999) == {}


def test_iter_activities_paginates_until_short_page():
    """Uma página incompleta encerra a paginação."""
    full_page = [dict(MOCK_ACTIVITIES[0], id=i) for i in range(200)]
    session = MagicMock()
    session.get.side_effect = [
        _response(200, full_page),
        _response(200, MOCK_ACTIVITIES),
    ]

    collected = list(_client(session).iter_activities())

    assert len(collected) == 202
    assert session.get.call_count == 2


def test_rate_limit_waits_then_retries():
    """Um 429 dorme até a virada da janela e repete a chamada uma vez."""
    slept: list[float] = []
    session = MagicMock()
    session.get.side_effect = [_response(429), _response(200, MOCK_ACTIVITIES)]

    activities = _client(session, sleep=slept.append).get_activities()

    assert len(activities) == 2
    assert len(slept) == 1 and 0 < slept[0] <= 905


def test_rate_limit_twice_raises():
    """Se o 429 persiste depois da espera, é a cota diária — não adianta insistir."""
    session = MagicMock()
    session.get.side_effect = [_response(429), _response(429)]

    with pytest.raises(StravaRateLimitError, match="cota diária"):
        _client(session, sleep=lambda _: None).get_activities()


def test_401_forces_token_refresh_and_retries():
    """Token vencido no meio do backfill renova e repete, sem perder a página."""
    session = MagicMock()
    session.get.side_effect = [_response(401), _response(200, MOCK_ACTIVITIES)]
    auth = MagicMock()
    auth.access_token.return_value = "renovado"

    activities = StravaClient(auth=auth, session=session).get_activities()

    assert len(activities) == 2
    auth.access_token.assert_any_call(force_refresh=True)


# ---------------------------------------------------------------------------
# Autenticação e rotação de token
# ---------------------------------------------------------------------------


def test_token_store_roundtrip(tmp_path):
    store = StravaTokenStore(tmp_path / "token.json")
    store.save(StravaTokens(refresh_token="r1", access_token="a1", expires_at=999))

    loaded = store.load()

    assert loaded.refresh_token == "r1"
    assert loaded.access_token == "a1"


def test_token_store_seeds_from_env(tmp_path, monkeypatch):
    """Na primeira execução a credencial vem do `.env`."""
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "do-env")
    store = StravaTokenStore(tmp_path / "ausente.json")

    assert store.load().refresh_token == "do-env"


def test_refresh_persists_rotated_token(tmp_path):
    """O refresh token novo tem de ir para o disco — o antigo já morreu."""
    store = StravaTokenStore(tmp_path / "token.json")
    store.save(StravaTokens(refresh_token="antigo"))

    session = MagicMock()
    session.post.return_value = _response(
        200,
        {
            "access_token": "novo-access",
            "refresh_token": "novo-refresh",
            "expires_at": int(time.time()) + 21600,
        },
    )

    token = StravaAuth("id", "segredo", store=store, session=session).access_token()

    assert token == "novo-access"
    assert store.load().refresh_token == "novo-refresh", "rotação não foi persistida"


def test_fresh_token_skips_refresh(tmp_path):
    """Token ainda válido não gasta uma renovação."""
    store = StravaTokenStore(tmp_path / "token.json")
    store.save(
        StravaTokens(
            refresh_token="r", access_token="ainda-vale", expires_at=int(time.time()) + 7200
        )
    )
    session = MagicMock()

    token = StravaAuth("id", "segredo", store=store, session=session).access_token()

    assert token == "ainda-vale"
    session.post.assert_not_called()


def test_missing_credentials_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("STRAVA_REFRESH_TOKEN", raising=False)
    store = StravaTokenStore(tmp_path / "nada.json")

    with pytest.raises(StravaAuthError, match="Nenhum refresh token"):
        StravaAuth("id", "segredo", store=store).access_token()


def test_rejected_refresh_raises(tmp_path):
    store = StravaTokenStore(tmp_path / "token.json")
    store.save(StravaTokens(refresh_token="revogado"))
    session = MagicMock()
    session.post.return_value = _response(400, {"message": "Bad Request"})

    with pytest.raises(StravaAuthError, match="recusou"):
        StravaAuth("id", "segredo", store=store, session=session).access_token()
