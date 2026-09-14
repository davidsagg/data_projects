"""
Power Curve Engine — Mean Maximal Power (MMP) por duração.

A curva de potência é o melhor esforço sustentado em cada duração. Duas
armadilhas moldam esta implementação:

1. **Um esforço não atravessa uma pausa.** A versão anterior projetava a
   atividade num array contíguo e preenchia as lacunas com 0 W: um treino com
   parada de 10 minutos ganhava 600 amostras de potência zero, destruindo
   qualquer janela longa que passasse por ali.
2. **Janela deslizante O(n)**, não O(n·d). Com 7,6 milhões de pontos, buscar o
   máximo de cada janela isoladamente é inviável.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from analytics.power_metrics import rolling_mean
from analytics.timeseries import ActivitySeries, load_series

# 720 s (12 min) entra porque é a duração longa do protocolo de teste do atleta;
# junto com os 60 s, forma o par de esforços máximos que alimenta o modelo CP/W'.
DEFAULT_DURATIONS: list[int] = [
    1, 5, 10, 15, 20, 30, 60, 120, 300, 480, 600, 720, 900, 1200, 1800, 2700,
    3600, 5400, 7200,
]


class PowerCurveEngine:
    """Calcula a curva de potência (MMP) a partir de uma ActivitySeries."""

    def compute(
        self,
        series: ActivitySeries,
        durations: list[int] | None = None,
    ) -> dict[int, float]:
        """Retorna o melhor esforço médio para cada duração pedida.

        Args:
            series: série já segmentada da atividade.
            durations: durações em segundos; usa `DEFAULT_DURATIONS` se omitido.

        Returns:
            Dicionário {duração: melhor_potência_w}, omitindo as durações que
            não cabem em nenhum segmento contínuo.
        """
        durations = durations or DEFAULT_DURATIONS
        segments = [
            np.nan_to_num(power, nan=0.0)
            for power in series.channel("power")
        ]
        segments = [s for s in segments if s.size]
        if not segments:
            return {}

        curve: dict[int, float] = {}
        for duration in durations:
            best: float | None = None
            for segment in segments:
                if segment.size < duration:
                    continue
                rolled = rolling_mean(segment, duration)
                if rolled.size:
                    top = float(rolled.max())
                    best = top if best is None else max(best, top)
            if best is not None:
                curve[duration] = round(best, 1)
        return curve


def compute_power_curve(
    series: ActivitySeries,
    durations: list[int] | None = None,
) -> dict[int, float]:
    """Atalho funcional para `PowerCurveEngine.compute`.

    Args:
        series: série já segmentada da atividade.
        durations: durações em segundos.

    Returns:
        Dicionário {duração: melhor_potência_w}.
    """
    return PowerCurveEngine().compute(series, durations)


def update_curve_in_db(
    store,
    activity_id: str,
    activity_date: date,
    durations: list[int] | None = None,
) -> dict[int, float]:
    """Calcula e persiste a curva de potência de uma atividade.

    O upsert é por (activity_id, duration_s), então recalcular é idempotente.

    Args:
        store: CatalogStore com conexão ativa.
        activity_id: UUID da atividade.
        activity_date: data da atividade, usada para filtrar a curva por período.
        durations: durações em segundos.

    Returns:
        A curva persistida.
    """
    series = load_series(store.conn, activity_id)
    curve = PowerCurveEngine().compute(series, durations)
    if curve:
        store.save_power_curve(activity_id, activity_date, curve)
    return curve
