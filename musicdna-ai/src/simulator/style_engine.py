"""Style Engine for MusicDNA AI — Module M9.

Generates chord progressions and melodies based on musical style, key and mood.
"""

from __future__ import annotations

import random
from typing import Literal

# ---------------------------------------------------------------------------
# Music theory constants
# ---------------------------------------------------------------------------

# Chord intervals in semitones from root.
CHORD_INTERVALS: dict[str, list[int]] = {
    "maj7": [0, 4, 7, 11],  # major with major seventh
    "m7": [0, 3, 7, 10],  # minor with minor seventh
    "7": [0, 4, 7, 10],  # dominant seventh
    "m7b5": [0, 3, 6, 10],  # half-diminished
}

# MIDI note number for each key name at octave 4.
NOTE_TO_MIDI: dict[str, int] = {
    "C": 60,
    "C#": 61,
    "Db": 61,
    "D": 62,
    "D#": 63,
    "Eb": 63,
    "E": 64,
    "F": 65,
    "F#": 66,
    "Gb": 66,
    "G": 67,
    "G#": 68,
    "Ab": 68,
    "A": 69,
    "A#": 70,
    "Bb": 70,
    "B": 71,
}

# Chord progressions per style and mood (scale degree + chord type).
PROGRESSIONS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "jazz": {
        "relaxado": [("II", "m7"), ("V", "7"), ("I", "maj7"), ("VI", "m7")],
        "animado": [("I", "maj7"), ("II", "m7"), ("V", "7"), ("I", "maj7")],
        "melancolico": [("I", "m7"), ("IV", "7"), ("VII", "maj7"), ("III", "7")],
        "energetico": [("I", "7"), ("IV", "7"), ("I", "7"), ("V", "7")],
    },
    "mpb": {
        "relaxado": [("IV", "maj7"), ("I", "7"), ("II", "m7"), ("V", "7")],
        "melancolico": [("I", "m7"), ("VI", "maj7"), ("II", "m7b5"), ("V", "7")],
        "animado": [("I", "maj7"), ("VI", "m7"), ("II", "m7"), ("V", "7")],
        "energetico": [("I", "7"), ("II", "m7"), ("V", "7"), ("I", "maj7")],
    },
}

# Scale degree offsets in semitones from the tonic (major scale).
MAJOR_DEGREES: dict[str, int] = {
    "I": 0,
    "II": 2,
    "III": 4,
    "IV": 5,
    "V": 7,
    "VI": 9,
    "VII": 11,
}

# Pitch classes of the major scale.
MAJOR_SCALE_PCS: list[int] = [0, 2, 4, 5, 7, 9, 11]

# Chromatic note names for MIDI-to-name conversion.
_NOTE_NAMES: list[str] = [
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
]


# ---------------------------------------------------------------------------
# StyleEngine
# ---------------------------------------------------------------------------


class StyleEngine:
    """Generates chord progressions and melodies for a given style and key.

    Attributes:
        style: Musical style (``'jazz'`` or ``'mpb'``).
        key: Root key name (e.g. ``'C'``, ``'F#'``).
        mood: Emotional mood of the session.
        root_midi: MIDI note number of the tonic at octave 4.
        progression_template: List of (degree, chord_type) pairs for this
            style/mood combination.
    """

    def __init__(self, style: str, key: str, mood: str) -> None:
        """Initialises the engine with style, key and mood parameters.

        Args:
            style: Musical style — ``'jazz'`` or ``'mpb'``.
            key: Root key name (e.g. ``'C'``, ``'D'``, ``'Bb'``).
            mood: Emotional mood (e.g. ``'relaxado'``, ``'animado'``).
        """
        self.style = style
        self.key = key
        self.mood = mood
        self.root_midi = NOTE_TO_MIDI[key]
        self.progression_template = PROGRESSIONS[style].get(
            mood, PROGRESSIONS[style]["relaxado"]
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_progression(self, bars: int = 4) -> list[dict]:
        """Generates a harmonic progression for the given number of bars.

        Each bar maps to one chord dict.  The template cycles if *bars*
        exceeds the template length.

        Args:
            bars: Number of bars (chords) to generate.

        Returns:
            List of dicts, each with ``chord_name`` (str) and
            ``midi_notes`` (list of int).
        """
        result: list[dict] = []
        template_len = len(self.progression_template)
        for i in range(bars):
            degree, chord_type = self.progression_template[i % template_len]
            degree_offset = MAJOR_DEGREES[degree]
            root = self.root_midi + degree_offset
            intervals = CHORD_INTERVALS[chord_type]
            midi_notes = [root + interval for interval in intervals]
            chord_name = f"{self._midi_to_name(root)}{chord_type}"
            result.append({"chord_name": chord_name, "midi_notes": midi_notes})
        return result

    def generate_melody(self, progression: list[dict], bars: int = 4) -> list[dict]:
        """Generates a melodic line over the given chord progression.

        Produces 4 notes per bar, each chosen from the tonic major scale.
        All pitches are constrained to the scale pitch classes of the
        session key.

        Args:
            progression: List of chord dicts as returned by
                :meth:`generate_progression`.
            bars: Number of bars of melody to generate.

        Returns:
            List of note dicts, each with ``pitch`` (int), ``start_time``
            (float), ``end_time`` (float) and ``velocity`` (int).
        """
        beat_duration = 60.0 / 120  # seconds per beat at 120 BPM
        notes: list[dict] = []
        for i, chord in enumerate(progression[:bars]):
            start_bar = i * 4 * beat_duration
            for beat in range(4):
                pc = random.choice(MAJOR_SCALE_PCS)
                pitch = self.root_midi + pc
                if pitch < 60:
                    pitch += 12  # ensure audible octave
                start = start_bar + beat * beat_duration
                notes.append(
                    {
                        "pitch": pitch,
                        "start_time": start,
                        "end_time": start + beat_duration * 0.9,
                        "velocity": 70,
                    }
                )
        return notes

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _midi_to_name(self, midi: int) -> str:
        """Converts a MIDI note number to its chromatic note name.

        Args:
            midi: MIDI note number (0–127).

        Returns:
            Note name string (e.g. ``'C'``, ``'F#'``).
        """
        return _NOTE_NAMES[midi % 12]
