import pytest
from pathlib import Path
from src.ingestion.fit_parser import FITParser, Activity, ActivityStream, FITParseError
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
