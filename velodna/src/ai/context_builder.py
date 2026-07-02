"""
Context Builder — monta o contexto do atleta para prompts do AI Coach.

Formata dados de atividade e métricas de fitness em texto estruturado
para uso nos system prompts do Ollama.
"""
from __future__ import annotations


class ContextBuilder:
    """Constrói blocos de contexto textual a partir de dados do atleta."""

    def build_activity_context(self, activity) -> str:
        """Formata os dados de uma atividade em bloco de texto.

        Args:
            activity: objeto Activity com campos de resumo da atividade

        Returns:
            String formatada com métricas da atividade.
        """
        duration_min = round(activity.duration_s / 60)
        distance_km = round(activity.distance_m / 1000, 1)
        tss = getattr(activity, "tss", None)

        return (
            f"Atividade: {activity.sport_type}\n"
            f"Duração: {duration_min} min\n"
            f"Distância: {distance_km} km\n"
            f"Potência média: {activity.avg_power_w}W\n"
            f"TSS: {tss}"
        )

    def build_fitness_context(self, metrics: dict) -> str:
        """Formata as métricas de fitness (CTL/ATL/TSB) em bloco de texto.

        Args:
            metrics: dicionário com chaves "ctl", "atl", "tsb"

        Returns:
            String formatada com métricas de carga de treino.
        """
        return (
            f"CTL: {metrics.get('ctl', 0):.1f}\n"
            f"ATL: {metrics.get('atl', 0):.1f}\n"
            f"TSB: {metrics.get('tsb', 0):.1f}"
        )
