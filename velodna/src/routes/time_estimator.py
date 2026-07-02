"""
Time Estimator — estima tempo de conclusão de uma rota por segmento.

Velocidade estimada a partir do FTP, CTL (fitness) e gradiente do segmento.
"""
from __future__ import annotations

from src.routes.gpx_analyzer import AnalyzedSegment


class TimeEstimator:
    """Estima o tempo total de uma rota dado o perfil de segmentos e o atleta."""

    def __init__(self, ftp: float, ctl: float = 50.0) -> None:
        """Args:
            ftp: FTP do atleta em watts.
            ctl: Chronic Training Load — proxy de fitness aeróbico (padrão 50).
        """
        self.ftp = ftp
        self.ctl = ctl

    def estimate(self, segs: list[AnalyzedSegment]) -> int:
        """Estima o tempo total em segundos para completar a lista de segmentos.

        Velocidade base proporcional ao FTP e CTL; penalizada por gradiente positivo.

        Args:
            segs: lista de AnalyzedSegment com length_m e avg_gradient_pct

        Returns:
            Tempo estimado em segundos (arredondado).
        """
        fitness_factor = max(0.85, min(1.15, self.ctl / 50.0))
        total = 0.0
        for s in segs:
            speed = max(
                1.5,
                self.ftp / 150 * fitness_factor / (1 + max(0, s.avg_gradient_pct) * 0.08),
            )
            total += s.length_m / speed
        return round(total)
