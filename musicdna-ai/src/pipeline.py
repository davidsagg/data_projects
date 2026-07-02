"""End-to-end audio processing pipeline for MusicDNA AI.

Wires together M1 (ingestion), M2 (feature extraction), M3 (vector store)
and M4 (catalog store) into a single cohesive interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.audio.features import FeatureExtractor
from src.audio.ingestion import AudioIngestionPipeline
from src.matching.catalog_store import CatalogStore
from src.matching.vector_store import VectorStore


class AudioPipeline:
    """Orchestrates ingestion, feature extraction, indexing and search.

    For in-memory databases (``db_path=':memory:'``) the DuckDB connection
    from the ingestion pipeline is shared with the catalog store so that
    rows written by :meth:`run` are immediately visible to
    :meth:`~src.matching.catalog_store.CatalogStore.filter`.

    Attributes:
        processed_dir: Directory where normalised WAV files are stored.
        embeddings_dir: Directory where feature JSON and NPY files are stored.
        ingestion: M1 audio ingestion pipeline.
        extractor: M2 feature extractor.
        vector_store: M3 ChromaDB vector store.
        catalog_store: M4 DuckDB catalog store.
    """

    def __init__(
        self,
        processed_dir: str,
        embeddings_dir: str,
        chroma_dir: str,
        db_path: str = ":memory:",
    ) -> None:
        """Initialises all pipeline components.

        Args:
            processed_dir: Path for normalised WAV output files.
            embeddings_dir: Path for feature JSON and embedding NPY files.
            chroma_dir: Path for the persistent ChromaDB store.
            db_path: DuckDB database path or ``':memory:'`` for tests.
        """
        self.processed_dir = processed_dir
        self.embeddings_dir = embeddings_dir

        self.ingestion = AudioIngestionPipeline(processed_dir, db_path)
        self.extractor = FeatureExtractor(embeddings_dir=embeddings_dir)
        self.vector_store = VectorStore(persist_dir=chroma_dir)
        self.catalog_store = CatalogStore(db_path=db_path)

        # Share the same DuckDB connection so that in-memory databases see
        # rows written by ingestion immediately in catalog_store queries.
        self.catalog_store.db = self.ingestion.db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        audio_path: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Ingests an audio file, extracts features and indexes the track.

        Steps:
        1. Ingest and normalise via M1 — returns a UUID ``job_id``.
        2. Extract acoustic features (BPM, key, MFCC …) via M2.
        3. Extract CLAP embedding via M2.
        4. Index embedding + metadata in the ChromaDB vector store (M3).

        Args:
            audio_path: Path to the source audio file (WAV/MP3/FLAC).
            metadata: Optional dict with keys ``title``, ``artist``,
                ``genre``, ``bpm_manual``, ``mood``.

        Returns:
            36-character UUID string assigned to this track.
        """
        job_id = self.ingestion.ingest(audio_path, metadata)
        processed_path = str(Path(self.processed_dir) / f"{job_id}.wav")

        self.extractor.extract_acoustic(job_id, processed_path)
        embedding = self.extractor.extract_embedding(job_id, processed_path)

        index_meta = {
            k: (v if v is not None else "")
            for k, v in {
                "title": metadata.get("title", "") if metadata else "",
                "genre": metadata.get("genre", "") if metadata else "",
                "bpm": float(metadata.get("bpm", 0.0)) if metadata else 0.0,
                "mood": metadata.get("mood", "") if metadata else "",
                "key": "",
            }.items()
        }
        self.vector_store.index(job_id, embedding, index_meta)

        return job_id

    def search_similar(
        self,
        audio_path: str,
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Finds tracks most similar to a query audio file.

        Generates a CLAP embedding for *audio_path*, searches the vector
        store, and optionally restricts results to tracks matching
        *filters* via the catalog store.

        Args:
            audio_path: Path to the query audio file.
            top_k: Maximum number of results to return.
            filters: Optional dict of catalog filter criteria (e.g.
                ``{'genre': 'jazz'}``).  Keys must match parameters
                accepted by :meth:`~src.matching.catalog_store.CatalogStore.filter`.

        Returns:
            List of dicts with at least ``job_id`` and ``similarity_score``,
            sorted by similarity descending.
        """
        embedding = self.extractor.extract_embedding("_query_tmp", audio_path)
        results = self.vector_store.search(embedding, top_k=top_k * 2)

        if filters:
            filtered_ids = {r["job_id"] for r in self.catalog_store.filter(**filters)}
            results = [r for r in results if r["job_id"] in filtered_ids]

        return results[:top_k]
