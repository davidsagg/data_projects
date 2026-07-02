"""Matching Engine for MusicDNA AI — Module M5.

Combines vector similarity search (M3), structured catalog filters (M4)
and LLM-generated justifications (Ollama) to recommend tracks for
sync-licensing projects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import requests

from src.audio.features import FeatureExtractor


@dataclass
class MatchResult:
    """A single track recommendation produced by the Matching Engine.

    Attributes:
        job_id: Unique identifier from M1 ingestion.
        title: Track title.
        artist: Artist name.
        similarity_score: Cosine similarity score in [0, 1].
        justification: LLM-generated explanation of the recommendation.
        genre: Musical genre.
        bpm: Beats per minute.
        mood: Mood descriptor.
    """

    job_id: str
    title: str
    artist: str
    similarity_score: float
    justification: str
    genre: str
    bpm: float
    mood: str


class MatchingEngine:
    """Combines semantic search, catalog filters and LLM justifications.

    Attributes:
        vector_store: M3 VectorStore used for embedding-based search.
        catalog_store: M4 CatalogStore used for structured filtering.
        ollama_base_url: Base URL of the running Ollama server.
        model_name: Ollama model tag used for justification generation.
    """

    def __init__(
        self,
        vector_store,
        catalog_store,
        ollama_base_url: str,
        model_name: str = "llama3",
    ) -> None:
        """Initialises engine dependencies.

        Args:
            vector_store: Pre-built :class:`~src.matching.vector_store.VectorStore`
                instance.
            catalog_store: Pre-built :class:`~src.matching.catalog_store.CatalogStore`
                instance.
            ollama_base_url: Base URL of the running Ollama server
                (e.g. ``'http://localhost:11434'``).
            model_name: Model tag served by Ollama (e.g. ``'llama3'``).
        """
        self.vector_store = vector_store
        self.catalog_store = catalog_store
        self.ollama_base_url = ollama_base_url
        self.model_name = model_name
        self._extractor: Optional[FeatureExtractor] = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(
        self,
        query: str = "",
        audio_path: str = "",
        top_k: int = 10,
        filters: Optional[dict] = None,
        context: str = "",
    ) -> list[MatchResult]:
        """Finds and ranks tracks for a sync-licensing context.

        Accepts either a *query* text string or an *audio_path* to a
        reference file.  Results from the vector store are optionally
        filtered through the catalog store and annotated with an LLM
        justification.

        Args:
            query: Text description of the desired music.
            audio_path: Path to a reference audio file.  Takes precedence
                over *query* when both are provided.
            top_k: Maximum number of results to return.
            filters: Optional dict for structured catalog filtering.
                Supported keys: ``genre``, ``mood``, ``bpm_min``,
                ``bpm_max``.
            context: Free-text licensing context used in the LLM prompt.
                Defaults to *query* when omitted.

        Returns:
            List of :class:`MatchResult` sorted by ``similarity_score``
            descending.
        """
        if audio_path:
            embedding = self._embed_audio(audio_path)
        else:
            embedding = self._embed_text(query)

        raw = self.vector_store.search(embedding, top_k=top_k * 2)

        catalog_lookup: dict[str, dict] = {}
        if filters:
            catalog_rows = self.catalog_store.filter(**filters)
            filtered_ids = {r["job_id"] for r in catalog_rows}
            catalog_lookup = {r["job_id"]: r for r in catalog_rows}
            raw = [r for r in raw if r["job_id"] in filtered_ids]

        raw = raw[:top_k]
        context_desc = context if context else query

        results: list[MatchResult] = []
        for item in raw:
            cat = catalog_lookup.get(item["job_id"], {})
            try:
                justification = self._call_ollama(item, context_desc)
            except Exception:  # noqa: BLE001 — covers TimeoutError and network errors
                justification = "[justificativa nao disponivel]"
            results.append(
                MatchResult(
                    job_id=item["job_id"],
                    title=item.get("title") or cat.get("title", ""),
                    artist=cat.get("artist") or item.get("artist", ""),
                    similarity_score=float(item["similarity_score"]),
                    justification=justification,
                    genre=item.get("genre") or cat.get("genre", ""),
                    bpm=float(item.get("bpm") or cat.get("bpm", 0.0)),
                    mood=item.get("mood") or cat.get("mood", ""),
                )
            )
        return results

    # ------------------------------------------------------------------
    # Private — embeddings
    # ------------------------------------------------------------------

    def _embed_text(self, text: str) -> np.ndarray:
        """Encodes a text string with the CLAP text encoder.

        Lazily loads ``laion/clap-htsat-unfused`` on first call.

        Args:
            text: Input text to encode.

        Returns:
            Float32 NumPy array of shape ``(512,)``.
        """
        import torch
        from transformers import ClapModel, ClapProcessor

        if not hasattr(self, "_clap_model") or self._clap_model is None:
            model_id = "laion/clap-htsat-unfused"
            self._clap_processor = ClapProcessor.from_pretrained(model_id)
            self._clap_model = ClapModel.from_pretrained(model_id)
            self._clap_model.eval()

        inputs = self._clap_processor.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=77,
        )
        with torch.no_grad():
            output = self._clap_model.get_text_features(**inputs)
            # Newer transformers versions return BaseModelOutputWithPooling
            # instead of a raw tensor — extract the pooled representation.
            if hasattr(output, "pooler_output"):
                output = output.pooler_output
            embedding = output.squeeze(0).cpu().numpy().astype(np.float32)
        return embedding

    def _embed_audio(self, audio_path: str) -> np.ndarray:
        """Encodes an audio file using :class:`~src.audio.features.FeatureExtractor`.

        Args:
            audio_path: Path to a WAV/MP3/FLAC file.

        Returns:
            Float32 NumPy array of shape ``(512,)``.
        """
        if self._extractor is None:
            import tempfile

            self._extractor = FeatureExtractor(
                embeddings_dir=tempfile.mkdtemp(),
            )
        return self._extractor.extract_embedding("_query", audio_path)

    # ------------------------------------------------------------------
    # Private — LLM justification
    # ------------------------------------------------------------------

    def _call_ollama(self, track_meta: dict, context: str) -> str:
        """Calls the Ollama REST API to generate a licensing justification.

        Args:
            track_meta: Dict with ``title``, ``bpm``, ``key``, ``genre``
                and ``mood`` fields.
            context: Free-text description of the licensing project.

        Returns:
            Justification string from the LLM.

        Raises:
            TimeoutError: When the request exceeds the 30-second timeout.
            requests.RequestException: On any other HTTP error.
        """
        prompt = (
            f"Voce e especialista em licenciamento musical. "
            f"A faixa \"{track_meta['title']}\" tem BPM {track_meta.get('bpm', 'N/A')}, "
            f"tonalidade {track_meta.get('key', 'desconhecida')}, "
            f"genero {track_meta.get('genre', 'N/A')} e mood {track_meta.get('mood', 'N/A')}. "
            f"Em 2 frases, explique por que ela e adequada para: {context}"
        )
        try:
            resp = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={"model": self.model_name, "prompt": prompt, "stream": False},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["response"].strip()
        except requests.Timeout as exc:
            raise TimeoutError("Ollama request timed out") from exc
