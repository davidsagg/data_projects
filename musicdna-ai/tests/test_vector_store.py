"""TDD tests for src/matching/vector_store.py — Module M3.

Test cases TC-M3-001 to TC-M3-005.
Production module not yet updated with new interface —
these tests are expected to fail until VectorStore is updated.
"""

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def persist_dir(tmp_path):
    d = tmp_path / "chroma"
    d.mkdir()
    return str(d)


@pytest.fixture
def chroma_store(persist_dir):
    from src.matching.vector_store import VectorStore

    return VectorStore(persist_dir=persist_dir)


@pytest.fixture
def embedding_512():
    rng = np.random.default_rng(42)
    emb = rng.random(512).astype(np.float32)
    return emb / np.linalg.norm(emb)


# ---------------------------------------------------------------------------
# TC-M3-001: index persists embedding
# ---------------------------------------------------------------------------


def test_index_embedding_persists(chroma_store, embedding_512):
    """TC-M3-001: after indexing one embedding, count() must return 1."""
    chroma_store.index("job-001", embedding_512, {"title": "Track One"})
    assert chroma_store.count() == 1


# ---------------------------------------------------------------------------
# TC-M3-002: search returns top_k ordered by score descending
# ---------------------------------------------------------------------------


def test_search_returns_top_k_ordered(persist_dir, embedding_512):
    """TC-M3-002: search must return <= top_k results ordered by score desc."""
    from src.matching.vector_store import VectorStore

    store = VectorStore(persist_dir=persist_dir)

    rng = np.random.default_rng(0)
    for i in range(20):
        v = rng.random(512).astype(np.float32)
        v = v / np.linalg.norm(v)
        store.index(f"job-{i:03d}", v, {"title": f"Track {i}"})

    results = store.search(embedding_512, top_k=5)

    assert len(results) <= 5
    scores = [r["similarity_score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.0 for s in scores)


# ---------------------------------------------------------------------------
# TC-M3-003: search respects threshold
# ---------------------------------------------------------------------------


def test_search_respects_threshold(persist_dir):
    """TC-M3-003: results with similarity below threshold must be excluded."""
    from src.matching.vector_store import VectorStore

    store = VectorStore(persist_dir=persist_dir)

    rng = np.random.default_rng(7)
    query = rng.random(512).astype(np.float32)
    query = query / np.linalg.norm(query)

    # Index an orthogonal (low-similarity) vector
    other = rng.random(512).astype(np.float32)
    other = other / np.linalg.norm(other)
    store.index("job-low", other, {"title": "Low Similarity"})

    results = store.search(query, top_k=5, threshold=0.99)
    assert all(r["similarity_score"] >= 0.99 for r in results)


# ---------------------------------------------------------------------------
# TC-M3-004: collection persists after reload
# ---------------------------------------------------------------------------


def test_collection_persists_after_reload(persist_dir, embedding_512):
    """TC-M3-004: a second VectorStore on the same persist_dir must see indexed data."""
    from src.matching.vector_store import VectorStore

    vs1 = VectorStore(persist_dir=persist_dir)
    vs1.index("job-persist-001", embedding_512, {"title": "Persistent Track"})

    vs2 = VectorStore(persist_dir=persist_dir)
    assert vs2.count() == 1


# ---------------------------------------------------------------------------
# TC-M3-005: get_metadata returns correct metadata
# ---------------------------------------------------------------------------


def test_index_includes_metadata(chroma_store, embedding_512):
    """TC-M3-005: get_metadata must return the dict stored during index()."""
    chroma_store.index(
        "job-meta",
        embedding_512,
        {"title": "Meta Track", "genre": "Jazz", "bpm": 120.0},
    )
    meta = chroma_store.get_metadata("job-meta")

    assert meta["title"] == "Meta Track"
    assert meta["genre"] == "Jazz"
    assert float(meta["bpm"]) == 120.0
