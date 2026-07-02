import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from src.ai.ollama_client import OllamaClient, OllamaUnavailableError
from src.ai.context_builder import ContextBuilder
from src.ai.post_activity_coach import PostActivityCoach, CoachResponse
from src.ai.weekly_plan_coach import WeeklyPlanCoach
from src.ingestion.fit_parser import Activity

MOCK_RESP = {"model": "llama3", "response": "Ótimo treino! Potência consistente.", "done": True}


def act():
    return Activity(garmin_id="r1", sport_type="cycling",
                    start_time=datetime(2024, 1, 15, 8, tzinfo=timezone.utc),
                    duration_s=3600, distance_m=40000, elevation_m=400, avg_power_w=250.0)


def _mock_post(rv=MOCK_RESP):
    m = MagicMock()
    m.json.return_value = rv
    m.status_code = 200
    return m


@patch("src.ai.ollama_client.requests.post")
def test_client_returns_text(mp):
    mp.return_value = _mock_post()
    r = OllamaClient().generate("test")
    assert isinstance(r, str) and len(r) > 0


@patch("src.ai.ollama_client.requests.post", side_effect=ConnectionError)
def test_client_raises_offline(mp):
    with pytest.raises(OllamaUnavailableError):
        OllamaClient().generate("t")


def test_context_activity():
    ctx = ContextBuilder().build_activity_context(act())
    assert "250" in ctx and "60" in ctx and "85" in ctx or "TSS" in ctx


def test_context_fitness():
    ctx = ContextBuilder().build_fitness_context({"ctl": 55, "atl": 62, "tsb": -7})
    assert "55" in ctx and "62" in ctx and "-7" in ctx


@patch("src.ai.ollama_client.requests.post")
def test_coach_calls_ollama(mp):
    mp.return_value = _mock_post()
    PostActivityCoach(OllamaClient()).analyze(act(), {"ctl": 55, "atl": 60, "tsb": -5})
    assert mp.called
    body = mp.call_args[1].get("json", {})
    assert "prompt" in body


@patch("src.ai.ollama_client.requests.post")
def test_coach_returns_response(mp):
    mp.return_value = _mock_post()
    r = PostActivityCoach(OllamaClient()).analyze(act(), {"ctl": 50, "atl": 55, "tsb": -5})
    assert isinstance(r, CoachResponse) and r.summary is not None


@patch("src.ai.ollama_client.requests.post")
def test_weekly_mentions_recovery(mp):
    mp.return_value = _mock_post()
    WeeklyPlanCoach(OllamaClient()).suggest_week({"ctl": 55, "atl": 75, "tsb": -20})
    body = mp.call_args[1].get("json", {})
    p = body.get("prompt", "").lower()
    assert "recuper" in p or "tsb" in p


@patch("src.ai.ollama_client.requests.post")
def test_weekly_returns_result(mp):
    mp.return_value = _mock_post({"model": "llama3", "done": True,
                                  "response": "Segunda:Z2\nTerca:descanso\nQuarta:intervalos\nQuinta:Z2\nSexta:descanso\nSabado:longo\nDomingo:descanso"})
    r = WeeklyPlanCoach(OllamaClient()).suggest_week({"ctl": 55, "atl": 58, "tsb": -3})
    assert r is not None and len(str(r)) > 0
