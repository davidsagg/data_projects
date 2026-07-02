"""FastAPI application for MusicDNA AI — Module M6.

Exposes endpoints for audio ingestion, track matching and health checks.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Optional

import requests
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.api.routers.jam import get_jam_generator
from src.api.routers.jam import router as jam_router

app = FastAPI(
    title="MusicDNA AI - Sync Licensing Matcher",
    description="API para matching de musicas para licenciamento",
    version="1.0.0",
)

app.include_router(jam_router)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class MatchRequest(BaseModel):
    """Request body for POST /match.

    Attributes:
        query: Text description of the desired music (required).
        top_k: Maximum number of results to return.
        filters: Optional catalog filters (e.g. ``{'genre': 'jazz'}``).
        context: Free-text licensing context for the LLM prompt.
    """

    query: str
    top_k: int = 5
    filters: Optional[dict] = None
    context: Optional[str] = ""


class MatchResultResponse(BaseModel):
    """Single track recommendation returned by POST /match.

    Attributes:
        job_id: Unique track identifier.
        title: Track title.
        artist: Artist name.
        similarity_score: Cosine similarity score in [0, 1].
        justification: LLM-generated licensing justification.
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


class MatchResponse(BaseModel):
    """Response envelope for POST /match.

    Attributes:
        results: List of track recommendations.
        total: Number of results returned.
    """

    results: list[MatchResultResponse]
    total: int


# ---------------------------------------------------------------------------
# Injectable dependencies
# ---------------------------------------------------------------------------


def get_pipeline():
    """Returns a production AudioPipeline instance.

    Returns:
        :class:`~src.pipeline.AudioPipeline` wired to production paths.
    """
    from src.pipeline import AudioPipeline

    return AudioPipeline(
        processed_dir="/workspace/data/processed",
        embeddings_dir="/workspace/data/embeddings",
        chroma_dir="/workspace/data/embeddings/chroma",
        db_path="/workspace/data/catalog.duckdb",
    )


def get_engine():
    """Returns a production MatchingEngine instance.

    Returns:
        :class:`~src.matching.engine.MatchingEngine` wired to production stores.
    """
    from src.matching.catalog_store import CatalogStore
    from src.matching.engine import MatchingEngine
    from src.matching.vector_store import VectorStore

    vs = VectorStore(persist_dir="/workspace/data/embeddings/chroma")
    cat = CatalogStore(db_path="/workspace/data/catalog.duckdb")
    return MatchingEngine(
        vector_store=vs,
        catalog_store=cat,
        ollama_base_url=os.getenv(
            "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
        ),
        model_name="llama3",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/ingest")
async def ingest(
    audio_file: UploadFile = File(...),
    title: str = Form(""),
    artist: str = Form(""),
    genre: str = Form(""),
    bpm_manual: float = Form(0.0),
    mood: str = Form(""),
    pipeline=Depends(get_pipeline),
) -> dict:
    """Ingests an audio file and indexes it in the catalog.

    Args:
        audio_file: Uploaded WAV/MP3/FLAC file.
        title: Track title.
        artist: Artist name.
        genre: Musical genre.
        bpm_manual: BPM (manually provided).
        mood: Mood descriptor.
        pipeline: Injected :class:`~src.pipeline.AudioPipeline` instance.

    Returns:
        Dict with ``job_id`` and ``status``.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        shutil.copyfileobj(audio_file.file, tmp)
        tmp_path = tmp.name

    metadata = {
        "title": title,
        "artist": artist,
        "genre": genre,
        "bpm": bpm_manual,
        "mood": mood,
    }
    job_id = pipeline.run(tmp_path, metadata=metadata)
    return {"job_id": job_id, "status": "processed"}


@app.post("/match", response_model=MatchResponse)
def match(
    request: MatchRequest,
    engine=Depends(get_engine),
) -> MatchResponse:
    """Finds tracks matching a text query.

    Args:
        request: :class:`MatchRequest` with query and optional filters.
        engine: Injected :class:`~src.matching.engine.MatchingEngine` instance.

    Returns:
        :class:`MatchResponse` with ranked track recommendations.
    """
    results = engine.match(
        query=request.query,
        top_k=request.top_k,
        filters=request.filters,
        context=request.context or "",
    )
    return MatchResponse(
        results=[MatchResultResponse(**vars(r)) for r in results],
        total=len(results),
    )


@app.get("/health")
def health() -> dict:
    """Returns the health status of the API and Ollama connectivity.

    Returns:
        Dict with ``status`` and ``ollama`` reachability.
    """
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=3)
        ollama_status = "reachable" if resp.status_code == 200 else "unreachable"
    except Exception:  # noqa: BLE001
        ollama_status = "unreachable"
    return {"status": "ok", "ollama": ollama_status}
