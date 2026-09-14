"""
Métricas de potência de uma atividade — NP, IF, VI, EF e TSS.

Referência: Coggan & Allen, "Training and Racing with a Power Meter".

A Normalized Power é uma média móvel de 30 s elevada à quarta potência: o
expoente amplifica os picos, refletindo o custo fisiológico desproporcional dos
esforços variáveis. Por isso a janela **não pode atravessar uma pausa** — juntar
os dois lados de um semáforo cria uma rampa artificial de potência que o
expoente 4 amplifica.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from analytics.timeseries import ActivitySeries

ROLLING_WINDOW_S = 30

# Abaixo disso a janela de 30 s não cabe e a NP não é definida.
MIN_SAMPLES_FOR_NP = ROLLING_WINDOW_S


@dataclass(frozen=True)
class PowerMetrics:
    """Métricas derivadas da série de potência de uma atividade."""

    normalized_power_w: float | None = None
    intensity_factor: float | None = None
    variability_index: float | None = None
    efficiency_factor: float | None = None
    avg_power_w: float | None = None
    max_power_w: float | None = None
    tss: float | None = None


def rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    """Média móvel causal de tamanho fixo.

    Args:
        values: série de entrada, sem NaN.
        window: tamanho da janela em amostras.

    Returns:
        Array com `len(values) - window + 1` médias; vazio se não couber.
    """
    if values.size < window:
        return np.array([])
    cumulative = np.cumsum(np.insert(values, 0, 0.0))
    return (cumulative[window:] - cumulative[:-window]) / window


def normalized_power(series: ActivitySeries, window: int = ROLLING_WINDOW_S) -> float | None:
    """Calcula a Normalized Power respeitando as pausas da atividade.

    Cada segmento contínuo contribui com suas médias móveis de 30 s; a média da
    quarta potência é feita sobre o conjunto de todas elas.

    Args:
        series: série já segmentada da atividade.
        window: tamanho da janela móvel, em segundos.

    Returns:
        NP em watts, ou None se não há janela de 30 s completa com potência.
    """
    fourth_powers: list[np.ndarray] = []

    for segment_power in series.channel("power"):
        clean = np.nan_to_num(segment_power, nan=0.0)
        if clean.size < window:
            continue
        rolled = rolling_mean(clean, window)
        fourth_powers.append(np.power(rolled, 4))

    if not fourth_powers:
        return None

    mean_fourth = np.concatenate(fourth_powers).mean()
    return float(np.power(mean_fourth, 0.25))


def compute_power_metrics(
    series: ActivitySeries,
    ftp_w: float | None,
) -> PowerMetrics:
    """Calcula o conjunto de métricas de potência de uma atividade.

    Args:
        series: série já segmentada da atividade.
        ftp_w: FTP vigente na data da atividade; sem ele não há IF nem TSS.

    Returns:
        PowerMetrics com os campos que puderam ser calculados.
    """
    if not series.has_data("power"):
        return PowerMetrics()

    power = np.nan_to_num(series.concat("power"), nan=0.0)
    avg_power = float(power.mean())
    max_power = float(power.max())

    np_w = normalized_power(series)
    metrics = {
        "avg_power_w": round(avg_power, 1),
        "max_power_w": round(max_power, 1),
        "normalized_power_w": round(np_w, 1) if np_w is not None else None,
    }

    if np_w is not None and avg_power > 0:
        metrics["variability_index"] = round(np_w / avg_power, 3)

    if np_w is not None and series.has_data("hr"):
        hr = series.concat("hr")
        mean_hr = float(np.nanmean(hr))
        if mean_hr > 0:
            metrics["efficiency_factor"] = round(np_w / mean_hr, 3)

    if np_w is not None and ftp_w:
        intensity = np_w / ftp_w
        metrics["intensity_factor"] = round(intensity, 3)
        metrics["tss"] = round(
            series.moving_time_s * np_w * intensity / (ftp_w * 3600) * 100, 1
        )

    return PowerMetrics(**metrics)
