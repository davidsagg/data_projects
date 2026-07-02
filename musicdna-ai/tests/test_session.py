"""TDD tests for src/simulator/session.py — Module M8 SessionConfig.

Test cases TC-M8-001 to TC-M8-003.
Production module not yet implemented — these tests are expected to fail
until SessionConfig is created.
"""

import pytest
from pydantic import ValidationError

from src.simulator.session import SessionConfig

# ---------------------------------------------------------------------------
# TC-M8-001: valid jazz session config
# ---------------------------------------------------------------------------


def test_session_config_valid_jazz():
    """TC-M8-001: valid config must set all fields and auto-generate a UUID."""
    config = SessionConfig(style="jazz", key="C", bpm=120, mood="relaxado", bars=8)
    assert config.style == "jazz"
    assert config.key == "C"
    assert config.bpm == 120
    assert config.mood == "relaxado"
    assert config.bars == 8
    assert len(config.session_id) == 36  # UUID gerado automaticamente


# ---------------------------------------------------------------------------
# TC-M8-002: invalid BPM raises ValidationError
# ---------------------------------------------------------------------------


def test_session_config_invalid_bpm_raises():
    """TC-M8-002: BPM out of valid range must raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SessionConfig(style="jazz", key="C", bpm=300, mood="animado")
    assert "bpm" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# TC-M8-003: invalid style raises ValidationError
# ---------------------------------------------------------------------------


def test_session_config_invalid_style_raises():
    """TC-M8-003: an unsupported style must raise ValidationError."""
    with pytest.raises(ValidationError):
        SessionConfig(style="sertanejo", key="C", bpm=100, mood="relaxado")
