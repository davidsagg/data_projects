"""
Análise de execução — como a intensidade foi distribuída ao longo do esforço.

Vem do workflow de análise de prova do post do Marco Altini: dividir o esforço
em quartos e olhar a distribuição de zonas de cada um. A leitura é imediata e
não precisa de número nenhum — se o primeiro quarto está deslocado para as zonas
altas e o último desabou para as baixas, o atleta saiu forte demais. Se os
quatro são parecidos, a execução foi regular.

O corte é por **tempo em movimento**, não por distância: numa prova de montanha
os quartos por distância teriam durações completamente diferentes e a comparação
perderia o sentido. Também não atravessa pausa — o quarto é construído sobre os
segmentos contínuos concatenados.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from analytics.timeseries import ActivitySeries
from analytics.zones import Zone, time_in_zones

QUARTERS = 4


@dataclass(frozen=True)
class QuarterProfile:
    """Distribuição de intensidade de um quarto do esforço."""

    quarter: int
    start_s: int
    duration_s: int
    zone_seconds: dict[str, int]
    avg_power_w: float | None
    avg_hr_bpm: float | None
    normalized_power_w: float | None

    @property
    def zone_pct(self) -> dict[str, float]:
        """Percentual do quarto passado em cada zona."""
        total = sum(self.zone_seconds.values()) or 1
        return {
            zone: round(seconds / total * 100, 1)
            for zone, seconds in self.zone_seconds.items()
        }

    def to_dict(self) -> dict:
        return {
            "quarter": self.quarter,
            "start_s": self.start_s,
            "duration_s": self.duration_s,
            "zone_seconds": self.zone_seconds,
            "zone_pct": self.zone_pct,
            "avg_power_w": self.avg_power_w,
            "avg_hr_bpm": self.avg_hr_bpm,
            "normalized_power_w": self.normalized_power_w,
        }


def analyze_pacing(
    series: ActivitySeries,
    zones: list[Zone],
    channel: str = "power",
) -> dict:
    """Divide o esforço em quartos e descreve a intensidade de cada um.

    Args:
        series: série já segmentada da atividade.
        zones: zonas em unidade absoluta, do canal escolhido.
        channel: `power` ou `hr`.

    Returns:
        Dicionário com os quartos e o veredito de execução.
    """
    values = series.concat(channel)
    if values.size < QUARTERS * 60:
        return {"quarters": [], "verdict": "curto demais para analisar"}

    power = np.nan_to_num(series.concat("power"), nan=np.nan)
    hr = series.concat("hr") if series.has_data("hr") else None

    size = values.size // QUARTERS
    profiles: list[QuarterProfile] = []

    for q in range(QUARTERS):
        start = q * size
        end = values.size if q == QUARTERS - 1 else (q + 1) * size
        sliced = _slice_series(series, channel, start, end)

        profiles.append(
            QuarterProfile(
                quarter=q + 1,
                start_s=start,
                duration_s=end - start,
                zone_seconds=time_in_zones(sliced, zones, channel),
                avg_power_w=_mean(power[start:end]),
                avg_hr_bpm=_mean(hr[start:end]) if hr is not None else None,
                normalized_power_w=_normalized_power(power[start:end]),
            )
        )

    return {
        "quarters": [p.to_dict() for p in profiles],
        "verdict": _verdict(profiles, zones),
        "decoupling_first_to_last": _drift(profiles),
    }


def load_density(
    series: ActivitySeries,
    power_bin_w: int = 25,
    hr_bin_bpm: int = 5,
) -> dict:
    """Densidade conjunta de carga externa (potência) e interna (FC).

    A leitura é a relação entre o que o atleta produziu e o que aquilo custou.
    Comparada entre períodos, a nuvem inteira se desloca: para cima e para a
    esquerda quando há ganho de base (mesma potência, menos batimentos).

    Args:
        series: série já segmentada da atividade.
        power_bin_w: largura da faixa de potência.
        hr_bin_bpm: largura da faixa de frequência cardíaca.

    Returns:
        Células ocupadas com a contagem de segundos, mais os limites dos eixos.
    """
    if not series.has_data("power") or not series.has_data("hr"):
        return {"cells": [], "power_bin_w": power_bin_w, "hr_bin_bpm": hr_bin_bpm}

    power = series.concat("power")
    hr = series.concat("hr")
    size = min(power.size, hr.size)
    power, hr = power[:size], hr[:size]

    # Só pontos com as duas medidas: um ponto sem FC não diz nada sobre custo.
    valid = np.isfinite(power) & np.isfinite(hr)
    power, hr = power[valid], hr[valid]
    if power.size == 0:
        return {"cells": [], "power_bin_w": power_bin_w, "hr_bin_bpm": hr_bin_bpm}

    power_bins = (power // power_bin_w).astype(int) * power_bin_w
    hr_bins = (hr // hr_bin_bpm).astype(int) * hr_bin_bpm

    pairs, counts = np.unique(
        np.stack([power_bins, hr_bins], axis=1), axis=0, return_counts=True
    )

    return {
        "cells": [
            {"power_w": int(p), "hr_bpm": int(h), "seconds": int(c)}
            for (p, h), c in zip(pairs, counts)
        ],
        "power_bin_w": power_bin_w,
        "hr_bin_bpm": hr_bin_bpm,
        "total_seconds": int(counts.sum()),
        "power_range": [int(power_bins.min()), int(power_bins.max() + power_bin_w)],
        "hr_range": [int(hr_bins.min()), int(hr_bins.max() + hr_bin_bpm)],
    }


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _slice_series(
    series: ActivitySeries, channel: str, start: int, end: int
) -> ActivitySeries:
    """Recorta a série concatenada num pedaço, preservando os canais.

    O recorte é sobre a série já concatenada, então a fatia pode cruzar a
    fronteira de dois segmentos. Isso é aceitável aqui: `time_in_zones` é um
    histograma, sem noção de vizinhança, e não seria afetado por uma emenda.
    """
    from analytics.timeseries import Segment

    channels = {}
    for name in ("power", "hr", "cadence", "speed", "altitude", "distance"):
        values = series.concat(name)
        if values.size >= end:
            channels[name] = values[start:end]

    return ActivitySeries(
        series.activity_id, [Segment(start_time_s=start, channels=channels)]
    )


def _mean(values: np.ndarray) -> float | None:
    if values.size == 0 or not np.isfinite(values).any():
        return None
    return round(float(np.nanmean(values)), 1)


def _normalized_power(values: np.ndarray) -> float | None:
    """NP do trecho — média da quarta potência da média móvel de 30 s."""
    clean = np.nan_to_num(values, nan=0.0)
    if clean.size < 30:
        return None
    cumulative = np.cumsum(np.insert(clean, 0, 0.0))
    rolled = (cumulative[30:] - cumulative[:-30]) / 30
    if rolled.size == 0:
        return None
    return round(float(np.power(np.power(rolled, 4).mean(), 0.25)), 1)


def _intensity_index(profile: QuarterProfile, zones: list[Zone]) -> float:
    """Índice médio de zona do quarto, ponderado pelo tempo.

    Condensa a distribuição num número comparável entre quartos: 1,0 significa
    tudo em Z1; 4,5 significa a maior parte entre Z4 e Z5.
    """
    total = sum(profile.zone_seconds.values())
    if total == 0:
        return 0.0
    return sum(
        zone.number * profile.zone_seconds.get(zone.name, 0) for zone in zones
    ) / total


def _verdict(profiles: list[QuarterProfile], zones: list[Zone]) -> str:
    """Classifica a execução comparando o primeiro quarto com o último."""
    indices = [_intensity_index(p, zones) for p in profiles]
    if not any(indices):
        return "sem dados de intensidade"

    drop = indices[0] - indices[-1]
    if drop > 0.8:
        return "saiu forte demais"
    if drop < -0.8:
        return "negative split"
    return "execução regular"


def _drift(profiles: list[QuarterProfile]) -> float | None:
    """Deriva da razão potência/FC entre o primeiro e o último quarto.

    É o mesmo princípio do decoupling, aplicado aos extremos do esforço: quanto
    o custo cardíaco de produzir a mesma potência subiu do começo ao fim.
    """
    first, last = profiles[0], profiles[-1]
    if not all([first.normalized_power_w, first.avg_hr_bpm,
                last.normalized_power_w, last.avg_hr_bpm]):
        return None

    start_ratio = first.normalized_power_w / first.avg_hr_bpm
    end_ratio = last.normalized_power_w / last.avg_hr_bpm
    if start_ratio <= 0:
        return None
    return round((end_ratio / start_ratio - 1) * 100, 1)
