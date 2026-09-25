"""
Detecção e análise de subidas.

Num pedal de montanha, a média da atividade inteira não descreve nada: 129 W de
média num dia de 1.570 m de elevação mistura 25 minutos a 210 W subindo com meia
hora a 0 W descendo. O que descreve o esforço é o que aconteceu em cada subida.

A métrica central é o **VAM** (Velocità Ascensionale Media) — metros verticais
por hora. É o que permite comparar subidas de inclinações e durações diferentes,
e o que mostra progressão ao longo da temporada melhor que a potência bruta,
porque já carrega o efeito do peso.

    VAM = ganho de elevação (m) ÷ duração (h)

O algoritmo é de limiar com histerese: acumula ganho enquanto o terreno sobe,
tolera trechos curtos de descida dentro da subida (nenhuma subida real é
monotônica) e encerra quando a descida passa de um limite. Sem a histerese,
qualquer ondulação partiria uma subida de 8 km em quarenta pedaços.

**Pausas** nunca são atravessadas: cada segmento contínuo é analisado por conta
própria, senão parar no meio da subida para tirar foto viraria uma subida de
duas horas com VAM ridículo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from analytics.timeseries import ActivitySeries

# Suavização da altitude. O barômetro oscila metro a metro mesmo em terreno
# plano, e sem suavizar a detecção vira ruído.
SMOOTHING_WINDOW_S = 20

# Ganho mínimo para um trecho contar como subida. Abaixo disso é ondulação.
MIN_GAIN_M = 30.0

# Inclinação média mínima. Um trecho que sobe 40 m em 5 km não é uma subida,
# é um falso plano.
MIN_GRADIENT_PCT = 3.0

# Duração mínima — evita que um lance de 15 s vire "subida".
MIN_DURATION_S = 60

# Teto de plausibilidade. Nenhuma subida pedalável sustenta mais que isto por
# minutos a fio; acima disso é artefato de barômetro ou de GPS, e o projeto já
# trata artefato de sensor assim em `timeseries.PLAUSIBLE_RANGE`.
MAX_PLAUSIBLE_GRADIENT_PCT = 25.0

# Quanto o atleta pode descer dentro de uma subida antes de ela ser considerada
# encerrada. É a histerese que impede a fragmentação.
MAX_INTERNAL_DROP_M = 12.0


@dataclass(frozen=True)
class Climb:
    """Uma subida detectada dentro da atividade."""

    start_s: int
    duration_s: int
    distance_m: float
    elevation_gain_m: float
    avg_gradient_pct: float
    max_gradient_pct: float
    vam_mh: float
    avg_power_w: float | None = None
    avg_hr_bpm: float | None = None
    avg_cadence_rpm: float | None = None

    @property
    def end_s(self) -> int:
        """Instante final, relativo ao início da atividade."""
        return self.start_s + self.duration_s

    def watts_per_kg(self, weight_kg: float | None) -> float | None:
        """Potência relativa — a leitura que importa subindo."""
        if not weight_kg or self.avg_power_w is None:
            return None
        return round(self.avg_power_w / weight_kg, 2)

    def category(self) -> str:
        """Classificação aproximada pelo produto ganho × inclinação.

        Segue o critério usado no ciclismo de estrada (o mesmo do Strava, em
        espírito): o produto de metros por percentual separa bem uma rampa curta
        e brutal de uma subida longa e suave.
        """
        score = self.elevation_gain_m * self.avg_gradient_pct
        if score >= 8000:
            return "HC"
        if score >= 6400:
            return "1"
        if score >= 3200:
            return "2"
        if score >= 1600:
            return "3"
        if score >= 800:
            return "4"
        return "sem categoria"


def detect_climbs(
    series: ActivitySeries,
    min_gain_m: float = MIN_GAIN_M,
    min_gradient_pct: float = MIN_GRADIENT_PCT,
) -> list[Climb]:
    """Encontra as subidas de uma atividade.

    Args:
        series: série já segmentada da atividade.
        min_gain_m: ganho mínimo de elevação para contar como subida.
        min_gradient_pct: inclinação média mínima.

    Returns:
        Subidas em ordem cronológica; vazio se não houver altitude ou distância.
    """
    if not series.has_data("altitude") or not series.has_data("distance"):
        return []

    climbs: list[Climb] = []

    for index, segment in enumerate(series.segments):
        altitude = series.channel("altitude")[index]
        distance = series.channel("distance")[index]
        if altitude.size < MIN_DURATION_S:
            continue

        smoothed = _smooth(np.nan_to_num(altitude, nan=0.0))
        spans = _ascending_spans(smoothed)

        power = _channel_or_none(series, "power", index)
        hr = _channel_or_none(series, "hr", index)
        cadence = _channel_or_none(series, "cadence", index)

        for start, end in spans:
            climb = _build_climb(
                smoothed, distance, power, hr, cadence,
                segment.start_time_s, start, end,
            )
            if (
                climb is not None
                and climb.elevation_gain_m >= min_gain_m
                and min_gradient_pct <= climb.avg_gradient_pct
                <= MAX_PLAUSIBLE_GRADIENT_PCT
                and climb.duration_s >= MIN_DURATION_S
            ):
                climbs.append(climb)

    return climbs


def summarize_climbs(climbs: list[Climb]) -> dict:
    """Agrega o conjunto de subidas de uma atividade.

    Args:
        climbs: subidas detectadas.

    Returns:
        Totais e a melhor subida pelo VAM.
    """
    if not climbs:
        return {
            "count": 0,
            "total_gain_m": 0.0,
            "total_duration_s": 0,
            "best_vam_mh": None,
        }

    best = max(climbs, key=lambda c: c.vam_mh)
    return {
        "count": len(climbs),
        "total_gain_m": round(sum(c.elevation_gain_m for c in climbs), 1),
        "total_duration_s": sum(c.duration_s for c in climbs),
        "total_distance_m": round(sum(c.distance_m for c in climbs), 1),
        "best_vam_mh": best.vam_mh,
        "best_climb_start_s": best.start_s,
        "avg_vam_mh": round(sum(c.vam_mh for c in climbs) / len(climbs), 1),
    }


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _smooth(values: np.ndarray) -> np.ndarray:
    """Média móvel centrada, preservando o comprimento.

    O padding é de **borda**, não de zero. `np.convolve(mode="same")` completa
    as pontas com zeros, e numa série de altitude que começa em 722 m isso cria
    uma rampa artificial de 0 a 722 m nos primeiros segundos — que o detector
    lê como uma subida de 384 m a 100% de inclinação. Repetir o primeiro e o
    último valor mantém as pontas no nível real do terreno.
    """
    if values.size < SMOOTHING_WINDOW_S:
        return values

    cumulative = np.cumsum(np.insert(values, 0, 0.0))
    rolled = (
        cumulative[SMOOTHING_WINDOW_S:] - cumulative[:-SMOOTHING_WINDOW_S]
    ) / SMOOTHING_WINDOW_S
    pad_left = (values.size - rolled.size) // 2
    pad_right = values.size - rolled.size - pad_left
    return np.pad(rolled, (pad_left, pad_right), mode="edge")


def _ascending_spans(altitude: np.ndarray) -> list[tuple[int, int]]:
    """Encontra os trechos de subida sustentada, com histerese.

    Percorre a série acumulando ganho. Um recuo é tolerado enquanto for menor
    que `MAX_INTERNAL_DROP_M` a partir do pico da subida corrente; acima disso,
    a subida é encerrada no pico e uma nova pode começar.
    """
    spans: list[tuple[int, int]] = []
    start: int | None = None
    peak_index = 0
    peak_value = altitude[0] if altitude.size else 0.0

    for i in range(1, altitude.size):
        value = altitude[i]

        if start is None:
            # Começa a contar quando o terreno vira para cima.
            if value > altitude[i - 1]:
                start = i - 1
                peak_index, peak_value = i, value
            continue

        if value >= peak_value:
            peak_index, peak_value = i, value
        elif peak_value - value > MAX_INTERNAL_DROP_M:
            spans.append((start, peak_index))
            start = None
            peak_value = value

    if start is not None and peak_index > start:
        spans.append((start, peak_index))

    return spans


def _channel_or_none(
    series: ActivitySeries, name: str, index: int
) -> np.ndarray | None:
    values = series.channel(name)[index]
    return values if np.isfinite(values).any() else None


def _build_climb(
    altitude: np.ndarray,
    distance: np.ndarray,
    power: np.ndarray | None,
    hr: np.ndarray | None,
    cadence: np.ndarray | None,
    offset: int,
    start: int,
    end: int,
) -> Climb | None:
    """Monta a `Climb` a partir das fatias de cada canal."""
    duration = end - start
    if duration <= 0:
        return None

    gain = float(altitude[end] - altitude[start])
    if gain <= 0:
        return None

    run = _distance_between(distance, start, end)
    if run <= 0:
        return None

    gradient = gain / run * 100
    hours = duration / 3600

    return Climb(
        start_s=offset + int(start),
        duration_s=int(duration),
        distance_m=round(run, 1),
        elevation_gain_m=round(gain, 1),
        avg_gradient_pct=round(gradient, 1),
        max_gradient_pct=_max_gradient(altitude, distance, start, end),
        vam_mh=round(gain / hours, 1) if hours > 0 else 0.0,
        avg_power_w=_mean_slice(power, start, end),
        avg_hr_bpm=_mean_slice(hr, start, end),
        avg_cadence_rpm=_mean_slice(cadence, start, end),
    )


def _distance_between(distance: np.ndarray, start: int, end: int) -> float:
    """Distância percorrida no trecho, tolerando canal ausente."""
    if distance.size <= end:
        return 0.0
    span = float(np.nan_to_num(distance[end]) - np.nan_to_num(distance[start]))
    return max(span, 0.0)


def _max_gradient(
    altitude: np.ndarray, distance: np.ndarray, start: int, end: int
) -> float:
    """Inclinação máxima sustentada em janelas de 30 s dentro da subida.

    O máximo instantâneo seria ruído de barômetro; a janela de meio minuto é
    curta o bastante para achar a rampa e longa o bastante para não inventá-la.
    """
    window = 30
    if end - start <= window or distance.size <= end:
        return 0.0

    best = 0.0
    for i in range(start, end - window):
        rise = float(altitude[i + window] - altitude[i])
        run = _distance_between(distance, i, i + window)
        if run > 5:
            best = max(best, rise / run * 100)
    return round(best, 1)


def _mean_slice(values: np.ndarray | None, start: int, end: int) -> float | None:
    if values is None:
        return None
    block = values[start:end]
    if block.size == 0 or not np.isfinite(block).any():
        return None
    return round(float(np.nanmean(block)), 1)
