"""
Post Activity Coach — gera insight pós-atividade via Ollama.

Analisa dados de atividade + métricas de fitness e retorna CoachResponse
com resumo, destaques, alertas e recomendações em português.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.ai.context_builder import ContextBuilder


@dataclass
class CoachResponse:
    """Resposta estruturada do AI Coach após análise de uma atividade."""

    summary: str
    highlights: Optional[str] = None
    alerts: Optional[str] = None
    recommendations: Optional[str] = None


class PostActivityCoach:
    """Coach de IA que analisa atividades e gera insights pós-treino."""

    SYSTEM = (
        "Você é um coach de ciclismo experiente. "
        "Analise a atividade e forneça insights objetivos em português. "
        "Máximo 250 palavras. Tom direto, sem elogios vagos."
    )

    def __init__(self, client) -> None:
        """Args:
            client: instância de OllamaClient.
        """
        self.client = client

    def analyze(self, activity, metrics: dict) -> CoachResponse:
        """Analisa a atividade e retorna um CoachResponse com insights.

        Args:
            activity: objeto Activity com dados do treino
            metrics: dicionário com CTL, ATL e TSB atuais

        Returns:
            CoachResponse com summary preenchido pelo modelo.
        """
        ctx = ContextBuilder()
        prompt = (
            f"{self.SYSTEM}\n\n"
            f"{ctx.build_activity_context(activity)}\n\n"
            f"Fitness:\n{ctx.build_fitness_context(metrics)}\n\n"
            "Resuma: destaques, alertas, recomendações."
        )
        return CoachResponse(summary=self.client.generate(prompt))
