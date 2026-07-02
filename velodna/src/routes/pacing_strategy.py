"""
Pacing Strategy — distribui potência alvo por segmento de uma rota.

Ajusta o percentual do FTP com base no gradiente, tipo de segmento e TSB.
"""
from __future__ import annotations

from src.routes.gpx_analyzer import AnalyzedSegment


class PacingStrategy:
    """Calcula potência recomendada por segmento dado o FTP e estado de forma."""

    def __init__(self, ftp: float, tsb: float = 0.0) -> None:
        """Args:
            ftp: FTP do atleta em watts.
            tsb: Training Stress Balance — positivo = fresco, negativo = fadigado.
        """
        self.ftp = ftp
        self.tsb = tsb

    def calculate(
        self, segs: list[AnalyzedSegment], target: float = 0.88
    ) -> list[AnalyzedSegment]:
        """Atribui recommended_power_w a cada segmento.

        Lógica:
          - Flat: target * ftp * fitness_factor
          - Climb: reduz proporcionalmente ao gradiente (mínimo 75% FTP)
          - Descent: 70% do target (recuperação ativa)
          - TSB negativo penaliza até 15% a potência máxima disponível

        Args:
            segs: lista de AnalyzedSegment com segment_type preenchido
            target: fração do FTP alvo para trechos planos (padrão 0.88)

        Returns:
            A mesma lista com recommended_power_w preenchido in-place.
        """
        fitness_factor = max(0.85, 1.0 + self.tsb * 0.002)
        for s in segs:
            g = s.avg_gradient_pct
            if s.segment_type == "climb":
                pct = max(0.75, target - g * 0.012)
            elif s.segment_type == "descent":
                pct = target * 0.70
            else:
                pct = target
            s.recommended_power_w = round(self.ftp * pct * fitness_factor, 1)
        return segs
