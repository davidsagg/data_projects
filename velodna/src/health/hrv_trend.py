"""
HRV Trend Analyzer — análise de tendência de HRV com média móvel de 7 dias.

Detecta padrões de melhora, estabilidade ou declínio no HRV do atleta.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrendResult:
    """Resultado da análise de tendência de HRV."""

    trend: str          # "declining", "stable", "improving" ou "insufficient_data"
    alert: bool         # True quando HRV declina > 15% abaixo da linha de base
    ma7_values: list = field(default_factory=list)


class HRVTrendAnalyzer:
    """Analisa a tendência de HRV usando média móvel de 7 dias."""

    def analyze(self, series: dict) -> TrendResult:
        """Analisa a série temporal de HRV e classifica a tendência.

        Args:
            series: dicionário {date: hrv_rmssd_ms} ordenável por data

        Returns:
            TrendResult com trend, alert e série de médias móveis de 7 dias.
        """
        vals = [series[d] for d in sorted(series)]

        if len(vals) < 7:
            return TrendResult("insufficient_data", False)

        # Média móvel de 7 dias (acumulativa no início da série)
        ma7 = [
            sum(vals[max(0, i - 6) : i + 1]) / min(7, i + 1)
            for i in range(len(vals))
        ]

        base = ma7[0]   # primeira MA7 como linha de base da série
        recent = ma7[-1]

        if recent < base * 0.85:
            return TrendResult("declining", True, ma7)
        if recent > base * 1.15:
            return TrendResult("improving", False, ma7)
        return TrendResult("stable", False, ma7)
