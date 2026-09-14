"""
Chat livre com o coach (US-14).

A diferença entre isto e um chatbot genérico é o contexto: cada pergunta vai
acompanhada do estado real do atleta — carga, forma, FTP vigente, saúde recente
e últimos treinos. Sem isso, o modelo responde generalidades de revista.

O histórico da conversa é persistido em `ai_conversations` e reenviado a cada
turno, porque o endpoint `/api/generate` do Ollama não guarda estado.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

# Quantos turnos anteriores acompanham a pergunta. Longo o bastante para manter
# o fio da conversa, curto o bastante para não estourar a janela do modelo nem
# empurrar o contexto do atleta para fora dela.
HISTORY_TURNS = 8

SYSTEM_PROMPT = """Você é um treinador de ciclismo experiente conversando com \
seu atleta. Responda em português do Brasil, de forma direta e prática.

Regras:
- Use os dados do atleta fornecidos abaixo. Se um dado necessário não estiver \
no contexto, diga que não tem essa informação em vez de supor.
- Seja específico: cite watts, TSS, zonas e prazos quando fizer sentido.
- Não dê diagnóstico médico. Sinais de doença ou dor persistente pedem médico.
- Respostas curtas, no máximo três parágrafos, salvo se pedirem detalhamento."""


@dataclass(frozen=True)
class ChatTurn:
    """Um turno da conversa."""

    role: str
    content: str


class ChatCoach:
    """Conversa com o atleta usando o estado dele como contexto."""

    def __init__(self, client) -> None:
        """Args:
            client: cliente com método `generate(prompt) -> str`.
        """
        self._client = client

    def build_prompt(
        self,
        question: str,
        athlete_context: str,
        history: list[ChatTurn] | None = None,
    ) -> str:
        """Monta o prompt completo de um turno.

        Args:
            question: pergunta do atleta.
            athlete_context: bloco de texto com o estado atual do atleta.
            history: turnos anteriores, do mais antigo para o mais recente.

        Returns:
            Prompt pronto para o modelo.
        """
        parts = [SYSTEM_PROMPT, "", "## Dados do atleta", athlete_context]

        recent = (history or [])[-HISTORY_TURNS:]
        if recent:
            parts += ["", "## Conversa até aqui"]
            parts += [
                f"{'Atleta' if turn.role == 'user' else 'Treinador'}: {turn.content}"
                for turn in recent
            ]

        parts += ["", "## Pergunta", f"Atleta: {question}", "", "Treinador:"]
        return "\n".join(parts)

    def answer(
        self,
        question: str,
        athlete_context: str,
        history: list[ChatTurn] | None = None,
    ) -> str:
        """Responde a uma pergunta do atleta.

        Args:
            question: pergunta do atleta.
            athlete_context: bloco de texto com o estado atual.
            history: turnos anteriores.

        Returns:
            Resposta do treinador.

        Raises:
            OllamaUnavailableError: se o servidor de inferência está fora.
        """
        prompt = self.build_prompt(question, athlete_context, history)
        return self._client.generate(prompt).strip()


def new_session_id() -> str:
    """Gera o identificador de uma nova conversa."""
    return str(uuid.uuid4())


def build_athlete_context(db, athlete_id: str) -> str:
    """Monta o bloco de contexto com o estado atual do atleta.

    Reúne perfil, carga, FTP vigente, saúde recente e últimos treinos num texto
    compacto — o modelo lê melhor um resumo denso que tabelas extensas.

    Args:
        db: conexão DuckDB.
        athlete_id: UUID do atleta.

    Returns:
        Texto com os dados disponíveis, em linhas curtas.
    """
    from api.query import row as query_row, rows as query_rows

    lines: list[str] = []

    profile = query_row(
        db,
        "SELECT name, ftp_w, max_hr_bpm, resting_hr_bpm, threshold_hr_bpm, "
        "weight_kg FROM athletes WHERE id = ?",
        [athlete_id],
    )
    if profile:
        lines.append(
            f"Perfil: FTP {_fmt(profile['ftp_w'])} W, peso {_fmt(profile['weight_kg'])} kg, "
            f"FC máx {_fmt(profile['max_hr_bpm'])}, FC repouso {_fmt(profile['resting_hr_bpm'])}, "
            f"FC limiar {_fmt(profile['threshold_hr_bpm'])}"
        )
        if profile["ftp_w"] and profile["weight_kg"]:
            ratio = profile["ftp_w"] / profile["weight_kg"]
            lines.append(f"Relação peso-potência: {ratio:.2f} W/kg")

    load = query_row(
        db,
        "SELECT date, ctl, atl, tsb FROM training_load WHERE athlete_id = ? "
        "ORDER BY date DESC LIMIT 1",
        [athlete_id],
    )
    if load:
        lines.append(
            f"Carga em {load['date']}: CTL {_fmt(load['ctl'], 1)} (fitness), "
            f"ATL {_fmt(load['atl'], 1)} (fadiga), TSB {_fmt(load['tsb'], 1)} (forma)"
        )

    weekly = query_rows(
        db,
        """
        SELECT DATE_TRUNC('week', date) AS week, SUM(daily_tss) AS tss
        FROM training_load
        WHERE athlete_id = ? AND date >= CURRENT_DATE - 28
        GROUP BY week ORDER BY week
        """,
        [athlete_id],
    )
    if weekly:
        totals = " · ".join(f"{_fmt(w['tss'], 0)}" for w in weekly)
        lines.append(f"TSS das últimas semanas (mais antiga primeiro): {totals}")

    health = query_row(
        db,
        """
        SELECT date, hrv_rmssd_ms, hrv_status, resting_hr_bpm, sleep_hours,
               body_battery
        FROM health_metrics WHERE athlete_id = ? ORDER BY date DESC LIMIT 1
        """,
        [athlete_id],
    )
    if health:
        lines.append(
            f"Saúde em {health['date']}: HRV {_fmt(health['hrv_rmssd_ms'])} ms "
            f"({health['hrv_status'] or 'sem status'}), FC repouso "
            f"{_fmt(health['resting_hr_bpm'])}, sono {_fmt(health['sleep_hours'], 1)} h, "
            f"body battery {_fmt(health['body_battery'])}"
        )

    recent = query_rows(
        db,
        """
        SELECT CAST(started_at AS DATE) AS date, sport_type, distance_m,
               elapsed_time_s, normalized_power_w, intensity_factor, tss
        FROM activities WHERE athlete_id = ? ORDER BY started_at DESC LIMIT 5
        """,
        [athlete_id],
    )
    if recent:
        lines.append("Últimos treinos:")
        for a in recent:
            lines.append(
                f"  - {a['date']}: {a['sport_type']}, "
                f"{_fmt((a['distance_m'] or 0) / 1000, 1)} km, "
                f"{round((a['elapsed_time_s'] or 0) / 60)} min, "
                f"NP {_fmt(a['normalized_power_w'])} W, "
                f"IF {_fmt(a['intensity_factor'], 2)}, TSS {_fmt(a['tss'], 0)}"
            )

    return "\n".join(lines) if lines else "Nenhum dado disponível."


def _fmt(value, digits: int = 0) -> str:
    """Formata um número para o contexto, marcando ausência explicitamente."""
    if value is None:
        return "não informado"
    return f"{float(value):.{digits}f}"
