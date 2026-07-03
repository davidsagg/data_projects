"""Jam session generator for MusicDNA AI — Module M10.

Combines StyleEngine melody generation, note_seq MIDI assembly and
Ollama improvisation suggestions into a single output artefact.
"""

from __future__ import annotations

import os
from pathlib import Path

import note_seq
import requests

from src.simulator.session import SessionConfig
from src.simulator.style_engine import StyleEngine


class JamGenerator:
    """Generates a MIDI file and an improvisation suggestion for a jam session.

    Attributes:
        output_dir: Directory where MIDI files are written.
        ollama_base_url: Base URL of the running Ollama server.
        model_name: Ollama model tag used for suggestion generation.
    """

    def __init__(
        self,
        output_dir: str,
        ollama_base_url: str = "http://localhost:11434",
        model_name: str = "llama3",
    ) -> None:
        """Initialises the generator and ensures the output directory exists.

        Args:
            output_dir: Filesystem path for MIDI output files.
            ollama_base_url: Base URL of the running Ollama server.
            model_name: Ollama model tag (e.g. ``'llama3'``).
        """
        self.output_dir = output_dir
        self.ollama_base_url = ollama_base_url
        self.model_name = model_name
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        session: SessionConfig,
        progression: list[dict],
    ) -> dict:
        """Generates a MIDI file and improvisation suggestion for the session.

        Steps:
        1. Generate a melody via :class:`~src.simulator.style_engine.StyleEngine`.
        2. Build a :class:`note_seq.NoteSequence` with chords and melody.
        3. Write the sequence to a MIDI file.
        4. Request an improvisation suggestion from Ollama.

        Args:
            session: :class:`~src.simulator.session.SessionConfig` with style,
                key, BPM, mood and bar count.
            progression: List of chord dicts (``chord_name``, ``midi_notes``)
                as returned by :meth:`~src.simulator.style_engine.StyleEngine\
.generate_progression`.

        Returns:
            Dict with keys ``session_id``, ``midi_path``, ``chord_sequence``
            and ``suggestion``.
        """
        style_engine = StyleEngine(
            style=session.style, key=session.key, mood=session.mood
        )
        melody_notes = style_engine.generate_melody(progression, bars=session.bars)

        ns = note_seq.NoteSequence()
        ns.tempos.add(qpm=float(session.bpm))

        beat_dur = 60.0 / session.bpm

        # Add chord notes (simultaneous).
        for i, chord in enumerate(progression[: session.bars]):
            start = i * 4 * beat_dur
            end = start + 4 * beat_dur - 0.1
            for pitch in chord["midi_notes"]:
                ns.notes.add(
                    pitch=pitch,
                    start_time=start,
                    end_time=end,
                    velocity=60,
                )

        # Add melody notes.
        for note in melody_notes:
            ns.notes.add(
                pitch=note["pitch"],
                start_time=note["start_time"],
                end_time=note["end_time"],
                velocity=note["velocity"],
            )

        ns.total_time = session.bars * 4 * beat_dur

        midi_path = os.path.join(self.output_dir, f"{session.session_id}.mid")
        note_seq.sequence_proto_to_midi_file(ns, midi_path)

        chord_names = [c["chord_name"] for c in progression[:4]]
        try:
            suggestion = self._call_ollama(session, chord_names)
        except Exception:  # noqa: BLE001
            suggestion = "[sugestao nao disponivel]"

        return {
            "session_id": session.session_id,
            "midi_path": midi_path,
            "chord_sequence": chord_names,
            "suggestion": suggestion,
        }

    # ------------------------------------------------------------------
    # Private — LLM suggestion
    # ------------------------------------------------------------------

    def _call_ollama(
        self,
        session: SessionConfig,
        chords: list[str],
    ) -> str:
        """Requests an improvisation suggestion from Ollama.

        Args:
            session: Session config providing style, key, BPM and mood context.
            chords: List of chord name strings from the progression.

        Returns:
            Suggestion string from the LLM.

        Raises:
            requests.RequestException: On HTTP or network error.
            requests.Timeout: When the request exceeds 30 seconds.
        """
        prompt = (
            f"Voce e um professor de jazz e MPB. "
            f"O musico esta improvisando em {session.style.upper()} "
            f"na tonalidade de {session.key}, BPM {session.bpm}, "
            f"mood {session.mood}. "
            f"A progressao e: {' | '.join(chords)}. "
            f"Em 2 frases em portugues, sugira uma abordagem de improvisacao."
        )
        resp = requests.post(
            f"{self.ollama_base_url}/api/generate",
            json={"model": self.model_name, "prompt": prompt, "stream": False},
            timeout=30,
        )
        return resp.json()["response"].strip()
