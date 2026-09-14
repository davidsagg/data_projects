"""
Detecção automática de intervalos — separa esforço de recuperação.

Um treino estruturado guarda sua própria estrutura: 4 × 8 min a 240 W com 4 min
de giro leve entre eles está tudo lá na série de potência, mas o resumo da
atividade mostra só "1h20, NP 198 W". A média esconde exatamente o que
distingue um treino de intervalos de um rodízio constante com a mesma carga.

O algoritmo é deliberadamente simples e explicável:

1. Suaviza a potência numa janela curta, para que uma oscilação de um segundo
   não abra e feche um intervalo.
2. Marca como esforço tudo acima de uma fração do FTP vigente.
3. Junta trechos de esforço separados por lacunas curtas — respirar dois
   segundos no meio de um bloco não o transforma em dois blocos.
4. Descarta o que for curto demais para ser proposital.
5. Agrupa os intervalos resultantes em séries de duração e potência parecidas,
   que é como o ciclista descreve o treino.

**Pausas** nunca são atravessadas: cada segmento contínuo é analisado por conta
própria, então um intervalo jamais começa antes de um semáforo e termina depois.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from analytics.power_metrics import rolling_mean
from analytics.timeseries import ActivitySeries

# Janela de suavização. Curta o bastante para não borrar o início de um bloco,
# longa o bastante para ignorar o ruído segundo a segundo do medidor.
SMOOTHING_WINDOW_S = 10

# Fração do FTP acima da qual o segundo conta como esforço. 0,88 fica na
# fronteira entre o ritmo de base e o trabalho de verdade: um sweet spot a 90%
# entra, um rodízio de endurance a 70% não.
DEFAULT_THRESHOLD_RATIO = 0.88

# Abaixo disso não é intervalo, é variação de terreno.
MIN_INTERVAL_S = 30

# Lacuna curta dentro de um bloco não o parte em dois.
MAX_MERGE_GAP_S = 15

# Tolerâncias para considerar dois intervalos parte da mesma série.
SET_DURATION_TOLERANCE = 0.25
SET_POWER_TOLERANCE = 0.10


@dataclass(frozen=True)
class Interval:
    """Um esforço contínuo detectado dentro da atividade."""

    start_s: int
    duration_s: int
    avg_power_w: float
    max_power_w: float
    normalized_power_w: float | None = None
    avg_hr_bpm: float | None = None
    avg_cadence_rpm: float | None = None
    recovery_s: int | None = None
    recovery_power_w: float | None = None

    @property
    def end_s(self) -> int:
        """Instante final do intervalo, relativo ao início da atividade."""
        return self.start_s + self.duration_s

    def intensity_factor(self, ftp_w: float | None) -> float | None:
        """Intensidade do intervalo em relação ao FTP informado."""
        if not ftp_w:
            return None
        return round(self.avg_power_w / ftp_w, 3)


@dataclass(frozen=True)
class IntervalSet:
    """Grupo de intervalos parecidos — a série como o ciclista a descreve."""

    count: int
    avg_duration_s: float
    avg_power_w: float
    avg_recovery_s: float | None
    intervals: list[Interval]

    def label(self, ftp_w: float | None = None) -> str:
        """Descrição curta da série, por exemplo `4 × 8min @ 240 W (IF 1,11)`."""
        minutes = self.avg_duration_s / 60
        duration = (
            f"{minutes:.0f}min" if minutes >= 1 else f"{self.avg_duration_s:.0f}s"
        )
        text = f"{self.count} × {duration} @ {self.avg_power_w:.0f} W"
        if ftp_w:
            text += f" (IF {self.avg_power_w / ftp_w:.2f})".replace(".", ",")
        return text


def detect_intervals(
    series: ActivitySeries,
    ftp_w: float | None,
    threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
    min_duration_s: int = MIN_INTERVAL_S,
) -> list[Interval]:
    """Encontra os blocos de esforço de uma atividade.

    Args:
        series: série já segmentada da atividade.
        ftp_w: FTP vigente na data; sem ele não há limiar de referência.
        threshold_ratio: fração do FTP que separa esforço de recuperação.
        min_duration_s: duração mínima para um bloco contar como intervalo.

    Returns:
        Intervalos em ordem cronológica; lista vazia se não há potência ou FTP.
    """
    if not ftp_w or not series.has_data("power"):
        return []

    threshold = ftp_w * threshold_ratio
    found: list[Interval] = []

    for segment_index, power in enumerate(series.channel("power")):
        clean = np.nan_to_num(power, nan=0.0)
        if clean.size < min_duration_s:
            continue

        offset = series.segments[segment_index].start_time_s
        smoothed = _smooth(clean)
        spans = _merge_gaps(_runs_above(smoothed, threshold), MAX_MERGE_GAP_S)

        hr = _segment_channel(series, "hr", segment_index)
        cadence = _segment_channel(series, "cadence", segment_index)

        for position, (start, end) in enumerate(spans):
            if end - start < min_duration_s:
                continue
            recovery_s, recovery_power = _recovery_after(spans, position, clean)
            found.append(
                _build_interval(
                    clean, hr, cadence, offset, start, end, recovery_s, recovery_power
                )
            )

    return found


def group_into_sets(intervals: list[Interval]) -> list[IntervalSet]:
    """Agrupa intervalos consecutivos de duração e potência semelhantes.

    Args:
        intervals: intervalos em ordem cronológica.

    Returns:
        Séries na ordem em que aparecem no treino.
    """
    if not intervals:
        return []

    groups: list[list[Interval]] = [[intervals[0]]]
    for interval in intervals[1:]:
        if _belongs_to(interval, groups[-1]):
            groups[-1].append(interval)
        else:
            groups.append([interval])

    return [_build_set(group) for group in groups]


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _smooth(power: np.ndarray) -> np.ndarray:
    """Média móvel centrada, preservando o comprimento do array."""
    if power.size < SMOOTHING_WINDOW_S:
        return power
    rolled = rolling_mean(power, SMOOTHING_WINDOW_S)
    pad_left = (power.size - rolled.size) // 2
    pad_right = power.size - rolled.size - pad_left
    return np.pad(rolled, (pad_left, pad_right), mode="edge")


def _runs_above(values: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    """Devolve os trechos `[início, fim)` em que o valor fica acima do limiar."""
    above = values > threshold
    if not above.any():
        return []

    edges = np.diff(above.astype(np.int8))
    starts = list(np.flatnonzero(edges == 1) + 1)
    ends = list(np.flatnonzero(edges == -1) + 1)

    if above[0]:
        starts.insert(0, 0)
    if above[-1]:
        ends.append(above.size)

    return list(zip(starts, ends))


def _merge_gaps(spans: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    """Funde trechos separados por uma lacuna menor que `max_gap`."""
    if not spans:
        return []

    merged = [spans[0]]
    for start, end in spans[1:]:
        previous_start, previous_end = merged[-1]
        if start - previous_end <= max_gap:
            merged[-1] = (previous_start, end)
        else:
            merged.append((start, end))
    return merged


def _recovery_after(
    spans: list[tuple[int, int]],
    position: int,
    power: np.ndarray,
) -> tuple[int | None, float | None]:
    """Mede a recuperação entre um intervalo e o próximo."""
    if position + 1 >= len(spans):
        return None, None
    end = spans[position][1]
    next_start = spans[position + 1][0]
    gap = power[end:next_start]
    if gap.size == 0:
        return None, None
    return int(gap.size), round(float(gap.mean()), 1)


def _segment_channel(
    series: ActivitySeries, name: str, index: int
) -> np.ndarray | None:
    """Devolve um canal do segmento, ou None se não houver medida."""
    values = series.channel(name)[index]
    return values if np.isfinite(values).any() else None


def _build_interval(
    power: np.ndarray,
    hr: np.ndarray | None,
    cadence: np.ndarray | None,
    offset: int,
    start: int,
    end: int,
    recovery_s: int | None,
    recovery_power: float | None,
) -> Interval:
    """Monta o `Interval` a partir das fatias de cada canal."""
    block = power[start:end]
    fourth = rolling_mean(block, 30)

    return Interval(
        start_s=offset + int(start),
        duration_s=int(end - start),
        avg_power_w=round(float(block.mean()), 1),
        max_power_w=round(float(block.max()), 1),
        normalized_power_w=(
            round(float(np.power(np.power(fourth, 4).mean(), 0.25)), 1)
            if fourth.size
            else None
        ),
        avg_hr_bpm=_mean_slice(hr, start, end),
        avg_cadence_rpm=_mean_slice(cadence, start, end),
        recovery_s=recovery_s,
        recovery_power_w=recovery_power,
    )


def _mean_slice(values: np.ndarray | None, start: int, end: int) -> float | None:
    """Média de uma fatia, ignorando NaN e fatias sem medida."""
    if values is None:
        return None
    block = values[start:end]
    if block.size == 0 or not np.isfinite(block).any():
        return None
    return round(float(np.nanmean(block)), 1)


def _belongs_to(interval: Interval, group: list[Interval]) -> bool:
    """Decide se o intervalo continua a série do grupo."""
    reference = group[0]
    duration_ok = abs(interval.duration_s - reference.duration_s) <= max(
        reference.duration_s * SET_DURATION_TOLERANCE, 10
    )
    power_ok = abs(interval.avg_power_w - reference.avg_power_w) <= max(
        reference.avg_power_w * SET_POWER_TOLERANCE, 5
    )
    return duration_ok and power_ok


def _build_set(group: list[Interval]) -> IntervalSet:
    """Resume um grupo de intervalos numa série."""
    recoveries = [i.recovery_s for i in group if i.recovery_s is not None]
    return IntervalSet(
        count=len(group),
        avg_duration_s=round(sum(i.duration_s for i in group) / len(group), 1),
        avg_power_w=round(sum(i.avg_power_w for i in group) / len(group), 1),
        avg_recovery_s=(
            round(sum(recoveries) / len(recoveries), 1) if recoveries else None
        ),
        intervals=group,
    )
