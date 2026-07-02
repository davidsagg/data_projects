"""Audio ingestion pipeline for MusicDNA AI — Module M1."""

import uuid
from pathlib import Path
from typing import Optional

import duckdb
import librosa
import soundfile as sf

TARGET_SR = 22050
SUPPORTED_FORMATS = {".wav", ".mp3", ".flac"}


class AudioIngestionError(Exception):
    """Raised when an audio file cannot be ingested.

    Covers unsupported formats and files that cannot be decoded by librosa.
    """


class AudioIngestionPipeline:
    """Ingests raw audio files, normalises them and persists metadata.

    The pipeline:

    1. Validates the file extension.
    2. Loads and resamples to 22 050 Hz mono via librosa.
    3. Writes the normalised WAV to *processed_dir*.
    4. Inserts a catalog row into the DuckDB connection exposed as ``self.db``.

    Attributes:
        processed_dir: :class:`pathlib.Path` where normalised WAV files land.
        db: Open :class:`duckdb.DuckDBPyConnection` for the catalog table.
    """

    def __init__(
        self,
        processed_dir: str,
        db_path: str = ":memory:",
    ) -> None:
        """Initialises the pipeline, storage directory and catalog table.

        Args:
            processed_dir: Directory where normalised WAV files are stored.
                Created (with parents) if it does not already exist.
            db_path: DuckDB connection string.  Use ``':memory:'`` for an
                in-memory database (default, ideal for tests) or a file path
                for persistent storage.
        """
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        self.db = duckdb.connect(db_path)
        self._init_catalog()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(
        self,
        file_path: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Ingests an audio file, normalises it and registers it in the catalog.

        Accepted formats: ``.wav``, ``.mp3``, ``.flac``.

        Args:
            file_path: Path to the source audio file.
            metadata: Optional dict with any of: ``title``, ``artist``,
                ``genre``, ``bpm_manual``, ``mood``.

        Returns:
            A UUID4 string (36 characters) that uniquely identifies this job.

        Raises:
            AudioIngestionError: If the extension is not supported, or if the
                file cannot be decoded as audio by librosa/soundfile.
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext not in SUPPORTED_FORMATS:
            raise AudioIngestionError(f"Formato nao suportado: {ext}")

        try:
            y, _ = librosa.load(str(path), sr=TARGET_SR, mono=True)
        except Exception as exc:
            raise AudioIngestionError(
                f"Nao foi possivel carregar o audio '{path.name}': {exc}"
            ) from exc

        job_id = str(uuid.uuid4())
        output_path = self.processed_dir / f"{job_id}.wav"
        sf.write(str(output_path), y, TARGET_SR, subtype="PCM_16")

        duration_sec = len(y) / TARGET_SR
        meta = metadata or {}

        self.db.execute(
            """
            INSERT INTO catalog
                (job_id, file_path, title, artist, genre, bpm,
                 mood, duration_sec, sample_rate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed')
            """,
            [
                job_id,
                str(path),
                meta.get("title"),
                meta.get("artist"),
                meta.get("genre"),
                meta.get("bpm"),
                meta.get("mood"),
                duration_sec,
                TARGET_SR,
            ],
        )
        return job_id

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_catalog(self) -> None:
        """Creates the catalog table in DuckDB if it does not already exist."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS catalog (
                job_id      VARCHAR PRIMARY KEY,
                file_path   VARCHAR,
                title       VARCHAR,
                artist      VARCHAR,
                genre       VARCHAR,
                bpm         FLOAT,
                mood        VARCHAR,
                duration_sec FLOAT,
                sample_rate INTEGER,
                status      VARCHAR,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
