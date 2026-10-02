"""
Testes do servidor MCP.

O que importa verificar aqui é o contrato com quem consome: que as ferramentas
existem com os nomes prometidos, que a indisponibilidade da API vira uma
mensagem acionável em vez de um traceback de rede, e — o mais importante — que
**nenhuma ferramenta escreve**. O servidor foi declarado somente-leitura, e essa
é a garantia que um teste precisa segurar: é fácil alguém acrescentar uma
ferramenta de escrita sem perceber que quebrou a promessa.
"""
from __future__ import annotations

import httpx
import pytest

from mcp_server import server as mcp


@pytest.fixture
def api(monkeypatch):
    """Substitui a camada HTTP por respostas controladas."""
    calls: list[tuple[str, dict]] = []
    responses: dict[str, object] = {}

    async def fake_get(path, params=None):
        calls.append((path, params or {}))
        return responses.get(path)

    monkeypatch.setattr(mcp, "_get", fake_get)
    return {"calls": calls, "responses": responses}


# ---------------------------------------------------------------------------
# Contrato
# ---------------------------------------------------------------------------


EXPECTED_TOOLS = {
    "get_athlete_profile",
    "get_week",
    "get_week_series",
    "list_activities",
    "get_activity_analysis",
    "get_wprime_balance",
    "get_training_load",
    "get_power_curve",
    "get_ftp_history",
    "get_efficiency",
    "get_health_metrics",
    "get_subjective_feedback",
    "get_health_insights",
    "get_segments",
    "get_panorama",
    "get_goals",
    "get_milestones",
}


async def _tool_names() -> set[str]:
    tools = await mcp.server.list_tools()
    return {t.name for t in tools}


async def test_exposes_the_expected_tools():
    assert await _tool_names() == EXPECTED_TOOLS


async def test_no_tool_writes():
    """A promessa de somente-leitura precisa de um teste que a segure.

    Verbos de escrita no nome são o sinal mais barato e mais confiável: uma
    ferramenta chamada `create_workout` ou `set_ftp` não passa despercebida.
    """
    forbidden = ("create", "update", "delete", "set_", "put_", "post_", "save",
                 "remove", "push", "write", "add_")
    offenders = [
        name for name in await _tool_names()
        if any(name.startswith(verb) or f"_{verb}" in name for verb in forbidden)
    ]
    assert offenders == [], f"ferramentas de escrita num servidor só-leitura: {offenders}"


async def test_every_tool_has_a_description():
    """Sem descrição, o modelo não sabe quando chamar a ferramenta."""
    tools = await mcp.server.list_tools()
    missing = [t.name for t in tools if not (t.description or "").strip()]
    assert missing == []


# ---------------------------------------------------------------------------
# Comportamento
# ---------------------------------------------------------------------------


async def test_api_down_gives_actionable_message(monkeypatch):
    """Rede caída não pode chegar ao usuário como traceback de httpx."""

    class FailingClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(mcp.httpx, "AsyncClient", FailingClient)

    with pytest.raises(mcp.VeloDNAUnavailable, match="make api"):
        await mcp._get("/week")


async def test_list_activities_defaults_to_last_30_days(api):
    api["responses"]["/activities/"] = []

    await mcp.list_activities()

    path, params = api["calls"][0]
    assert path == "/activities/"
    assert params["start"] and params["end"]


async def test_list_activities_filters_by_sport(api):
    api["responses"]["/activities/"] = [
        {"id": "1", "sport_type": "cycling"},
        {"id": "2", "sport_type": "running"},
    ]

    result = await mcp.list_activities(start="2026-01-01", end="2026-12-31", sport="cycling")

    assert [a["id"] for a in result] == ["1"]


async def test_power_curve_defaults_to_cycling(api):
    """Potência de corrida infla o eFTP em até 25% — o default protege disso."""
    api["responses"]["/power-curve"] = []

    await mcp.get_power_curve()

    _, params = api["calls"][0]
    assert params["sport"] == "cycling"


async def test_training_load_trims_to_requested_days(api):
    api["responses"]["/pmc"] = [{"date": f"2026-01-{d:02d}"} for d in range(1, 29)]

    result = await mcp.get_training_load(days=7)

    assert len(result) == 7
    assert result[-1]["date"] == "2026-01-28"


async def test_activity_analysis_bundles_the_four_views(api):
    for path, payload in [
        ("/activities/abc/zone-distribution", {"z": 1}),
        ("/activities/abc/intervals", {"interval_count": 3}),
        ("/activities/abc/durability", {"verdict": "boa"}),
        ("/activities/abc/feedback", {"rpe": 7}),
    ]:
        api["responses"][path] = payload

    result = await mcp.get_activity_analysis("abc")

    assert set(result) == {"zones", "intervals", "durability", "subjective_feedback"}
    assert result["subjective_feedback"]["rpe"] == 7


async def test_segments_switches_between_list_and_efforts(api):
    api["responses"]["/segments"] = [{"id": "s1"}]
    api["responses"]["/segments/s1/efforts"] = {"efforts": []}

    assert await mcp.get_segments() == [{"id": "s1"}]
    assert await mcp.get_segments("s1") == {"efforts": []}


async def test_athlete_profile_gathers_context(api):
    api["responses"]["/zones/definitions"] = {"ftp_w": 217.0}
    api["responses"]["/pmc"] = [{"date": "2026-09-01"}, {"date": "2026-09-13", "ctl": 49.4}]
    api["responses"]["/readiness/today"] = {"score": 45}
    api["responses"]["/critical-power"] = {"cp_w": 218.1}
    api["responses"]["/ftp-history"] = [{"ftp_w": 200.0}] * 10

    result = await mcp.get_athlete_profile()

    assert result["current_form"]["ctl"] == 49.4
    assert result["catalog_span"] == {"first": "2026-09-01", "last": "2026-09-13"}
    assert len(result["ftp_history_recent"]) == 6, "só o histórico recente, não os 10"
