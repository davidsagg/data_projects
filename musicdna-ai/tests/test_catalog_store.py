"""TDD tests for src/matching/catalog_store.py — Module M4.

Test cases TC-M4-001 to TC-M4-004.
Production module not yet implemented — these tests are expected to fail
until CatalogStore is created.
"""

import csv

import pytest

from src.matching.catalog_store import CatalogStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_track(store, job_id, title, artist, genre, bpm, mood, key):
    store.db.execute(
        "INSERT INTO catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        [
            job_id,
            f"/data/{job_id}.wav",
            title,
            artist,
            genre,
            bpm,
            mood,
            key,
            180.0,
            22050,
            "processed",
        ],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def catalog_store():
    """CatalogStore backed by an in-memory DuckDB database."""
    return CatalogStore(db_path=":memory:")


@pytest.fixture
def populated_catalog(catalog_store):
    """CatalogStore with 10 tracks across jazz, electronic, mpb and rock."""
    tracks = [
        ("j001", "Track A", "Art1", "jazz", 90.0, "melancolico", "C major"),
        ("j002", "Track B", "Art2", "jazz", 120.0, "alegre", "G major"),
        ("j003", "Track C", "Art3", "jazz", 100.0, "melancolico", "D minor"),
        ("j004", "Track D", "Art4", "jazz", 130.0, "alegre", "B major"),
        ("j005", "Track E", "Art5", "electronic", 140.0, "energetico", "A minor"),
        ("j006", "Track F", "Art6", "electronic", 160.0, "energetico", "E minor"),
        ("j007", "Track G", "Art7", "electronic", 80.0, "melancolico", "F major"),
        ("j008", "Track H", "Art8", "mpb", 110.0, "melancolico", "A major"),
        ("j009", "Track I", "Art9", "mpb", 95.0, "alegre", "E major"),
        ("j010", "Track J", "Art10", "rock", 115.0, "relaxado", "C# major"),
    ]
    for t in tracks:
        _insert_track(catalog_store, *t)
    return catalog_store


# ---------------------------------------------------------------------------
# TC-M4-001: filter by genre
# ---------------------------------------------------------------------------


def test_filter_by_genre(populated_catalog):
    """TC-M4-001: filter(genre=) must return only tracks with that genre."""
    results = populated_catalog.filter(genre="jazz")
    assert len(results) == 4
    assert all(r["genre"] == "jazz" for r in results)


# ---------------------------------------------------------------------------
# TC-M4-002: filter by BPM range
# ---------------------------------------------------------------------------


def test_filter_by_bpm_range(populated_catalog):
    """TC-M4-002: filter(bpm_min=, bpm_max=) must respect the BPM bounds."""
    results = populated_catalog.filter(bpm_min=90, bpm_max=130)
    assert all(90.0 <= r["bpm"] <= 130.0 for r in results)
    assert len(results) > 0


# ---------------------------------------------------------------------------
# TC-M4-003: combined genre + mood filter
# ---------------------------------------------------------------------------


def test_filter_combined_genre_and_mood(populated_catalog):
    """TC-M4-003: combining genre and mood filters must apply both conditions."""
    results = populated_catalog.filter(genre="jazz", mood="melancolico")
    assert len(results) == 2
    assert all(r["genre"] == "jazz" and r["mood"] == "melancolico" for r in results)


# ---------------------------------------------------------------------------
# TC-M4-004: export to CSV
# ---------------------------------------------------------------------------


def test_export_to_csv(populated_catalog, tmp_path):
    """TC-M4-004: export_csv must write all rows with the expected headers."""
    output = str(tmp_path / "export.csv")
    populated_catalog.export_csv(output)

    with open(output) as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 10
    assert "job_id" in rows[0] and "genre" in rows[0]
