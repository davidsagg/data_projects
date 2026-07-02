"""
Weekly Plan Coach — gera sugestão de periodização semanal via Ollama.

Considera CTL/ATL/TSB atual e target_tss_week para distribuir carga
nos dias disponíveis, priorizando recuperação quando TSB < -15.
"""
from __future__ import annotations

from src.ai.context_builder import ContextBuilder


class WeeklyPlanCoach:
    """Coach de IA que sugere distribuição de treinos para a próxima semana."""

    def __init__(self, client) -> None:
        """Args:
            client: instância de OllamaClient.
        """
        self.client = client

    def suggest_week(
        self,
        metrics: dict,
        target_tss_week: float | None = None,
        available_days: list[str] | None = None,
    ) -> str:
        """Gera sugestão de treino para os próximos 7 dias.

        Args:
            metrics: dicionário com "ctl", "atl" e "tsb" atuais
            target_tss_week: TSS total alvo para a semana (opcional)
            available_days: lista de dias disponíveis, ex: ["seg","qua","sex","sab"]

        Returns:
            Texto com plano semanal gerado pelo modelo.
        """
        ctx = ContextBuilder()
        tsb = metrics.get("tsb", 0)

        recovery_note = (
            "IMPORTANTE: TSB muito negativo — priorize recuperação ativa ou descanso."
            if tsb < -15
            else ""
        )
        tss_note = f"TSS alvo para a semana: {target_tss_week:.0f}." if target_tss_week else ""
        days_note = (
            f"Dias disponíveis: {', '.join(available_days)}."
            if available_days
            else "Considere os 7 dias da semana."
        )

        prompt = (
            "Você é um coach de ciclismo experiente. Crie um plano semanal de treino.\n\n"
            f"{ctx.build_fitness_context(metrics)}\n"
            f"{tss_note}\n"
            f"{days_note}\n"
            f"{recovery_note}\n\n"
            "Para cada dia disponível liste: tipo de treino (ex: Z2 base, intervalos VO2max, "
            "recuperação ativa, descanso), duração estimada em minutos e TSS alvo.\n"
            "Responda em português, de forma objetiva e prática."
        )
        return self.client.generate(prompt)
