import pytest
from unittest.mock import patch, MagicMock
from src.ingestion.strava_client import StravaClient

MOCK_ACTIVITIES = [
    {"id":1,"sport_type":"Ride","start_date":"2024-01-01T08:00:00Z","distance":50000.0,"elapsed_time":7200},
    {"id":2,"sport_type":"Ride","start_date":"2024-01-03T08:00:00Z","distance":30000.0,"elapsed_time":4500},
]
MOCK_STREAMS = {"time":{"data":[0,1,2,3]},"watts":{"data":[200,210,195,220]}}

@patch("src.ingestion.strava_client.requests.get")
def test_get_activities_returns_list(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_ACTIVITIES
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp
    client = StravaClient(access_token="test_token")
    activities = client.get_activities(limit=2)
    assert isinstance(activities, list)
    assert len(activities) == 2
    assert "id" in activities[0]
    assert "distance" in activities[0]

@patch("src.ingestion.strava_client.requests.get")
def test_get_activity_streams_returns_power(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_STREAMS
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp
    client = StravaClient(access_token="test_token")
    streams = client.get_activity_streams(activity_id=123)
    assert "time" in streams
    assert "watts" in streams
