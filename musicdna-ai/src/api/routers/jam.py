"""JAM session router for MusicDNA AI.

Provides POST /jam/session and GET /jam/session/{session_id} endpoints.
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/jam", tags=["Jam Session"])

# In-memory session storage (sufficient for development).
_sessions: dict = {}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class JamSessionRequest(BaseModel):
    """Request body for POST /jam/session.

    Attributes:
        style: Musical style — ``'jazz'`` or ``'mpb'``.
        key: Root key (e.g. ``'C'``, ``'F#'``).
        bpm: Tempo in beats per minute, between 40 and 240.
        mood: Emotional mood descriptor.
        bars: Number of bars to generate, between 2 and 32.
    """

    style: Literal["jazz", "mpb"]
    key: str = "C"
    bpm: int = Field(default=120, ge=40, le=240)
    mood: str = "relaxado"
    bars: int = Field(default=8, ge=2, le=32)


class JamSessionResponse(BaseModel):
    """Response body for POST and GET /jam/session endpoints.

    Attributes:
        session_id: UUID identifying the session.
        style: Musical style used.
        key: Root key used.
        bpm: Tempo used.
        mood: Mood used.
        bars: Number of bars generated.
        chord_sequence: List of chord name strings.
        suggestion: Ollama improvisation suggestion.
        midi_path: Path to the generated MIDI file.
    """

    session_id: str
    style: str
    key: str
    bpm: int
    mood: str
    bars: int
    chord_sequence: list[str]
    suggestion: str
    midi_path: str


# ---------------------------------------------------------------------------
# Injectable dependency
# ---------------------------------------------------------------------------


def get_jam_generator():
    """Returns a production JamGenerator instance.

    Returns:
        :class:`~src.simulator.generator.JamGenerator` wired to production paths.
    """
    from src.simulator.generator import JamGenerator

    return JamGenerator(
        output_dir="/workspace/data/sessions",
        ollama_base_url=os.getenv(
            "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
        ),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/session", response_model=JamSessionResponse)
def create_jam_session(
    request: JamSessionRequest,
    generator=Depends(get_jam_generator),
) -> JamSessionResponse:
    """Creates a new jam session and returns MIDI and improvisation suggestion.

    Args:
        request: :class:`JamSessionRequest` with style, key, BPM, mood and bars.
        generator: Injected :class:`~src.simulator.generator.JamGenerator`.

    Returns:
        :class:`JamSessionResponse` with session data and MIDI path.
    """
    from src.simulator.session import SessionConfig
    from src.simulator.style_engine import StyleEngine

    session = SessionConfig(
        style=request.style,
        key=request.key,
        bpm=request.bpm,
        mood=request.mood,
        bars=request.bars,
    )
    style_engine = StyleEngine(request.style, request.key, request.mood)
    progression = style_engine.generate_progression(bars=request.bars)
    result = generator.generate(session, progression)

    response_data = JamSessionResponse(
        session_id=result["session_id"],
        style=request.style,
        key=request.key,
        bpm=request.bpm,
        mood=request.mood,
        bars=request.bars,
        chord_sequence=result["chord_sequence"],
        suggestion=result["suggestion"],
        midi_path=result["midi_path"],
    )
    _sessions[result["session_id"]] = response_data
    return response_data


@router.get("/session/{session_id}", response_model=JamSessionResponse)
def get_jam_session(session_id: str) -> JamSessionResponse:
    """Retrieves a previously created jam session by ID.

    Args:
        session_id: UUID of the session to retrieve.

    Returns:
        :class:`JamSessionResponse` for the requested session.

    Raises:
        HTTPException: HTTP 404 when *session_id* is not found.
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    return _sessions[session_id]
