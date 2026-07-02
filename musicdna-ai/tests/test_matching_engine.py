"""TDD tests for src/matching/engine.py — Module M5 (nova interface).

Test cases TC-M5-001 to TC-M5-007.
Production module not yet updated — these tests are expected to fail
until MatchingEngine is refactored with the new interface.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from src.matching.engine import MatchingEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# MatchResult esperado (dataclass ou namedtuple):
# MatchResult(job_id, title, artist, similarity_score,
#             justification, genre, bpm, mood)


def _make_vector_store_mock(n=3):
    mock = MagicMock()
    mock.search.return_value = [
        {
            "job_id": f"job-{i:03d}",
            "similarity_score": 0.9 - i * 0.1,
            "title": f"Track {i}",
            "genre": "jazz",
            "bpm": 120.0,
            "mood": "relaxed",
            "key": "C major",
        }
        for i in range(n)
    ]
    return mock


def _make_catalog_mock(n=3):
    mock = MagicMock()
    mock.filter.return_value = [
        {
            "job_id": f"job-{i:03d}",
            "title": f"Track {i}",
            "artist": f"Artist {i}",
            "genre": "jazz",
            "bpm_manual": 120.0,
            "mood": "relaxed",
        }
        for i in range(n)
    ]
    return mock


def _make_ollama_mock(justification="Faixa adequada para o contexto."):
    mock = MagicMock()
    mock.return_value = justification
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    """MatchingEngine with mocked vector store and catalog store."""
    vs = _make_vector_store_mock()
    cat = _make_catalog_mock()
    return MatchingEngine(
        vector_store=vs,
        catalog_store=cat,
        ollama_base_url="http://host.docker.internal:11434",
        model_name="llama3",
    )


# ---------------------------------------------------------------------------
# TC-M5-001: match returns list of MatchResult with justification
# ---------------------------------------------------------------------------


@patch("src.matching.engine.MatchingEngine._call_ollama")
@patch("src.matching.engine.MatchingEngine._embed_text")
def test_match_returns_list_of_match_results(mock_embed, mock_ollama, engine):
    """TC-M5-001: match() must return a list of MatchResult with justifications."""
    mock_embed.return_value = np.random.rand(512).astype(np.float32)
    mock_ollama.return_value = "Faixa ideal para o contexto."
    results = engine.match(query="cena de tensao em thriller", top_k=3)
    assert len(results) == 3
    assert all(hasattr(r, "job_id") for r in results)
    assert all(hasattr(r, "justification") for r in results)
    assert all(r.justification != "" for r in results)


# ---------------------------------------------------------------------------
# TC-M5-002: each MatchResult has all required fields with correct types
# ---------------------------------------------------------------------------


@patch("src.matching.engine.MatchingEngine._call_ollama")
@patch("src.matching.engine.MatchingEngine._embed_text")
def test_match_result_has_all_required_fields(mock_embed, mock_ollama, engine):
    """TC-M5-002: MatchResult must expose job_id, title, artist,
    similarity_score, justification, genre, bpm and mood with correct types."""
    engine.vector_store = _make_vector_store_mock(1)
    engine.catalog_store = _make_catalog_mock(1)
    mock_embed.return_value = np.random.rand(512).astype(np.float32)
    mock_ollama.return_value = "Esta faixa jazz e perfeita para o comercial."
    results = engine.match("musica para comercial", top_k=1)
    r = results[0]
    assert isinstance(r.job_id, str)
    assert isinstance(r.title, str)
    assert isinstance(r.artist, str)
    assert 0.0 <= r.similarity_score <= 1.0
    assert len(r.justification) >= 20
    assert isinstance(r.genre, str)
    assert isinstance(r.bpm, float)
    assert isinstance(r.mood, str)


# ---------------------------------------------------------------------------
# TC-M5-003: ollama called exactly once per result
# ---------------------------------------------------------------------------


@patch("src.matching.engine.MatchingEngine._call_ollama")
@patch("src.matching.engine.MatchingEngine._embed_text")
def test_match_calls_ollama_once_per_result(mock_embed, mock_ollama, engine):
    """TC-M5-003: _call_ollama must be invoked exactly once per returned result."""
    engine.vector_store = _make_vector_store_mock(5)
    engine.catalog_store = _make_catalog_mock(5)
    mock_embed.return_value = np.random.rand(512).astype(np.float32)
    mock_ollama.return_value = "Justificativa."
    engine.match("trilha para documentario", top_k=5)
    assert mock_ollama.call_count == 5


# ---------------------------------------------------------------------------
# TC-M5-004: genre filter restricts results
# ---------------------------------------------------------------------------


@patch("src.matching.engine.MatchingEngine._call_ollama")
@patch("src.matching.engine.MatchingEngine._embed_text")
def test_match_with_filters_restricts_results(mock_embed, mock_ollama):
    """TC-M5-004: filters must restrict results to matching catalog entries."""
    vs = _make_vector_store_mock(5)
    cat = MagicMock()
    cat.filter.return_value = [
        {
            "job_id": f"job-{i:03d}",
            "title": f"Jazz {i}",
            "artist": "A",
            "genre": "jazz",
            "bpm_manual": 100.0,
            "mood": "happy",
        }
        for i in range(3)
    ]
    mock_embed.return_value = np.random.rand(512).astype(np.float32)
    mock_ollama.return_value = "Jazz perfeito."
    eng = MatchingEngine(vs, cat, "http://host.docker.internal:11434", "llama3")
    results = eng.match("musica relaxante", top_k=5, filters={"genre": "jazz"})
    assert all(r.genre == "jazz" for r in results)


# ---------------------------------------------------------------------------
# TC-M5-005: text query dispatches to _embed_text
# ---------------------------------------------------------------------------


@patch("src.matching.engine.MatchingEngine._call_ollama")
@patch("src.matching.engine.MatchingEngine._embed_text")
def test_match_text_query_uses_embed_text(mock_embed, mock_ollama, engine):
    """TC-M5-005: a text query must call _embed_text with the exact query string."""
    mock_embed.return_value = np.random.rand(512).astype(np.float32)
    mock_ollama.return_value = "Ok."
    engine.match("upbeat jazz for coffee shop", top_k=1)
    mock_embed.assert_called_once_with("upbeat jazz for coffee shop")


# ---------------------------------------------------------------------------
# TC-M5-006: audio query dispatches to _embed_audio
# ---------------------------------------------------------------------------


@patch("src.matching.engine.MatchingEngine._call_ollama")
@patch("src.matching.engine.MatchingEngine._embed_audio")
def test_match_audio_query_uses_embed_audio(
    mock_embed_audio, mock_ollama, engine, tmp_path
):
    """TC-M5-006: an audio_path query must call _embed_audio with that path."""
    import soundfile as sf

    wav = str(tmp_path / "q.wav")
    t = np.linspace(0, 2, 2 * 22050)
    sf.write(wav, (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32), 22050)
    mock_embed_audio.return_value = np.random.rand(512).astype(np.float32)
    mock_ollama.return_value = "Ok."
    engine.match(audio_path=wav, top_k=1)
    mock_embed_audio.assert_called_once_with(wav)


# ---------------------------------------------------------------------------
# TC-M5-007: ollama timeout returns fallback justification
# ---------------------------------------------------------------------------


@patch("src.matching.engine.MatchingEngine._call_ollama")
@patch("src.matching.engine.MatchingEngine._embed_text")
def test_ollama_timeout_returns_fallback(mock_embed, mock_ollama, engine):
    """TC-M5-007: when _call_ollama raises TimeoutError, justification must
    be the fallback string '[justificativa nao disponivel]'."""
    engine.vector_store = _make_vector_store_mock(1)
    engine.catalog_store = _make_catalog_mock(1)
    mock_embed.return_value = np.random.rand(512).astype(np.float32)
    mock_ollama.side_effect = TimeoutError("Ollama timeout")
    results = engine.match("query", top_k=1)
    assert len(results) == 1
    assert results[0].justification == "[justificativa nao disponivel]"
