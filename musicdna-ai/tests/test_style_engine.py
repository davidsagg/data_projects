"""TDD tests for src/simulator/style_engine.py — Module M9.

Test cases TC-M9-001 to TC-M9-004.
Production module not yet implemented — these tests are expected to fail
until StyleEngine is created.
"""

import pytest

from src.simulator.style_engine import StyleEngine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def jazz_engine():
    """StyleEngine configured for jazz in C major, relaxado mood."""
    return StyleEngine(style="jazz", key="C", mood="relaxado")


@pytest.fixture
def mpb_engine():
    """StyleEngine configured for MPB in G major, melancolico mood."""
    return StyleEngine(style="mpb", key="G", mood="melancolico")


# ---------------------------------------------------------------------------
# TC-M9-001: jazz progression returns chord sequence
# ---------------------------------------------------------------------------


def test_jazz_progression_returns_chord_sequence(jazz_engine):
    """TC-M9-001: generate_progression must return one chord dict per bar
    with chord_name (str) and midi_notes (list of ints in [48, 84])."""
    progression = jazz_engine.generate_progression(bars=4)
    assert len(progression) == 4
    for chord in progression:
        assert "chord_name" in chord
        assert "midi_notes" in chord
        assert isinstance(chord["chord_name"], str)
        assert isinstance(chord["midi_notes"], list)
        assert all(48 <= n <= 84 for n in chord["midi_notes"])


# ---------------------------------------------------------------------------
# TC-M9-002: MPB progression returns chord sequence with triads
# ---------------------------------------------------------------------------


def test_mpb_progression_returns_chord_sequence(mpb_engine):
    """TC-M9-002: MPB progression must return 4 chords each with >= 3 notes."""
    progression = mpb_engine.generate_progression(bars=4)
    assert len(progression) == 4
    for chord in progression:
        assert "chord_name" in chord
        assert len(chord["midi_notes"]) >= 3  # pelo menos triade


# ---------------------------------------------------------------------------
# TC-M9-003: progression respects key transposition
# ---------------------------------------------------------------------------


def test_progression_respects_key_transposition():
    """TC-M9-003: the first chord in D major must contain MIDI note 62 (D)."""
    engine = StyleEngine(style="jazz", key="D", mood="animado")
    progression = engine.generate_progression(bars=2)
    # I grau em Re maior = Dmaj7 = [62, 66, 69, 73]
    first_chord = progression[0]
    assert (
        62 in first_chord["midi_notes"]
    ), f"Nota Re (62) ausente no primeiro acorde: {first_chord}"


# ---------------------------------------------------------------------------
# TC-M9-004: melody notes within C major scale
# ---------------------------------------------------------------------------


def test_generate_melody_notes_within_scale(jazz_engine):
    """TC-M9-004: all melody notes must belong to the C major scale
    (pitch classes 0, 2, 4, 5, 7, 9, 11)."""
    progression = jazz_engine.generate_progression(bars=4)
    melody = jazz_engine.generate_melody(progression, bars=4)
    # Escala de Do maior: C D E F G A B (+ oitavas)
    c_major_pcs = {0, 2, 4, 5, 7, 9, 11}
    assert len(melody) > 0
    for note in melody:
        assert isinstance(note, dict)
        assert "pitch" in note and "start_time" in note and "end_time" in note
        assert (
            note["pitch"] % 12 in c_major_pcs
        ), f"Nota {note['pitch']} fora da escala de Do maior"
