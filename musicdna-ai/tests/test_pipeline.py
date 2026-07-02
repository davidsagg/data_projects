"""Integration tests for src/pipeline.py — AudioPipeline.

Tests TC-PIPE-001 to TC-PIPE-003.
Production module not yet implemented — these tests are expected to fail
until AudioPipeline is created.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf
import torch

from src.pipeline import AudioPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_clap():
    """Returns mock CLAP processor and model producing a (1, 512) tensor."""
    mock_proc = MagicMock()
    mock_proc.return_value = {"input_features": torch.zeros(1, 1, 64, 100)}
    mock_model = MagicMock()
    mock_model.get_audio_features.return_value = torch.rand(1, 512)
    return mock_proc, mock_model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pipeline(tmp_path):
    """AudioPipeline with all components wired to isolated temp directories."""
    return AudioPipeline(
        processed_dir=str(tmp_path / "processed"),
        embeddings_dir=str(tmp_path / "embeddings"),
        chroma_dir=str(tmp_path / "chroma"),
        db_path=":memory:",
    )


@pytest.fixture
def sample_wav(tmp_path):
    """Writes a 3-second 440 Hz sine-wave WAV file and returns its path."""
    path = str(tmp_path / "test.wav")
    t = np.linspace(0, 3, 3 * 22050)
    sf.write(path, (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32), 22050)
    return path


# ---------------------------------------------------------------------------
# TC-PIPE-001: full pipeline run creates all artifacts
# ---------------------------------------------------------------------------


@patch("src.audio.features.AutoProcessor.from_pretrained")
@patch("src.audio.features.ClapModel.from_pretrained")
def test_pipeline_full_run_creates_all_artifacts(
    mock_model_cls, mock_proc_cls, pipeline, sample_wav
):
    """TC-PIPE-001: run() must create WAV, features JSON, embedding NPY,
    vector store entry and catalog row."""
    mock_proc_cls.return_value, mock_model_cls.return_value = _mock_clap()

    meta = {
        "title": "Full Test",
        "artist": "Tester",
        "genre": "jazz",
        "bpm_manual": 120.0,
        "mood": "relaxed",
    }
    job_id = pipeline.run(sample_wav, metadata=meta)

    assert len(job_id) == 36
    assert (Path(pipeline.processed_dir) / f"{job_id}.wav").exists()
    assert (Path(pipeline.embeddings_dir) / f"{job_id}_features.json").exists()
    assert (Path(pipeline.embeddings_dir) / f"{job_id}_embedding.npy").exists()
    assert pipeline.vector_store.count() == 1
    assert len(pipeline.catalog_store.filter(genre="jazz")) == 1


# ---------------------------------------------------------------------------
# TC-PIPE-002: search after indexing returns top_k results
# ---------------------------------------------------------------------------


@patch("src.audio.features.AutoProcessor.from_pretrained")
@patch("src.audio.features.ClapModel.from_pretrained")
def test_pipeline_search_after_index(
    mock_model_cls, mock_proc_cls, pipeline, sample_wav
):
    """TC-PIPE-002: search_similar() must return top_k dicts with job_id
    and similarity_score after indexing multiple tracks."""
    mock_proc_cls.return_value, mock_model_cls.return_value = _mock_clap()

    for i in range(3):
        pipeline.run(
            sample_wav,
            metadata={
                "title": f"T{i}",
                "artist": "A",
                "genre": "jazz",
                "bpm_manual": 100.0,
                "mood": "happy",
            },
        )

    results = pipeline.search_similar(sample_wav, top_k=2)

    assert len(results) == 2
    assert all("job_id" in r and "similarity_score" in r for r in results)


# ---------------------------------------------------------------------------
# TC-PIPE-003: genre filter applied during search
# ---------------------------------------------------------------------------


@patch("src.audio.features.AutoProcessor.from_pretrained")
@patch("src.audio.features.ClapModel.from_pretrained")
def test_pipeline_filter_then_search(
    mock_model_cls, mock_proc_cls, pipeline, sample_wav
):
    """TC-PIPE-003: search_similar() with filters must exclude non-matching
    genres from results."""
    mock_proc_cls.return_value, mock_model_cls.return_value = _mock_clap()

    for i in range(5):
        pipeline.run(
            sample_wav,
            metadata={
                "title": f"Jazz {i}",
                "artist": "A",
                "genre": "jazz",
                "bpm_manual": 100.0,
                "mood": "happy",
            },
        )
    for i in range(5):
        pipeline.run(
            sample_wav,
            metadata={
                "title": f"Elec {i}",
                "artist": "B",
                "genre": "electronic",
                "bpm_manual": 140.0,
                "mood": "energetic",
            },
        )

    results = pipeline.search_similar(sample_wav, top_k=5, filters={"genre": "jazz"})

    assert all(r["genre"] == "jazz" for r in results)
