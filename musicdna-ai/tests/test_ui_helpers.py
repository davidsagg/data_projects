"""TDD tests for src/ui/helpers.py — UI helper functions.

Test cases TC-UI-001 to TC-UI-005.
Production module not yet implemented — these tests are expected to fail
until the helper functions are created.
"""

import pytest

# ---------------------------------------------------------------------------
# TC-UI-001: format match results for display
# ---------------------------------------------------------------------------


def test_format_match_results_for_display():
    """TC-UI-001: format_match_results must convert raw dicts to display rows
    with 'Faixa', 'Score (%)' and 'Justificativa' keys."""
    from src.ui.helpers import format_match_results

    results = [
        {
            "job_id": "j1",
            "title": "Jazz A",
            "artist": "Art1",
            "similarity_score": 0.92,
            "justification": "Ideal para o contexto.",
            "genre": "jazz",
            "bpm": 120.0,
            "mood": "relaxado",
        },
        {
            "job_id": "j2",
            "title": "MPB B",
            "artist": "Art2",
            "similarity_score": 0.74,
            "justification": "Boa escolha.",
            "genre": "mpb",
            "bpm": 90.0,
            "mood": "melancolico",
        },
    ]
    formatted = format_match_results(results)
    assert len(formatted) == 2
    assert "Faixa" in formatted[0]
    assert "Score (%)" in formatted[0]
    assert formatted[0]["Score (%)"] == 92.0
    assert "Justificativa" in formatted[0]


# ---------------------------------------------------------------------------
# TC-UI-002: format chord progression for display
# ---------------------------------------------------------------------------


def test_format_progression_for_display():
    """TC-UI-002: format_progression must return one dict per chord with
    'Compasso', 'Acorde' and 'Notas MIDI' keys."""
    from src.ui.helpers import format_progression

    progression = [
        {"chord_name": "Dm7", "midi_notes": [62, 65, 69, 72]},
        {"chord_name": "G7", "midi_notes": [67, 71, 74, 77]},
        {"chord_name": "Cmaj7", "midi_notes": [60, 64, 67, 71]},
    ]
    formatted = format_progression(progression)
    assert len(formatted) == 3
    assert formatted[0]["Compasso"] == 1
    assert formatted[0]["Acorde"] == "Dm7"
    assert "Notas MIDI" in formatted[0]


# ---------------------------------------------------------------------------
# TC-UI-003: build ingest payload from form data
# ---------------------------------------------------------------------------


def test_build_ingest_payload_from_form():
    """TC-UI-003: build_ingest_payload must coerce bpm to float."""
    from src.ui.helpers import build_ingest_payload

    form = {
        "title": "Jazz Morning",
        "artist": "Trio",
        "genre": "jazz",
        "bpm": 120,
        "mood": "relaxado",
    }
    payload = build_ingest_payload(form)
    assert payload["title"] == "Jazz Morning"
    assert payload["genre"] == "jazz"
    assert isinstance(payload["bpm"], float)
    assert payload["bpm"] == 120.0


# ---------------------------------------------------------------------------
# TC-UI-004: parse health response
# ---------------------------------------------------------------------------


def test_parse_health_response():
    """TC-UI-004: parse_health must map status/ollama strings to bool flags
    and human-readable labels."""
    from src.ui.helpers import parse_health

    response = {"status": "ok", "ollama": "reachable"}
    parsed = parse_health(response)
    assert parsed["api_ok"] is True
    assert parsed["ollama_ok"] is True
    assert parsed["api_label"] == "Online"
    assert parsed["ollama_label"] == "Conectado"


# ---------------------------------------------------------------------------
# TC-UI-005: score to percentage and colour
# ---------------------------------------------------------------------------


def test_score_to_percentage_and_color():
    """TC-UI-005: score_display must return percentage, label and colour
    (green >= 0.7, orange >= 0.5, red < 0.5)."""
    from src.ui.helpers import score_display

    result = score_display(0.873)
    assert result["percentage"] == pytest.approx(87.3, abs=0.1)
    assert result["label"] == "87%"
    assert result["color"] == "green"
    assert score_display(0.5)["color"] == "orange"
    assert score_display(0.3)["color"] == "red"
