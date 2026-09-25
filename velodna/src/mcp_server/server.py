"""
Servidor MCP do VeloDNA — conversa com o próprio acervo.

A ideia vem do post do Marco Altini sobre o conector da augo: o valor não está
num assistente embutido, e sim em expor a camada de dados para que o atleta (ou
treinador) construa as próprias análises com o modelo de sua escolha. O VeloDNA
já é essa camada — faltava a ponte.

**Fala HTTP com a API, não com o DuckDB.** Não é preferência: o DuckDB aceita um
escritor só, e com a API de pé nem uma conexão `read_only=True` consegue abrir o
arquivo. Um servidor MCP que tocasse o banco direto estaria em conflito com a API
sempre que os dois rodassem juntos — que é exatamente o caso de uso. Ir por HTTP
também reaproveita toda a lógica dos endpoints em vez de duplicá-la.

**Somente leitura, por decisão.** Nenhuma ferramenta aqui altera nada. Gravar
continua passando pela UI e pelos scripts, onde há confirmação e histórico.

Uso (stdio, para o Claude Desktop ou o Claude Code):

    .venv/bin/python -m mcp_server.server

A API precisa estar no ar (`make api`).
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

API_BASE = os.getenv("VELODNA_API_URL", "http://localhost:8006")
TIMEOUT_S = float(os.getenv("VELODNA_MCP_TIMEOUT", "120"))

server = MCPServer(
    name="velodna",
    instructions=(
        "Acervo de ciclismo do atleta: atividades com potência e frequência "
        "cardíaca, métricas derivadas (NP, IF, TSS, CTL/ATL/TSB), histórico de "
        "FTP, curva de potência, potência crítica, zonas, saúde diária do Garmin "
        "(HRV, sono, FC de repouso) e feedback subjetivo do atleta.\n\n"
        "Convenções que importam ao interpretar os dados:\n"
        "- A semana vai de segunda a domingo; é a unidade de periodização.\n"
        "- Potência de corrida NÃO é comparável à de ciclismo e fica fora das "
        "métricas de bike. Filtre por sport='cycling' ao falar de FTP ou curva.\n"
        "- TSS pode vir de potência ou de FC (campo tss_source); os dois não têm "
        "a mesma precisão.\n"
        "- As zonas de cada atividade são as do FTP vigente na data dela.\n"
        "- O acervo começa em 2023 por decisão do atleta.\n\n"
        "Somente leitura: nenhuma ferramenta altera dados."
    ),
)


class VeloDNAUnavailable(RuntimeError):
    """A API local não respondeu."""


async def _get(path: str, params: dict | None = None) -> Any:
    """Faz um GET na API local, traduzindo a indisponibilidade em algo legível."""
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=TIMEOUT_S) as client:
            response = await client.get(path, params=clean)
    except httpx.RequestError as error:
        raise VeloDNAUnavailable(
            f"A API do VeloDNA não respondeu em {API_BASE}. "
            "Suba-a com 'make api' no diretório do projeto."
        ) from error

    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise RuntimeError(
            f"GET {path} falhou (HTTP {response.status_code}): {response.text[:200]}"
        )
    return response.json()


# ---------------------------------------------------------------------------
# Contexto do atleta
# ---------------------------------------------------------------------------


@server.tool(
    description=(
        "Perfil e estado atual do atleta: FTP vigente, zonas, potência crítica, "
        "forma (CTL/ATL/TSB) e prontidão de hoje. Chame isto primeiro quando "
        "precisar de contexto antes de analisar qualquer coisa."
    )
)
async def get_athlete_profile() -> dict:
    zones = await _get("/zones/definitions")
    pmc = await _get("/pmc")
    readiness = await _get("/readiness/today")
    cp = await _get("/critical-power", {"days": 400, "sport": "cycling"})
    ftp_history = await _get("/ftp-history")

    latest_load = pmc[-1] if pmc else None
    return {
        "zones": zones,
        "critical_power": cp,
        "ftp_history_recent": (ftp_history or [])[-6:],
        "current_form": latest_load,
        "readiness_today": readiness,
        "catalog_span": {
            "first": pmc[0]["date"] if pmc else None,
            "last": latest_load["date"] if latest_load else None,
        },
    }


# ---------------------------------------------------------------------------
# Semana
# ---------------------------------------------------------------------------


@server.tool(
    description=(
        "Resumo de uma semana (segunda a domingo): volume, carga, aderência ao "
        "plano, distribuição de intensidade e — no campo 'days' — treino, saúde "
        "e feedback subjetivo dia a dia no mesmo eixo. É a visão mais rica para "
        "entender como a semana foi e como o corpo respondeu."
    )
)
async def get_week(reference: str | None = None, include_zones: bool = True) -> dict:
    """Args:
        reference: qualquer dia da semana desejada (AAAA-MM-DD); padrão é hoje.
        include_zones: calcular tempo em zona (mais lento, mas é o que dá a
            distribuição de intensidade).
    """
    return await _get("/week", {"reference": reference, "zones": include_zones})


@server.tool(
    description=(
        "Série das últimas N semanas, da mais antiga para a mais recente. Use "
        "para responder se uma semana é normal para este atleta, ou para ver "
        "a progressão de carga ao longo de um bloco."
    )
)
async def get_week_series(weeks: int = 12, reference: str | None = None) -> list:
    return await _get("/weeks", {"weeks": weeks, "reference": reference, "zones": False})


# ---------------------------------------------------------------------------
# Atividades
# ---------------------------------------------------------------------------


@server.tool(
    description=(
        "Lista atividades num período, com as métricas de resumo de cada uma "
        "(TSS, NP, IF, duração, distância, elevação). Sem período, devolve os "
        "últimos 30 dias."
    )
)
async def list_activities(
    start: str | None = None,
    end: str | None = None,
    sport: str | None = None,
) -> list:
    if not start and not end:
        end = date.today().isoformat()
        start = (date.today() - timedelta(days=30)).isoformat()
    activities = await _get("/activities/", {"start": start, "end": end}) or []
    if sport:
        activities = [a for a in activities if a.get("sport_type") == sport]
    return activities


@server.tool(
    description=(
        "Análise completa de uma atividade: resumo, distribuição de zonas, "
        "blocos de esforço detectados, durabilidade (queda de potência e de "
        "eficiência depois do trabalho acumulado) e o feedback subjetivo que o "
        "atleta registrou. Use para analisar um treino específico a fundo."
    )
)
async def get_activity_analysis(activity_id: str) -> dict:
    summary = await _get(f"/activities/{activity_id}/zone-distribution")
    intervals = await _get(f"/activities/{activity_id}/intervals")
    durability = await _get(f"/activities/{activity_id}/durability")
    feedback = await _get(f"/activities/{activity_id}/feedback")
    return {
        "zones": summary,
        "intervals": intervals,
        "durability": durability,
        "subjective_feedback": feedback,
    }


@server.tool(
    description=(
        "Balanço de W' (reserva anaeróbica) ao longo de uma atividade, pelo "
        "modelo de Skiba. Mostra quanto do tanque sobrou em cada esforço e "
        "quantas vezes o atleta desceu abaixo de metade da reserva."
    )
)
async def get_wprime_balance(activity_id: str) -> dict:
    return await _get(f"/activities/{activity_id}/wbal")


# ---------------------------------------------------------------------------
# Forma e capacidade
# ---------------------------------------------------------------------------


@server.tool(
    description=(
        "Série de carga de treino: CTL (forma), ATL (fadiga) e TSB (frescor) "
        "por dia. Use para analisar periodização, rampa de carga e picos de forma."
    )
)
async def get_training_load(days: int = 180) -> list:
    pmc = await _get("/pmc") or []
    return pmc[-days:]


@server.tool(
    description=(
        "Curva de potência (melhor esforço médio por duração) num período. "
        "Filtre sempre por sport='cycling' ao falar de capacidade na bike — a "
        "potência de corrida usa outra escala e infla a curva."
    )
)
async def get_power_curve(
    start: str | None = None,
    end: str | None = None,
    sport: str = "cycling",
) -> list:
    return await _get("/power-curve", {"start": start, "end": end, "sport": sport})


@server.tool(
    description=(
        "Evolução do FTP ao longo do tempo, com a origem de cada ponto "
        "(teste registrado, ajuste manual ou estimativa a partir da curva)."
    )
)
async def get_ftp_history() -> list:
    return await _get("/ftp-history")


@server.tool(
    description=(
        "Efficiency Factor (potência normalizada por batimento) e desacoplamento "
        "cardíaco por atividade. É a leitura de adaptação aeróbica de longo "
        "prazo: mesma potência custando menos batimentos significa ganho de base."
    )
)
async def get_efficiency(
    start: str | None = None,
    end: str | None = None,
    sport: str = "cycling",
) -> list:
    return await _get("/efficiency", {"start": start, "end": end, "sport": sport})


# ---------------------------------------------------------------------------
# Saúde e percepção
# ---------------------------------------------------------------------------


@server.tool(
    description=(
        "Métricas diárias de saúde do Garmin: HRV, sono, FC de repouso, body "
        "battery e nível de estresse. Cruze com a carga de treino para explicar "
        "treinos fracos e antecipar sobrecarga."
    )
)
async def get_health_metrics(days: int = 60) -> list:
    return await _get("/health-daily", {"days": days})


@server.tool(
    description=(
        "Feedback subjetivo do atleta no período: esforço percebido (RPE, escala "
        "de Borg 1–10), sensação do corpo (1–5) e notas livres. É o dado que "
        "explica os outliers que os sensores não explicam — um treino fraco com "
        "HRV normal costuma ter a causa escrita aqui."
    )
)
async def get_subjective_feedback(
    start: str | None = None, end: str | None = None
) -> list:
    return await _get("/feedback", {"start": start, "end": end})


@server.tool(
    description=(
        "Alertas de overreaching em aberto, e a correlação entre recuperação e "
        "performance com tamanho de amostra e p-valor."
    )
)
async def get_health_insights() -> dict:
    return {
        "alerts": await _get("/health/alerts"),
        "sleep_performance_correlation": await _get("/health/sleep-correlation"),
    }


# ---------------------------------------------------------------------------
# Segmentos
# ---------------------------------------------------------------------------


@server.tool(
    description=(
        "Segmentos pessoais do atleta com o resumo das passagens. Passe um "
        "segment_id para receber o histórico completo de passagens, ordenado "
        "por tempo."
    )
)
async def get_segments(segment_id: str | None = None) -> Any:
    if segment_id:
        return await _get(f"/segments/{segment_id}/efforts")
    return await _get("/segments")


def main() -> None:
    """Sobe o servidor em stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
