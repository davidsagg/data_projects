"""
Sleep Correlator — correlação de Pearson entre qualidade do sono e performance.

Requer mínimo de 7 pares de observações para retornar resultado válido.
"""
from __future__ import annotations

import math
from typing import Optional


class SleepCorrelator:
    """Calcula a correlação de Pearson entre métricas de sono e performance."""

    MIN = 7  # mínimo de pares para resultado estatisticamente válido

    def correlate(self, data: list[tuple]) -> Optional[float]:
        """Calcula o coeficiente de Pearson entre pares (sono, performance).

        Args:
            data: lista de tuplas (sleep_score, np_watts) ou métricas similares

        Returns:
            Coeficiente de Pearson [-1.0, 1.0], ou None se dados insuficientes.
        """
        if len(data) < self.MIN:
            return None

        x = [d[0] for d in data]
        y = [d[1] for d in data]
        n = len(x)
        mx, my = sum(x) / n, sum(y) / n

        num = sum((a - mx) * (b - my) for a, b in zip(x, y))
        den = math.sqrt(
            sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)
        )
        return round(num / den, 4) if den > 0 else 0.0
