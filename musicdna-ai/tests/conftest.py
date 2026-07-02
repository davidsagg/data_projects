"""Shared pytest fixtures for MusicDNA AI test suite."""

from pathlib import Path

import chromadb
import duckdb
import numpy as np
import pytest
import soundfile as sf

# ---------------------------------------------------------------------------
# sample_audio
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_audio(tmp_path: Path) -> Path:
    """Generates a synthetic 10-second mono WAV file at 440 Hz / 22 050 Hz.

    Returns:
        Path to the written WAV file inside *tmp_path*.
    """
    sr = 22_050
    duration = 10.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = (np.sin(2 * np.pi * 440 * t) * 0.8).astype(np.float32)
    path = tmp_path / "sample_440hz_10s.wav"
    sf.write(str(path), audio, sr)
    return path


# ---------------------------------------------------------------------------
# db_connection
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_connection() -> duckdb.DuckDBPyConnection:
    """Creates an in-memory DuckDB connection with the catalog schema.

    The catalog table mirrors the schema used by M1 AudioIngestionPipeline.
    The connection is closed automatically after the test.

    Yields:
        An open :class:`duckdb.DuckDBPyConnection` with the catalog table.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE catalog (
            job_id        VARCHAR PRIMARY KEY,
            file_path     VARCHAR NOT NULL,
            title         VARCHAR,
            artist        VARCHAR,
            genre         VARCHAR,
            bpm_manual    DOUBLE,
            mood          VARCHAR,
            duration_sec  DOUBLE NOT NULL,
            sample_rate   INTEGER NOT NULL,
            status        VARCHAR NOT NULL DEFAULT 'processed',
            created_at    TIMESTAMP NOT NULL DEFAULT now()
        )
        """)
    yield con
    con.close()


# ---------------------------------------------------------------------------
# chroma_client
# ---------------------------------------------------------------------------


@pytest.fixture()
def chroma_client() -> chromadb.ClientAPI:
    """Creates an ephemeral ChromaDB client with an isolated 'tracks' collection.

    Uses :func:`chromadb.EphemeralClient` so no data is written to disk.
    A fresh collection named ``tracks`` with cosine distance is pre-created.

    Returns:
        A :class:`chromadb.ClientAPI` with an empty ``tracks`` collection.
    """
    client = chromadb.EphemeralClient()
    client.create_collection(
        name="tracks",
        metadata={"hnsw:space": "cosine"},
    )
    return client
