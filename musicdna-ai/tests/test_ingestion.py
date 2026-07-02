"""TDD tests for src/audio/ingestion.py — Module M1.

Test cases TC-M1-001 to TC-M1-005.
Production module not yet implemented — these tests are expected to fail
until AudioIngestionPipeline and AudioIngestionError are created.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from src.audio.ingestion import AudioIngestionError, AudioIngestionPipeline

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_wav_file():
    """Generates a temporary 440 Hz, 3-second, mono WAV at 22 050 Hz.

    Yields:
        Path-like string to the temporary WAV file.
        The file is deleted automatically after the test.
    """
    t = np.linspace(0, 3, 3 * 22050)
    signal = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    sf.write(tmp_path, signal, 22050)
    yield tmp_path

    Path(tmp_path).unlink(missing_ok=True)


@pytest.fixture()
def pipeline(tmp_path: Path) -> AudioIngestionPipeline:
    """Returns an AudioIngestionPipeline with isolated storage.

    Args:
        tmp_path: Pytest-provided temporary directory for processed files.

    Returns:
        Pipeline instance backed by an in-memory DuckDB and a temp directory.
    """
    return AudioIngestionPipeline(
        processed_dir=tmp_path,
        db_path=":memory:",
    )


# ---------------------------------------------------------------------------
# TC-M1-001: valid WAV ingestion
# ---------------------------------------------------------------------------


def test_ingest_valid_wav(pipeline, sample_wav_file):
    """TC-M1-001: ingesting a valid WAV must return a UUID and write the file."""
    job_id = pipeline.ingest(sample_wav_file)

    assert isinstance(job_id, str) and len(job_id) == 36  # UUID
    processed_path = Path(pipeline.processed_dir) / f"{job_id}.wav"
    assert processed_path.exists()


# ---------------------------------------------------------------------------
# TC-M1-002: invalid format raises AudioIngestionError
# ---------------------------------------------------------------------------


def test_ingest_invalid_format(pipeline, tmp_path):
    """TC-M1-002: a non-audio file must raise AudioIngestionError."""
    bad_file = tmp_path / "fake.wav"
    bad_file.write_text("isso nao e audio")

    with pytest.raises(AudioIngestionError):
        pipeline.ingest(str(bad_file))


# ---------------------------------------------------------------------------
# TC-M1-003: metadata persisted in DuckDB
# ---------------------------------------------------------------------------


def test_metadata_persisted_in_duckdb(pipeline, sample_wav_file):
    """TC-M1-003: after ingestion a catalog row must exist with valid metadata."""
    job_id = pipeline.ingest(sample_wav_file)

    result = pipeline.db.execute(
        "SELECT * FROM catalog WHERE job_id = ?", [job_id]
    ).fetchone()

    assert result is not None
    assert result[7] > 0  # duration_sec
    assert result[8] == 22050  # sample_rate


# ---------------------------------------------------------------------------
# TC-M1-004: manual metadata stored correctly
# ---------------------------------------------------------------------------


def test_ingest_with_manual_metadata(pipeline, sample_wav_file):
    """TC-M1-004: metadata dict must be persisted to the catalog row."""
    meta = {"title": "Test Track", "artist": "Test Artist", "genre": "jazz"}
    job_id = pipeline.ingest(sample_wav_file, metadata=meta)

    result = pipeline.db.execute(
        "SELECT title, artist, genre FROM catalog WHERE job_id = ?", [job_id]
    ).fetchone()

    assert result == ("Test Track", "Test Artist", "jazz")


# ---------------------------------------------------------------------------
# TC-M1-005: status field set to 'processed'
# ---------------------------------------------------------------------------


def test_status_set_to_processed(pipeline, sample_wav_file):
    """TC-M1-005: catalog row status must be 'processed' after ingestion."""
    job_id = pipeline.ingest(sample_wav_file)

    status = pipeline.db.execute(
        "SELECT status FROM catalog WHERE job_id = ?", [job_id]
    ).fetchone()[0]

    assert status == "processed"
