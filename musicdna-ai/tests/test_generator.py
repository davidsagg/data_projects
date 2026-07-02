"""TDD tests for src/simulator/generator.py — Module M10 JamGenerator.

Test cases TC-M10-001 to TC-M10-004.
Production module not yet implemented — these tests are expected to fail
until JamGenerator is created.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.simulator.session import SessionConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    """SessionConfig for a 4-bar jazz session in C major."""
    return SessionConfig(style="jazz", key="C", bpm=120, mood="relaxado", bars=4)


@pytest.fixture
def progression():
    """Four-chord jazz progression (II-V-I-VI in C major)."""
    return [
        {"chord_name": "Dm7", "midi_notes": [62, 65, 69, 72]},
        {"chord_name": "G7", "midi_notes": [67, 71, 74, 77]},
        {"chord_name": "Cmaj7", "midi_notes": [60, 64, 67, 71]},
        {"chord_name": "Am7", "midi_notes": [69, 72, 76, 79]},
    ]


# ---------------------------------------------------------------------------
# TC-M10-001: generate() creates a non-empty MIDI file
# ---------------------------------------------------------------------------


@patch("src.simulator.generator.JamGenerator._call_ollama")
def test_generate_midi_creates_file(mock_ollama, session, progression, tmp_path):
    """TC-M10-001: generate() must create a non-empty MIDI file on disk."""
    from src.simulator.generator import JamGenerator

    mock_ollama.return_value = "Improvise sobre a tercia do acorde."
    gen = JamGenerator(
        output_dir=str(tmp_path),
        ollama_base_url="http://host.docker.internal:11434",
    )
    result = gen.generate(session, progression)
    assert os.path.exists(result["midi_path"])
    assert os.path.getsize(result["midi_path"]) > 0


# ---------------------------------------------------------------------------
# TC-M10-002: MIDI file contains the correct tempo
# ---------------------------------------------------------------------------


@patch("src.simulator.generator.JamGenerator._call_ollama")
def test_midi_has_correct_tempo(mock_ollama, session, progression, tmp_path):
    """TC-M10-002: the MIDI file tempo must match session BPM (120)."""
    import note_seq

    from src.simulator.generator import JamGenerator

    mock_ollama.return_value = "Sugestao."
    gen = JamGenerator(
        output_dir=str(tmp_path),
        ollama_base_url="http://host.docker.internal:11434",
    )
    result = gen.generate(session, progression)
    ns = note_seq.midi_file_to_note_sequence(result["midi_path"])
    assert abs(ns.tempos[0].qpm - 120.0) < 1.0


# ---------------------------------------------------------------------------
# TC-M10-003: MIDI file contains notes from the progression
# ---------------------------------------------------------------------------


@patch("src.simulator.generator.JamGenerator._call_ollama")
def test_midi_has_notes_from_progression(mock_ollama, session, progression, tmp_path):
    """TC-M10-003: the MIDI file must contain at least 4 notes."""
    import note_seq

    from src.simulator.generator import JamGenerator

    mock_ollama.return_value = "Sugestao."
    gen = JamGenerator(
        output_dir=str(tmp_path),
        ollama_base_url="http://host.docker.internal:11434",
    )
    result = gen.generate(session, progression)
    ns = note_seq.midi_file_to_note_sequence(result["midi_path"])
    assert len(ns.notes) >= 4


# ---------------------------------------------------------------------------
# TC-M10-004: Ollama suggestion returned in result dict
# ---------------------------------------------------------------------------


@patch("src.simulator.generator.JamGenerator._call_ollama")
def test_ollama_suggestion_returned(mock_ollama, session, progression, tmp_path):
    """TC-M10-004: result dict must include the Ollama suggestion string."""
    from src.simulator.generator import JamGenerator

    mock_ollama.return_value = "Use a escala lidia sobre o Cmaj7."
    gen = JamGenerator(
        output_dir=str(tmp_path),
        ollama_base_url="http://host.docker.internal:11434",
    )
    result = gen.generate(session, progression)
    assert "suggestion" in result
    assert len(result["suggestion"]) > 0
    assert result["suggestion"] == "Use a escala lidia sobre o Cmaj7."
