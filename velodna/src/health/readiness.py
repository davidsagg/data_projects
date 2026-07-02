"""
Readiness Calculator — score de recuperação diário (0–100).

Composição: sono (40%), HRV (30%), body battery (20%), TSB (10%).
"""
from __future__ import annotations

from src.ingestion.garmin_health_client import HealthDaily


class ReadinessCalculator:
    """Calcula o score de prontidão do atleta para treino."""

    def calculate(self, h: HealthDaily, metrics: dict) -> float:
        """Calcula o score de recuperação composto (0–100).

        Args:
            h: dados de saúde diários do atleta
            metrics: dicionário com pelo menos {"tsb": float}

        Returns:
            Score de recuperação entre 0.0 e 100.0.
        """
        score = 50.0

        if h.sleep_score is not None:
            score += (h.sleep_score - 70) * 0.5

        if h.hrv_rmssd_ms is not None:
            score += (h.hrv_rmssd_ms - 40) * 0.4

        if h.body_battery_max is not None:
            score += (h.body_battery_max - 60) * 0.3

        score += metrics.get("tsb", 0) * 0.5

        return round(max(0.0, min(100.0, score)), 1)

    def get_recommendation(self, score: float) -> str:
        """Retorna recomendação de treino baseada no score de recuperação.

        Args:
            score: valor entre 0 e 100

        Returns:
            Texto com recomendação de intensidade de treino.
        """
        if score < 50:
            return "Descanso ativo ou completo"
        if score < 75:
            return "Treino moderado — sem máxima intensidade"
        return "Apto para treino intenso de alta carga"
