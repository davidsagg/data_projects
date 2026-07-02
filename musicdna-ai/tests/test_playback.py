"""TDD tests for src/simulator/playback.py — Module M11 SessionPlayback.

Test cases TC-M11-001 to TC-M11-002.
Production module not yet implemented — these tests are expected to fail
until SessionPlayback is created.
"""

import os

import note_seq
import pytest

from src.simulator.playback import SessionPlayback
from src.simulator.session import SessionConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_ns():
    """NoteSequence with 3 notes at 120 BPM."""
    ns = note_seq.NoteSequence()
    ns.tempos.add(qpm=120)
    ns.notes.add(pitch=60, start_time=0.0, end_time=0.5, velocity=80)
    ns.notes.add(pitch=64, start_time=0.5, end_time=1.0, velocity=80)
    ns.notes.add(pitch=67, start_time=1.0, end_time=1.5, velocity=80)
    ns.total_time = 1.5
    return ns


@pytest.fixture
def session():
    """SessionConfig for a jazz session in C major."""
    return SessionConfig(style="jazz", key="C", bpm=120, mood="relaxado")


# ---------------------------------------------------------------------------
# TC-M11-001: export_midi creates a valid MIDI file
# ---------------------------------------------------------------------------


def test_export_session_creates_midi_file(sample_ns, session, tmp_path):
    """TC-M11-001: export_midi must create a MIDI file readable by music21
    with the correct number of notes."""
    import music21

    pb = SessionPlayback(export_dir=str(tmp_path))
    midi_path = pb.export_midi(sample_ns, session.session_id)

    assert os.path.exists(midi_path)
    score = music21.converter.parse(midi_path)
    assert len(score.flatten().notes) == 3


# ---------------------------------------------------------------------------
# TC-M11-002: session_summary contains all required fields
# ---------------------------------------------------------------------------


def test_session_summary_contains_required_fields(session, tmp_path):
    """TC-M11-002: session_summary must return a dict with all required keys."""
    pb = SessionPlayback(export_dir=str(tmp_path))
    progression = [
        {"chord_name": "Dm7", "midi_notes": [62, 65, 69, 72]},
        {"chord_name": "G7", "midi_notes": [67, 71, 74, 77]},
    ]
    suggestion = "Use a escala de Do maior sobre toda a progressao."
    midi_path = str(tmp_path / "test.mid")

    summary = pb.session_summary(session, progression, suggestion, midi_path)

    required = [
        "session_id",
        "style",
        "key",
        "bpm",
        "mood",
        "bars",
        "chord_sequence",
        "suggestion",
        "midi_path",
    ]
    for field in required:
        assert field in summary, f"Campo ausente: {field}"
    assert isinstance(summary["chord_sequence"], list)
    assert summary["style"] == "jazz"
