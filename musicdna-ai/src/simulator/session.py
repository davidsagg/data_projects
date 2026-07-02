"""Session configuration model for MusicDNA AI — Module M8.

Defines and validates the parameters for a simulated jam session.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SessionConfig(BaseModel):
    """Configuration for a simulated jam session.

    Attributes:
        style: Musical style — ``'jazz'`` or ``'mpb'``.
        key: Musical key (e.g. ``'C'``, ``'F#'``, ``'Bb'``).
        bpm: Tempo in beats per minute, between 40 and 240.
        mood: Emotional mood of the session.
        bars: Number of bars to generate, between 2 and 32.
        session_id: Auto-generated UUID identifying this session.
    """

    style: Literal["jazz", "mpb"]
    key: str = "C"
    bpm: int = Field(default=120, ge=40, le=240)
    mood: str = "relaxado"
    bars: int = Field(default=8, ge=2, le=32)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """Validates that *v* is a recognised musical key.

        Args:
            v: Key string to validate.

        Returns:
            The validated key string.

        Raises:
            ValueError: If *v* is not in the list of valid keys.
        """
        valid_keys = [
            "C",
            "C#",
            "Db",
            "D",
            "D#",
            "Eb",
            "E",
            "F",
            "F#",
            "Gb",
            "G",
            "G#",
            "Ab",
            "A",
            "A#",
            "Bb",
            "B",
        ]
        if v not in valid_keys:
            raise ValueError(f"Key invalida: {v}. Use: {valid_keys}")
        return v

    @field_validator("mood")
    @classmethod
    def validate_mood(cls, v: str) -> str:
        """Validates that *v* is a recognised mood descriptor.

        Args:
            v: Mood string to validate.

        Returns:
            The validated mood string.

        Raises:
            ValueError: If *v* is not in the list of valid moods.
        """
        valid_moods = [
            "relaxado",
            "animado",
            "melancolico",
            "energetico",
            "alegre",
            "triste",
        ]
        if v not in valid_moods:
            raise ValueError(f"Mood invalido: {v}. Use: {valid_moods}")
        return v
