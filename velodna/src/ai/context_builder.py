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
        duration_min = round((activity.elapsed_time_s or 0) / 60)
        distance_km = round((activity.distance_m or 0) / 1000, 1)

        lines = [
            f"Atividade: {activity.sport_type}",
            f"Duração: {duration_min} min",
            f"Distância: {distance_km} km",
            f"Potência média: {activity.avg_power_w}W",
            f"TSS: {getattr(activity, 'tss', None)}",
        ]

        np_w = getattr(activity, "normalized_power_w", None)
        if np_w is not None:
            lines.append(f"Potência normalizada: {round(np_w)}W")
        intensity = getattr(activity, "intensity_factor", None)
        if intensity is not None:
            lines.append(f"Intensity Factor: {intensity:.2f}")

        return "\n".join(lines)

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
