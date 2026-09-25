import pytest
from pathlib import Path
from ingestion.fit_parser import FITParser, Activity, ActivityStream, FITParseError
FIXTURES = Path("tests/fixtures")

def test_parse_activity_returns_activity_object():
    parser = FITParser()
    activity = parser.parse(FIXTURES / "sample.fit")
    assert isinstance(activity, Activity)
    assert activity.sport_type == "cycling"
    assert activity.duration_s > 0
    assert activity.distance_m > 0
    assert activity.start_time is not None

def test_parse_streams_returns_list_of_activity_streams():
    parser = FITParser()
    activity = parser.parse(FIXTURES / "sample.fit")
    assert isinstance(activity.streams, list)
    assert len(activity.streams) > 0
    assert isinstance(activity.streams[0], ActivityStream)
    assert activity.streams[0].timestamp is not None

def test_parse_invalid_file_raises_fit_parse_error():
    parser = FITParser()
    with pytest.raises(FITParseError):
        parser.parse(FIXTURES / "sample_invalid.fit")


def test_timestamps_are_labelled_utc():
    """O FIT grava em UTC, mas o `fitparse` devolve datetime naive.

    Sem rótulo, o DuckDB presume o fuso local ao gravar na coluna TIMESTAMPTZ e
    desloca o instante — em São Paulo, três horas à frente. O erro é silencioso:
    a data continua certa e só o horário fica errado.
    """
    from datetime import timezone

    activity = FITParser().parse(FIXTURES / "sample.fit")

    assert activity.start_time.tzinfo is not None, "start_time precisa ter fuso"
    assert activity.start_time.utcoffset() == timezone.utc.utcoffset(None)

    for stream in activity.streams[:5]:
        assert stream.timestamp.tzinfo is not None, "stream sem fuso"
        assert stream.timestamp.utcoffset() == timezone.utc.utcoffset(None)


def test_reads_enhanced_altitude_and_speed():
    """Garmin moderno grava `enhanced_altitude`/`enhanced_speed` e omite os clássicos.

    Ler só o nome clássico devolvia None em todo o acervo recente, e o erro era
    invisível: o resumo continuava mostrando a elevação certa, porque esse número
    vem da mensagem `session`, não dos records. Só apareceu quando a detecção de
    subidas devolveu zero subidas num pedal de 1.570 m.
    """
    from unittest.mock import MagicMock

    from ingestion.fit_parser import _first_value

    record = MagicMock()
    record.get_value.side_effect = lambda name: {
        "enhanced_altitude": 771.0,
        "enhanced_speed": 3.695,
    }.get(name)

    assert _first_value(record, "enhanced_altitude", "altitude") == 771.0
    assert _first_value(record, "enhanced_speed", "speed") == 3.695


def test_falls_back_to_classic_field_names():
    """Aparelhos antigos gravam só `altitude`/`speed` — o fallback os cobre."""
    from unittest.mock import MagicMock

    from ingestion.fit_parser import _first_value

    record = MagicMock()
    record.get_value.side_effect = lambda name: {"altitude": 640.0}.get(name)

    assert _first_value(record, "enhanced_altitude", "altitude") == 640.0
    assert _first_value(record, "enhanced_speed", "speed") is None
