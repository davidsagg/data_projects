"""TDD tests for JAM endpoints in src/api/main.py.

Test cases TC-JAM-001 to TC-JAM-005.
Endpoints not yet implemented — these tests are expected to fail
until POST /jam/session and GET /jam/session/{id} are added.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# In-memory store to simulate session persistence across requests.
_sessions_store = {}


@pytest.fixture
def client():
    """TestClient with JamGenerator dependency mocked out."""
    from src.api.main import app, get_jam_generator

    mock_gen = MagicMock()
    mock_gen.generate.return_value = {
        "session_id": "test-uuid-1234-5678-abcd-ef0123456789",
        "midi_path": "/workspace/data/sessions/test.mid",
        "chord_sequence": ["Dm7", "G7", "Cmaj7", "Am7"],
        "suggestion": "Use a escala de Do maior.",
    }
    app.dependency_overrides[get_jam_generator] = lambda: mock_gen
    yield TestClient(app)
    app.dependency_overrides.clear()


VALID_PAYLOAD = {
    "style": "jazz",
    "key": "C",
    "bpm": 120,
    "mood": "relaxado",
    "bars": 4,
}


# ---------------------------------------------------------------------------
# TC-JAM-001: POST /jam/session returns session data
# ---------------------------------------------------------------------------


def test_post_jam_session_returns_session_data(client):
    """TC-JAM-001: POST /jam/session must return session_id, chord_sequence,
    suggestion and midi_path."""
    r = client.post("/jam/session", json=VALID_PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body
    assert "chord_sequence" in body
    assert isinstance(body["chord_sequence"], list)
    assert "suggestion" in body
    assert "midi_path" in body


# ---------------------------------------------------------------------------
# TC-JAM-002: invalid style returns 422
# ---------------------------------------------------------------------------


def test_post_jam_session_invalid_style_returns_422(client):
    """TC-JAM-002: an unsupported style must return HTTP 422."""
    r = client.post("/jam/session", json={**VALID_PAYLOAD, "style": "sertanejo"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# TC-JAM-003: invalid BPM returns 422
# ---------------------------------------------------------------------------


def test_post_jam_session_invalid_bpm_returns_422(client):
    """TC-JAM-003: BPM out of valid range must return HTTP 422."""
    r = client.post("/jam/session", json={**VALID_PAYLOAD, "bpm": 300})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# TC-JAM-004: GET /jam/session/{id} returns the created session
# ---------------------------------------------------------------------------


def test_get_jam_session_returns_session(client):
    """TC-JAM-004: GET /jam/session/{id} must return the session created
    by the preceding POST."""
    post_r = client.post("/jam/session", json=VALID_PAYLOAD)
    session_id = post_r.json()["session_id"]

    get_r = client.get(f"/jam/session/{session_id}")
    assert get_r.status_code == 200
    assert get_r.json()["session_id"] == session_id


# ---------------------------------------------------------------------------
# TC-JAM-005: GET /jam/session/{id} with unknown id returns 404
# ---------------------------------------------------------------------------


def test_get_jam_session_not_found_returns_404(client):
    """TC-JAM-005: GET /jam/session/{id} for a non-existent session must
    return HTTP 404 with 'nao encontrada' in the detail message."""
    r = client.get("/jam/session/nao-existe-123")
    assert r.status_code == 404
    assert "nao encontrada" in r.json()["detail"].lower()
