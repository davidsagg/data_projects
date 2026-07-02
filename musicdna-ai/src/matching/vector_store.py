"""Vector Store for MusicDNA AI — Module M3.

Indexes CLAP embeddings in ChromaDB and provides cosine-similarity search.
"""

from __future__ import annotations

from typing import Optional

import chromadb
import numpy as np


class VectorStore:
    """Persists and queries CLAP audio embeddings using ChromaDB.

    ChromaDB with ``hnsw:space: cosine`` returns distances in [0, 2], where
    0 means identical vectors.  All public methods convert distances to
    similarity scores in [0, 1] using ``score = 1 - distance / 2``.

    Attributes:
        client: ChromaDB client instance.
        collection: ChromaDB collection used for storing track embeddings.
    """

    def __init__(
        self,
        persist_dir: str = "",
        collection_name: str = "tracks",
        _client: Optional[chromadb.ClientAPI] = None,
    ) -> None:
        """Initialises the vector store and ensures the collection exists.

        Args:
            persist_dir: Filesystem path for the persistent ChromaDB database.
            collection_name: Name of the ChromaDB collection.
            _client: Optional pre-built ChromaDB client used in tests.
                When supplied, *persist_dir* is ignored.
        """
        if _client is not None:
            self.client = _client
        else:
            self.client = chromadb.PersistentClient(path=persist_dir)

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index(
        self,
        job_id: str,
        embedding: np.ndarray,
        metadata: Optional[dict] = None,
    ) -> None:
        """Adds or updates a track embedding in the collection.

        ChromaDB only accepts ``str``, ``int``, ``float``, and ``bool`` as
        metadata values.  Any ``None`` value is replaced with an empty string
        before storage.

        Args:
            job_id: Unique track identifier used as the ChromaDB document ID.
            embedding: Float array of shape ``(512,)`` produced by M2 CLAP.
            metadata: Optional dict of track attributes.  ``None`` values are
                coerced to ``""`` automatically.
        """
        sanitized: dict = {}
        for k, v in (metadata or {}).items():
            if v is None:
                sanitized[k] = ""
            elif isinstance(v, float):
                sanitized[k] = float(v)
            else:
                sanitized[k] = v

        self.collection.upsert(
            ids=[job_id],
            embeddings=[np.asarray(embedding, dtype=np.float32).tolist()],
            metadatas=[sanitized],
        )

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> list[dict]:
        """Finds the most similar tracks to *query_embedding*.

        ChromaDB cosine distance is in [0, 2] (0 = identical).  Scores are
        converted via ``similarity = 1 - distance / 2`` and filtered by
        *threshold* before returning.

        Args:
            query_embedding: Float array of shape ``(512,)`` to search against.
            top_k: Maximum number of candidates to retrieve before filtering.
            threshold: Minimum similarity score (0–1) to include a result.

        Returns:
            List of dicts sorted by ``similarity_score`` descending.  Each
            dict contains ``job_id``, ``similarity_score``, and all metadata
            fields stored during :meth:`index`.  Returns ``[]`` when the
            collection is empty.
        """
        if self.count() == 0:
            return []

        n = min(top_k, max(1, self.count()))
        results = self.collection.query(
            query_embeddings=[np.asarray(query_embedding, dtype=np.float32).tolist()],
            n_results=n,
            include=["metadatas", "distances"],
        )

        hits: list[dict] = []
        for doc_id, dist, meta in zip(
            results["ids"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            score = round(1.0 - float(dist) / 2.0, 6)
            if score < threshold:
                continue
            entry = {"job_id": doc_id, "similarity_score": score}
            entry.update(meta)
            hits.append(entry)

        hits.sort(key=lambda h: h["similarity_score"], reverse=True)
        return hits

    def count(self) -> int:
        """Returns the number of tracks currently indexed.

        Returns:
            Integer count of documents in the collection.
        """
        return self.collection.count()

    def get_metadata(self, job_id: str) -> dict:
        """Retrieves stored metadata for a given job_id.

        Args:
            job_id: Unique identifier of the indexed track.

        Returns:
            Metadata dict stored during :meth:`index`, or ``{}`` if not found.
        """
        result = self.collection.get(ids=[job_id], include=["metadatas"])
        return result["metadatas"][0] if result["metadatas"] else {}
