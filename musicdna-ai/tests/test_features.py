"""TDD tests for src/audio/features.py — Module M2 acoustic features.

Test cases TC-M2-001 to TC-M2-007.
Production module not yet implemented — these tests are expected to fail
until FeatureExtractor is created.
"""

import json
import re
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from src.audio.features import FeatureExtractor

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_wav_file():
    """Generates a temporary 440 Hz, 5-second, mono WAV at 22 050 Hz.

    Yields:
        :class:`pathlib.Path` to the temporary WAV file.
        The file is deleted automatically after the test.
    """
    sr = 22050
    duration = 5
    t = np.linspace(0, duration, duration * sr)
    signal = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    sf.write(str(tmp_path), signal, sr)
    yield tmp_path

    tmp_path.unlink(missing_ok=True)


@pytest.fixture()
def extractor(tmp_path: Path) -> FeatureExtractor:
    """Returns a FeatureExtractor with an isolated embeddings directory.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        :class:`FeatureExtractor` instance writing to *tmp_path*.
    """
    return FeatureExtractor(embeddings_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# TC-M2-001: BPM extraction
# ---------------------------------------------------------------------------


def test_extract_bpm_returns_float(extractor, sample_wav_file, tmp_path):
    """TC-M2-001: bpm must be a float in the plausible musical range [1, 300]."""
    result = extractor.extract_acoustic("test-job-001", str(sample_wav_file))
    assert isinstance(result["bpm"], float)
    assert 1.0 <= result["bpm"] <= 300.0


# ---------------------------------------------------------------------------
# TC-M2-002: Key extraction
# ---------------------------------------------------------------------------


def test_extract_key_returns_valid_format(extractor, sample_wav_file):
    """TC-M2-002: key must match '<note> major|minor', e.g. 'C# minor'."""
    result = extractor.extract_acoustic("test-job-002", str(sample_wav_file))
    pattern = r"^[A-G][#b]? (major|minor)$"
    assert re.match(pattern, result["key"]), f"Key invalida: {result['key']}"


# ---------------------------------------------------------------------------
# TC-M2-003: MFCC shape and types
# ---------------------------------------------------------------------------


def test_extract_mfcc_correct_shape(extractor, sample_wav_file):
    """TC-M2-003: mfcc_mean and mfcc_std must each contain 20 float values."""
    result = extractor.extract_acoustic("test-job-003", str(sample_wav_file))
    assert len(result["mfcc_mean"]) == 20
    assert len(result["mfcc_std"]) == 20
    assert all(isinstance(v, float) for v in result["mfcc_mean"])


# ---------------------------------------------------------------------------
# TC-M2-004: Spectral features are positive
# ---------------------------------------------------------------------------


def test_extract_spectral_features_positive(extractor, sample_wav_file):
    """TC-M2-004: spectral centroid and bandwidth means must be positive."""
    result = extractor.extract_acoustic("test-job-004", str(sample_wav_file))
    assert result["spectral_centroid_mean"] > 0
    assert result["spectral_bandwidth_mean"] > 0


# ---------------------------------------------------------------------------
# TC-M2-005: Chroma shape and value range
# ---------------------------------------------------------------------------


def test_extract_chroma_correct_shape(extractor, sample_wav_file):
    """TC-M2-005: chroma_mean must have 12 values, each in [0.0, 1.0]."""
    result = extractor.extract_acoustic("test-job-005", str(sample_wav_file))
    assert len(result["chroma_mean"]) == 12
    assert all(0.0 <= v <= 1.0 for v in result["chroma_mean"])


# ---------------------------------------------------------------------------
# TC-M2-006: JSON persistence
# ---------------------------------------------------------------------------


def test_features_saved_to_json(extractor, sample_wav_file):
    """TC-M2-006: extract_acoustic must persist a valid JSON with required keys."""
    job_id = "test-job-006"
    extractor.extract_acoustic(job_id, str(sample_wav_file))

    json_path = Path(extractor.embeddings_dir) / f"{job_id}_features.json"
    assert json_path.exists()

    data = json.loads(json_path.read_text())
    for key in ["bpm", "key", "mfcc_mean", "chroma_mean", "rms_mean", "duration_sec"]:
        assert key in data, f"Chave ausente: {key}"


# ---------------------------------------------------------------------------
# TC-M2-007: RMS energy
# ---------------------------------------------------------------------------


def test_rms_energy_positive(extractor, sample_wav_file):
    """TC-M2-007: rms_mean must be positive for a non-silent signal."""
    result = extractor.extract_acoustic("test-job-007", str(sample_wav_file))
    assert result["rms_mean"] > 0.0


# ---------------------------------------------------------------------------
# TC-M2-008 to TC-M2-010: CLAP embedding extraction
# ---------------------------------------------------------------------------

import torch  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402


def _make_clap_mocks():
    """Retorna mocks de processor e model CLAP com output (1, 512)."""
    mock_processor = MagicMock()
    mock_processor.return_value = {"input_features": torch.zeros(1, 1, 64, 100)}
    mock_model = MagicMock()
    mock_model.get_audio_features.return_value = torch.rand(1, 512)
    return mock_processor, mock_model


@patch("src.audio.features.AutoProcessor.from_pretrained")
@patch("src.audio.features.ClapModel.from_pretrained")
def test_extract_embedding_correct_shape(
    mock_model_cls, mock_proc_cls, extractor, sample_wav_file
):
    """TC-M2-008: extract_embedding must return a numpy array of shape (512,)."""
    mock_proc_cls.return_value, mock_model_cls.return_value = _make_clap_mocks()
    result = extractor.extract_embedding("emb-001", str(sample_wav_file))
    assert isinstance(result, np.ndarray)
    assert result.shape == (512,)


@patch("src.audio.features.AutoProcessor.from_pretrained")
@patch("src.audio.features.ClapModel.from_pretrained")
def test_extract_embedding_saved_as_npy(
    mock_model_cls, mock_proc_cls, extractor, sample_wav_file
):
    """TC-M2-009: extract_embedding must persist a loadable .npy of shape (512,)."""
    mock_proc_cls.return_value, mock_model_cls.return_value = _make_clap_mocks()
    extractor.extract_embedding("emb-002", str(sample_wav_file))
    npy_path = Path(extractor.embeddings_dir) / "emb-002_embedding.npy"
    assert npy_path.exists()
    loaded = np.load(str(npy_path))
    assert loaded.shape == (512,)


@patch("src.audio.features.AutoProcessor.from_pretrained")
@patch("src.audio.features.ClapModel.from_pretrained")
def test_extract_embedding_dtype_float32(
    mock_model_cls, mock_proc_cls, extractor, sample_wav_file
):
    """TC-M2-010: the persisted embedding must have dtype float32."""
    mock_proc_cls.return_value, mock_model_cls.return_value = _make_clap_mocks()
    extractor.extract_embedding("emb-003", str(sample_wav_file))
    npy_path = Path(extractor.embeddings_dir) / "emb-003_embedding.npy"
    loaded = np.load(str(npy_path))
    assert loaded.dtype == np.float32
