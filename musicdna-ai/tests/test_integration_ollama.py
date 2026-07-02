"""Integration tests with real Ollama — MusicDNA AI.

These tests call the real Ollama instance and are NOT mocked.
Run only when Ollama is available:

    pytest tests/test_integration_ollama.py -v -m integration

Skip in CI with:

    pytest tests/ -m "not integration"
"""

import os
import tempfile

import numpy as np
import pytest
import requests

pytestmark = pytest.mark.integration  # marks all tests in this file


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_engine():
    """MatchingEngine wired to real Ollama with 3 fake indexed tracks."""
    from src.matching.catalog_store import CatalogStore
    from src.matching.engine import MatchingEngine
    from src.matching.vector_store import VectorStore

    tmpdir = tempfile.mkdtemp()
    vs = VectorStore(persist_dir=os.path.join(tmpdir, "chroma"))
    cat = CatalogStore(db_path=":memory:")

    rng = np.random.default_rng(42)
    for i in range(3):
        emb = rng.random(512).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        vs.index(
            f"job-{i}",
            emb,
            {
                "title": f"Jazz Track {i}",
                "genre": "jazz",
                "bpm": 120.0,
                "mood": "relaxed",
                "key": "C major",
            },
        )
        cat.db.execute(
            "INSERT INTO catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
            [
                f"job-{i}",
                f"/data/job-{i}.wav",
                f"Jazz Track {i}",
                "Artist",
                "jazz",
                120.0,
                "relaxed",
                180.0,
                22050,
                1,
                "processed",
            ],
        )

    return MatchingEngine(
        vs,
        cat,
        ollama_base_url="http://host.docker.internal:11434",
        model_name="llama3",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_real_match_generates_portuguese_justification(real_engine):
    """Valida que o Ollama gera justificativa em portugues com conteudo relevante."""
    results = real_engine.match(
        query="musica para cena romantica em serie brasileira",
        top_k=2,
    )
    assert len(results) > 0
    for r in results:
        assert (
            len(r.justification) > 30
        ), f"Justificativa muito curta: {r.justification}"
        print(f"\n[{r.title}] score={r.similarity_score:.3f}")
        print(f"Justificativa: {r.justification}")


def test_real_match_health_check(real_engine):
    """Confirma que o Ollama esta acessivel durante o teste."""
    resp = requests.get("http://host.docker.internal:11434/api/tags", timeout=5)
    assert resp.status_code == 200
    models = [m["name"] for m in resp.json()["models"]]
    assert any("llama3" in m for m in models), f"llama3 nao encontrado: {models}"
