import pytest
from datetime import date
from unittest.mock import patch
from src.ingestion.garmin_health_client import GarminHealthClient, HealthDaily

MOCK_SLEEP = {"dailySleepDTO":{"sleepTimeSeconds":25200,
    "sleepScores":{"overall":{"value":78}},
    "deepSleepSeconds":5400,"remSleepSeconds":7200}}
MOCK_HRV = {"lastNight":{"rmssd":42.5,"status":"BALANCED"}}

@patch.object(GarminHealthClient, "_fetch_sleep")
@patch.object(GarminHealthClient, "_fetch_hrv")
def test_get_health_daily_returns_health_daily(mock_hrv, mock_sleep):
    mock_sleep.return_value = MOCK_SLEEP
    mock_hrv.return_value = MOCK_HRV
    client = GarminHealthClient.__new__(GarminHealthClient)
    result = client.get_health_daily(date(2024, 1, 15))
    assert isinstance(result, HealthDaily)
    assert result.sleep_score == 78
    assert result.hrv_rmssd_ms == 42.5

@patch.object(GarminHealthClient, "get_health_daily")
def test_get_health_range_returns_list(mock_daily):
    mock_daily.return_value = HealthDaily(date=date(2024, 1, 1))
    client = GarminHealthClient.__new__(GarminHealthClient)
    results = client.get_health_range(date(2024,1,1), date(2024,1,3))
    assert isinstance(results, list)
    assert len(results) == 3
    assert mock_daily.call_count == 3
