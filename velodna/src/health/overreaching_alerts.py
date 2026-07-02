"""
Overreaching Alerts — detecta sinais de sobrecarga de treino.

Triggers:
  - TSB < -30 (danger) ou TSB < -20 (warning)
  - Ramp rate > 8 TSS/semana (warning) ou > 12 (danger)
  - HRV suprimido (> 15% abaixo da média de 14 dias) + ATL alto (> 80)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal


Severity = Literal["warning", "danger"]


@dataclass
class OverreachingAlert:
    """Representa um alerta de overreaching ativo."""

    type: str
    severity: Severity
    message: str
    metric_value: float
    threshold: float


class OverreachingAnalyzer:
    """Analisa métricas de carga e saúde para detectar risco de overreaching."""

    def check_tsb(self, tsb: float) -> OverreachingAlert | None:
        """Verifica TSB abaixo do limiar de recuperação.

        Args:
            tsb: Training Stress Balance atual

        Returns:
            Alerta se TSB indicar sobrecarga, caso contrário None.
        """
        if tsb < -30:
            return OverreachingAlert(
                type="tsb_critical",
                severity="danger",
                message=f"TSB em {tsb:.1f} — carga acumulada muito alta. Insira dias de recuperação imediatamente.",
                metric_value=tsb,
                threshold=-30,
            )
        if tsb < -20:
            return OverreachingAlert(
                type="tsb_high",
                severity="warning",
                message=f"TSB em {tsb:.1f} — fadiga elevada. Reduza intensidade nos próximos dias.",
                metric_value=tsb,
                threshold=-20,
            )
        return None

    def check_ramp_rate(self, tss_by_week: list[float]) -> OverreachingAlert | None:
        """Verifica se o aumento semanal de TSS excede o limiar seguro.

        Args:
            tss_by_week: lista com TSS das últimas semanas (mais recente por último)

        Returns:
            Alerta se o ramp rate for excessivo, caso contrário None.
        """
        if len(tss_by_week) < 2:
            return None
        delta = tss_by_week[-1] - tss_by_week[-2]
        if delta > 12:
            return OverreachingAlert(
                type="ramp_rate_critical",
                severity="danger",
                message=f"Aumento de {delta:.0f} TSS em relação à semana anterior — risco alto de overreaching.",
                metric_value=delta,
                threshold=12,
            )
        if delta > 8:
            return OverreachingAlert(
                type="ramp_rate_high",
                severity="warning",
                message=f"Aumento de {delta:.0f} TSS em relação à semana anterior — aumento acima do ideal (máx 8).",
                metric_value=delta,
                threshold=8,
            )
        return None

    def check_hrv_suppression(
        self,
        hrv_recent: float | None,
        hrv_baseline: float | None,
        atl: float,
    ) -> OverreachingAlert | None:
        """Verifica HRV suprimido combinado com fadiga alta.

        Args:
            hrv_recent: RMSSD mais recente
            hrv_baseline: média dos últimos 14 dias de RMSSD
            atl: Acute Training Load atual

        Returns:
            Alerta se HRV suprimido + ATL elevado, caso contrário None.
        """
        if hrv_recent is None or hrv_baseline is None or hrv_baseline == 0:
            return None
        drop_pct = (hrv_baseline - hrv_recent) / hrv_baseline * 100
        if drop_pct > 15 and atl > 80:
            return OverreachingAlert(
                type="hrv_suppressed",
                severity="warning",
                message=(
                    f"HRV {drop_pct:.0f}% abaixo da média de 14 dias com fadiga alta (ATL {atl:.0f}). "
                    "Sistema nervoso sobrecarregado — considere dia de recuperação."
                ),
                metric_value=drop_pct,
                threshold=15,
            )
        return None

    def compute_all(
        self,
        tsb: float,
        atl: float,
        tss_by_week: list[float],
        hrv_recent: float | None = None,
        hrv_baseline: float | None = None,
    ) -> list[OverreachingAlert]:
        """Executa todas as verificações e retorna a lista de alertas ativos.

        Args:
            tsb: Training Stress Balance atual
            atl: Acute Training Load atual
            tss_by_week: TSS por semana (mais recente por último)
            hrv_recent: HRV mais recente
            hrv_baseline: média HRV dos últimos 14 dias

        Returns:
            Lista de alertas (vazia se nenhum threshold for excedido).
        """
        alerts: list[OverreachingAlert] = []
        for check in [
            self.check_tsb(tsb),
            self.check_ramp_rate(tss_by_week),
            self.check_hrv_suppression(hrv_recent, hrv_baseline, atl),
        ]:
            if check is not None:
                alerts.append(check)
        return alerts
