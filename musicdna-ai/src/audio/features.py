"""Feature extraction pipeline for MusicDNA AI — Module M2."""

import json
from pathlib import Path

import librosa
import numpy as np
import torch

try:
    from transformers import AutoProcessor, ClapModel
except ImportError:
    ClapModel = None  # type: ignore[assignment,misc]
    AutoProcessor = None  # type: ignore[assignment,misc]

# Krumhansl-Kessler key profiles (major then minor)
_KK_MAJOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_KK_MINOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

TARGET_SR = 22050


class FeatureExtractor:
    """Extracts acoustic features from audio files — Module M2.

    Attributes:
        embeddings_dir: Directory where feature JSON files are persisted.
    """

    def __init__(self, embeddings_dir: str) -> None:
        """Initialises the extractor and ensures the output directory exists.

        Args:
            embeddings_dir: Filesystem path where ``{job_id}_features.json``
                files will be written.
        """
        self.embeddings_dir = embeddings_dir
        Path(embeddings_dir).mkdir(parents=True, exist_ok=True)

        self._model = None  # lazy-loaded CLAP model
        self._processor = None  # lazy-loaded CLAP processor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_acoustic(self, job_id: str, audio_path: str) -> dict:
        """Extracts acoustic features from an audio file and persists them.

        Computes BPM, key, MFCCs, spectral centroid, spectral bandwidth,
        chroma, RMS energy and duration from *audio_path*, saves the result
        as ``{embeddings_dir}/{job_id}_features.json`` and returns the dict.

        Args:
            job_id: Unique identifier for this audio job (used as filename
                stem for the output JSON).
            audio_path: Path to a WAV, MP3 or FLAC file.

        Returns:
            Dict with keys: ``bpm``, ``key``, ``mfcc_mean``, ``mfcc_std``,
            ``spectral_centroid_mean``, ``spectral_centroid_std``,
            ``spectral_bandwidth_mean``, ``spectral_bandwidth_std``,
            ``chroma_mean``, ``rms_mean``, ``duration_sec``.
        """
        y, sr = librosa.load(audio_path, sr=TARGET_SR, mono=True)

        # BPM — librosa.beat.beat_track returns 0 for signals without
        # percussive onsets; librosa.feature.tempo is more robust for any
        # input signal type and satisfies the 1–300 BPM contract.
        tempo = librosa.feature.tempo(y=y, sr=sr)
        bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)

        key = self._detect_key(y, sr)

        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        mfcc_mean: list[float] = mfcc.mean(axis=1).tolist()
        mfcc_std: list[float] = mfcc.std(axis=1).tolist()

        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)

        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean: list[float] = chroma.mean(axis=1).tolist()

        rms = librosa.feature.rms(y=y)
        rms_mean = float(rms.mean())

        duration_sec = float(len(y) / sr)

        result = {
            "bpm": bpm,
            "key": key,
            "mfcc_mean": mfcc_mean,
            "mfcc_std": mfcc_std,
            "spectral_centroid_mean": float(centroid.mean()),
            "spectral_centroid_std": float(centroid.std()),
            "spectral_bandwidth_mean": float(bandwidth.mean()),
            "spectral_bandwidth_std": float(bandwidth.std()),
            "chroma_mean": chroma_mean,
            "rms_mean": rms_mean,
            "duration_sec": duration_sec,
        }

        out_path = Path(self.embeddings_dir) / f"{job_id}_features.json"
        out_path.write_text(json.dumps(result, indent=2))

        return result

    def extract_embedding(self, job_id: str, audio_path: str) -> np.ndarray:
        """Gera embedding CLAP de 512 dimensoes para o audio.

        Carrega o modelo ``laion/clap-htsat-unfused`` na primeira chamada
        (lazy loading).  O audio e reamostrado para 48 000 Hz conforme
        exigido pelo CLAP.  O embedding e normalizado por L2 antes de ser
        persistido.

        Args:
            job_id: Identificador unico da faixa.
            audio_path: Caminho para o arquivo de audio.

        Returns:
            numpy array de shape ``(512,)`` com dtype ``float32``.
        """
        if self._model is None:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            self._processor = AutoProcessor.from_pretrained("laion/clap-htsat-unfused")
            # Assign first, then move to device in-place so that mocks in
            # tests keep their configured return values (MagicMock.to() does
            # not return self, unlike a real nn.Module).
            self._model = ClapModel.from_pretrained("laion/clap-htsat-unfused")
            self._model.to(device)
            self._device = device

        y_48k, _ = librosa.load(audio_path, sr=48000, mono=True)

        inputs = self._processor(audio=y_48k, sampling_rate=48000, return_tensors="pt")
        with torch.no_grad():
            output = self._model.get_audio_features(**inputs)

        embedding = output if isinstance(output, torch.Tensor) else output.pooler_output
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
        result = embedding.squeeze(0).cpu().numpy().astype(np.float32)

        output_path = Path(self.embeddings_dir) / f"{job_id}_embedding.npy"
        np.save(str(output_path), result)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_key(self, y: np.ndarray, sr: int) -> str:
        """Detects musical key using Krumhansl-Kessler profiles.

        Computes the mean chroma_cqt vector and correlates it with all 24
        major and minor KK profiles (12 rotations each).  Returns the key
        whose profile has the highest Pearson correlation.

        Args:
            y: Mono audio signal at *sr* Hz.
            sr: Sample rate in Hz.

        Returns:
            Key string in the format ``'<note> major'`` or ``'<note> minor'``,
            e.g. ``'A minor'`` or ``'C# major'``.
        """
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        mean_chroma = chroma.mean(axis=1)

        best_score = -np.inf
        best_key = "C major"

        for i in range(12):
            major_profile = np.roll(_KK_MAJOR, i)
            corr_major = float(np.corrcoef(mean_chroma, major_profile)[0, 1])
            if corr_major > best_score:
                best_score = corr_major
                best_key = f"{_NOTE_NAMES[i]} major"

            minor_profile = np.roll(_KK_MINOR, i)
            corr_minor = float(np.corrcoef(mean_chroma, minor_profile)[0, 1])
            if corr_minor > best_score:
                best_score = corr_minor
                best_key = f"{_NOTE_NAMES[i]} minor"

        return best_key
