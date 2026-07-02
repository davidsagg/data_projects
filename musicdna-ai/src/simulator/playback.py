"""Session playback and export utilities for MusicDNA AI — Module M11.

Handles MIDI export and session summary generation.
"""

from __future__ import annotations

import os
from pathlib import Path

import note_seq

from src.simulator.session import SessionConfig


class SessionPlayback:
    """Exports jam session results to MIDI and produces summary dicts.

    Attributes:
        export_dir: Directory where MIDI files are written.
    """

    def __init__(self, export_dir: str) -> None:
        """Initialises the playback handler and ensures the export dir exists.

        Args:
            export_dir: Filesystem path for MIDI output files.
        """
        self.export_dir = export_dir
        Path(export_dir).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export_midi(self, note_sequence: note_seq.NoteSequence, session_id: str) -> str:
        """Exports a NoteSequence as a MIDI file.

        Args:
            note_sequence: The :class:`note_seq.NoteSequence` to serialise.
            session_id: Session UUID used as the output filename stem.

        Returns:
            Absolute path to the written MIDI file.
        """
        midi_path = os.path.join(self.export_dir, f"{session_id}.mid")
        note_seq.sequence_proto_to_midi_file(note_sequence, midi_path)
        return midi_path

    def session_summary(
        self,
        session: SessionConfig,
        progression: list[dict],
        suggestion: str,
        midi_path: str,
    ) -> dict:
        """Generates a complete summary dict for a finished jam session.

        Args:
            session: :class:`~src.simulator.session.SessionConfig` with all
                session parameters.
            progression: List of chord dicts (``chord_name``, ``midi_notes``).
            suggestion: Improvisation suggestion string from Ollama.
            midi_path: Path to the exported MIDI file.

        Returns:
            Dict with keys ``session_id``, ``style``, ``key``, ``bpm``,
            ``mood``, ``bars``, ``chord_sequence``, ``suggestion`` and
            ``midi_path``.
        """
        return {
            "session_id": session.session_id,
            "style": session.style,
            "key": session.key,
            "bpm": session.bpm,
            "mood": session.mood,
            "bars": session.bars,
            "chord_sequence": [c["chord_name"] for c in progression],
            "suggestion": suggestion,
            "midi_path": midi_path,
        }
