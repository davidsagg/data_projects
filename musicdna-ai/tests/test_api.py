"""TDD tests for src/api/main.py — Module M6 FastAPI.

Test cases TC-M6-001 to TC-M6-005.
Production module not yet implemented — these tests are expected to fail
until the FastAPI app is created.
"""

import io
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app, get_engine, get_pipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class MockMatchResult:
    """Minimal MatchResult substitute for API tests."""

    job_id: str = "job-001"
    title: str = "Test Track"
    artist: str = "Test Artist"
    similarity_score: float = 0.92
    justification: str = "Faixa ideal para o contexto solicitado."
    genre: str = "jazz"
    bpm: float = 120.0
    mood: str = "relaxed"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """TestClient with pipeline and engine dependencies mocked out."""
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = "abc123-def456-ghi789-jkl012-mno345"

    mock_engine = MagicMock()
    mock_engine.match.return_value = [MockMatchResult()]

    app.dependency_overrides[get_pipeline] = lambda: mock_pipeline
    app.dependency_overrides[get_engine] = lambda: mock_engine

    yield TestClient(app)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# TC-M6-001: POST /ingest returns job_id and status
# ---------------------------------------------------------------------------


def test_post_ingest_returns_job_id(client, tmp_path):
    """TC-M6-001: POST /ingest must return job_id and status='processed'."""
    wav_bytes = io.BytesIO(b"RIFF" + b"\x00" * 40)
    response = client.post(
        "/ingest",
        files={"audio_file": ("test.wav", wav_bytes, "audio/wav")},
        data={"title": "Test", "artist": "Artist", "genre": "jazz"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "processed"


# ---------------------------------------------------------------------------
# TC-M6-002: POST /match with text query returns results
# ---------------------------------------------------------------------------


def test_post_match_text_returns_results(client):
    """TC-M6-002: POST /match must return a list of results with required fields."""
    response = client.post(
        "/match", json={"query": "cena de acao em filme", "top_k": 3}
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "job_id" in results[0]
    assert "similarity_score" in results[0]
    assert "justification" in results[0]


# ---------------------------------------------------------------------------
# TC-M6-003: POST /match with empty body returns 422
# ---------------------------------------------------------------------------


def test_post_match_invalid_body_returns_422(client):
    """TC-M6-003: POST /match without required fields must return HTTP 422."""
    response = client.post("/match", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# TC-M6-004: GET /health returns status ok with ollama key
# ---------------------------------------------------------------------------


def test_get_health_returns_ok(client):
    """TC-M6-004: GET /health must return status='ok' and an 'ollama' key."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "ollama" in body


# ---------------------------------------------------------------------------
# TC-M6-005: Swagger docs available at /docs
# ---------------------------------------------------------------------------


def test_swagger_docs_available(client):
    """TC-M6-005: GET /docs must return HTTP 200 with text/html content."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
