"""
Injury Risk Coach — avalia risco de lesão por overuse via Ollama.

Fatores analisados:
  - Ramp rate > 10% semana-a-semana
  - Volume > 120% da média de 4 semanas
  - TSB < -35
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InjuryRiskFactors:
    """Fatores de risco identificados na análise."""

    ramp_rate_pct: float | None = None
    volume_ratio_pct: float | None = None
    tsb: float | None = None
    risk_level: str = "low"
    triggered_factors: list[str] = field(default_factory=list)


class InjuryRiskCoach:
    """Analisa padrão de carga e gera avaliação de risco de lesão via Ollama."""

    def __init__(self, client) -> None:
        """Args:
            client: instância de OllamaClient.
        """
        self.client = client

    def assess_factors(
        self,
        tss_by_week: list[float],
        distance_by_week: list[float],
        tsb: float,
    ) -> InjuryRiskFactors:
        """Identifica fatores de risco a partir das métricas de carga.

        Args:
            tss_by_week: TSS das últimas semanas (mais recente por último, mín 2)
            distance_by_week: km das últimas semanas (mais recente por último, mín 5)
            tsb: Training Stress Balance atual

        Returns:
            InjuryRiskFactors com os gatilhos identificados.
        """
        factors = InjuryRiskFactors(tsb=tsb)

        # Ramp rate semana-a-semana
        if len(tss_by_week) >= 2 and tss_by_week[-2] > 0:
            ramp = (tss_by_week[-1] - tss_by_week[-2]) / tss_by_week[-2] * 100
            factors.ramp_rate_pct = round(ramp, 1)
            if ramp > 10:
                factors.triggered_factors.append(
                    f"Ramp rate de {ramp:.0f}% semana-a-semana (limite: 10%)"
                )

        # Volume vs média das últimas 4 semanas
        if len(distance_by_week) >= 5:
            avg_4w = sum(distance_by_week[-5:-1]) / 4
            if avg_4w > 0:
                ratio = distance_by_week[-1] / avg_4w * 100
                factors.volume_ratio_pct = round(ratio, 1)
                if ratio > 120:
                    factors.triggered_factors.append(
                        f"Volume {ratio:.0f}% da média de 4 semanas (limite: 120%)"
                    )

        # TSB crítico
        if tsb < -35:
            factors.triggered_factors.append(
                f"TSB em {tsb:.1f} — abaixo do limiar crítico de -35"
            )

        n = len(factors.triggered_factors)
        factors.risk_level = "high" if n >= 2 else ("medium" if n == 1 else "low")
        return factors

    def generate_assessment(self, factors: InjuryRiskFactors) -> str:
        """Gera explicação contextualizada do risco via Ollama.

        Args:
            factors: fatores de risco identificados

        Returns:
            Texto de avaliação gerado pelo modelo.
        """
        if not factors.triggered_factors:
            return (
                "Nenhum fator de risco de lesão identificado esta semana. "
                "Continue monitorando a carga progressivamente."
            )

        triggered_text = "\n".join(f"- {f}" for f in factors.triggered_factors)
        prompt = (
            "Você é um fisioterapeuta esportivo especializado em ciclismo. "
            "Analise os seguintes fatores de risco de lesão por overuse identificados "
            "no padrão de treino de um ciclista e forneça uma avaliação clara e prática.\n\n"
            f"Nível de risco: {factors.risk_level.upper()}\n"
            f"Fatores identificados:\n{triggered_text}\n\n"
            "Explique em 3-4 frases:\n"
            "1. O que esses fatores indicam sobre o risco de lesão\n"
            "2. Que tipo de lesão por overuse é mais provável nesse contexto\n"
            "3. O que o atleta deve fazer imediatamente\n\n"
            "Seja direto e específico. Responda em português."
        )
        return self.client.generate(prompt)
