"""
W'bal sobre o terreno — onde, no percurso, o tanque esvaziou.

A curva de W'bal sozinha diz *quando* a reserva acabou ("aos 2h47"), e essa é a
informação errada para quem pedalou: ninguém lembra do minuto, lembra da
subida. Alinhada à elevação e à distância, a mesma curva responde "o gás acabou
no km 64, no fim de uma rampa de 180 m" — e daí sai a lição de ritmo.

Dois cuidados:

**Alinhamento.** O W'bal é calculado sobre os segundos em movimento, segmento a
segmento. Desenhar esse vetor contra o tempo total (índice × duração/pontos),
como o gráfico anterior fazia, desloca cada mergulho para a direita a cada
pausa. Aqui cada ponto carrega o próprio `time_s` e a própria distância.

**Decimação.** Reduzir 15 mil pontos a 900 pegando um a cada N perde
justamente os fundos dos mergulhos, que duram segundos. Cada balde fica com o
ponto de **menor** W' — o que se quer ver é o pior momento, não um momento
qualquer.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import pairwise

import numpy as np

from analytics.timeseries import ActivitySeries

# Abaixo desta fração do W' o tanque está "na reserva" — o atleta ainda pedala,
# mas não tem mais com o que responder a um ataque ou a uma rampa.
DEPLETED_FRACTION = 0.25

# Episódio mais curto que isso é ruído de um sprint, não falta de gás.
MIN_EPISODE_S = 10

# Dois mergulhos separados por menos que isso são o mesmo esforço.
MERGE_GAP_S = 30

# Janela antes do fundo usada para descrever o terreno que levou até ele.
LEAD_IN_S = 600

# Ganho mínimo para a aproximação contar como rampa (abaixo é ondulação).
MIN_CLIMB_GAIN_M = 10

# Inclinação média a partir da qual o trecho de aproximação é "subida".
CLIMB_GRADE_PCT = 3.0


@dataclass(frozen=True)
class DepletionEpisode:
    """Um trecho contínuo com o W' abaixo do limiar de reserva."""

    start_s: int
    end_s: int
    min_s: int
    min_pct: float
    start_km: float | None
    end_km: float | None
    avg_power_w: float | None
    lead_gain_m: float | None
    lead_grade_pct: float | None
    terrain: str

    @property
    def duration_s(self) -> int:
        return self.end_s - self.start_s + 1

    def to_dict(self) -> dict:
        return {**asdict(self), "duration_s": self.duration_s}


def aligned_channels(series: ActivitySeries) -> dict[str, np.ndarray]:
    """Tempo, distância, altitude e potência alinhados ao vetor do W'bal.

    O W'bal tem um valor por segundo de cada segmento, na ordem dos segmentos;
    estes vetores seguem exatamente a mesma ordem e o mesmo tamanho.

    Args:
        series: série segmentada da atividade.

    Returns:
        Dicionário com `time_s`, `distance_m`, `altitude_m` e `power_w`.
    """
    if not series.segments:
        empty = np.array([], dtype=float)
        return {"time_s": empty, "distance_m": empty, "altitude_m": empty, "power_w": empty}

    time_s = np.concatenate(
        [s.start_time_s + np.arange(len(s)) for s in series.segments]
    ).astype(float)
    return {
        "time_s": time_s,
        "distance_m": series.concat("distance"),
        "altitude_m": series.concat("altitude"),
        "power_w": series.concat("power"),
    }


def decimate_keep_minimum(balance: list[float], target: int) -> list[int]:
    """Índices que reduzem a série a `target` pontos preservando os fundos.

    Args:
        balance: W'bal em joules, um valor por segundo.
        target: número máximo de pontos.

    Returns:
        Índices em ordem crescente — o de menor W' em cada balde.
    """
    n = len(balance)
    if n <= target:
        return list(range(n))
    values = np.asarray(balance, dtype=float)
    edges = np.linspace(0, n, target + 1).astype(int)
    return [
        int(lo + np.argmin(values[lo:hi]))
        for lo, hi in pairwise(edges)
        if hi > lo
    ]


def terrain_points(
    balance: list[float],
    channels: dict[str, np.ndarray],
    target: int,
) -> list[dict]:
    """Série decimada com W', tempo, distância, altitude e potência por ponto.

    Args:
        balance: W'bal em joules.
        channels: saída de `aligned_channels`.
        target: número máximo de pontos.

    Returns:
        Lista de dicionários `t`, `km`, `alt`, `kj`, `w` (nulos quando o canal
        não foi gravado).
    """
    def pick(name: str, index: int, digits: int, scale: float = 1.0):
        values = channels[name]
        if index >= len(values) or not np.isfinite(values[index]):
            return None
        return round(float(values[index]) / scale, digits)

    return [
        {
            "t": int(channels["time_s"][i]),
            "km": pick("distance_m", i, 2, 1000.0),
            "alt": pick("altitude_m", i, 1),
            "kj": round(balance[i] / 1000, 2),
            "w": pick("power_w", i, 0),
        }
        for i in decimate_keep_minimum(balance, target)
    ]


def depletion_episodes(
    balance: list[float],
    channels: dict[str, np.ndarray],
    w_prime_j: float,
    fraction: float = DEPLETED_FRACTION,
) -> list[DepletionEpisode]:
    """Trechos em que o W' ficou abaixo de `fraction` da reserva.

    Para cada um, descreve o terreno dos `LEAD_IN_S` segundos anteriores ao
    fundo — é a rampa (ou a perseguição no plano) que esvaziou o tanque.

    Args:
        balance: W'bal em joules, um valor por segundo.
        channels: saída de `aligned_channels`.
        w_prime_j: W' total, em joules.
        fraction: fração do W' abaixo da qual o tanque está na reserva.

    Returns:
        Episódios em ordem cronológica.
    """
    if not balance or w_prime_j <= 0:
        return []

    values = np.asarray(balance, dtype=float)
    time_s = channels["time_s"]
    below = values < w_prime_j * fraction

    runs: list[list[int]] = []
    index = 0
    while index < len(values):
        if not below[index]:
            index += 1
            continue
        start = index
        while index < len(values) and below[index]:
            index += 1
        end = index - 1
        if runs and time_s[start] - time_s[runs[-1][1]] <= MERGE_GAP_S:
            runs[-1][1] = end
        else:
            runs.append([start, end])

    episodes = []
    for start, end in runs:
        if time_s[end] - time_s[start] + 1 < MIN_EPISODE_S:
            continue
        low = start + int(np.argmin(values[start : end + 1]))
        episodes.append(_describe(values, channels, start, end, low, w_prime_j))
    return episodes


def _describe(
    values: np.ndarray,
    channels: dict[str, np.ndarray],
    start: int,
    end: int,
    low: int,
    w_prime_j: float,
) -> DepletionEpisode:
    """Monta o episódio com distância, potência e o terreno de aproximação."""
    time_s = channels["time_s"]
    distance = channels["distance_m"]
    altitude = channels["altitude_m"]
    power = channels["power_w"]

    lead_from = int(np.searchsorted(time_s, time_s[low] - LEAD_IN_S))
    window = altitude[lead_from : low + 1]
    gain = None
    grade = None
    if np.isfinite(window).sum() >= 2 and np.isfinite(altitude[low]):
        # A inclinação se mede a partir do pé da rampa (o ponto mais baixo da
        # aproximação), não do começo da janela: dez minutos de plano antes de
        # quatro de subida diluiriam 6% em 2% e a subida viraria "plano".
        # Último ponto no fundo (±1 m), não o primeiro: num plano antes da
        # rampa, o primeiro mínimo fica lá no começo da janela.
        at_bottom = np.flatnonzero(window <= np.nanmin(window) + 1.0)
        foot = lead_from + int(at_bottom[-1])
        gain = round(float(altitude[low] - altitude[foot]), 0)
        origin = foot if gain >= MIN_CLIMB_GAIN_M else lead_from
        run_m = _finite_diff(distance, origin, low)
        if run_m and run_m > 50 and np.isfinite(altitude[origin]):
            grade = round(float((altitude[low] - altitude[origin]) / run_m * 100), 1)

    if grade is None:
        terrain = "sem altitude"
    elif grade >= CLIMB_GRADE_PCT:
        terrain = "subida"
    elif grade <= -CLIMB_GRADE_PCT:
        terrain = "descida"
    else:
        terrain = "plano"

    watts = power[start : end + 1]
    watts = watts[np.isfinite(watts)]

    return DepletionEpisode(
        start_s=int(time_s[start]),
        end_s=int(time_s[end]),
        min_s=int(time_s[low]),
        min_pct=round(float(values[low] / w_prime_j * 100), 1),
        start_km=_km(distance, start),
        end_km=_km(distance, end),
        avg_power_w=round(float(watts.mean()), 0) if watts.size else None,
        lead_gain_m=gain,
        lead_grade_pct=grade,
        terrain=terrain,
    )


def _km(distance: np.ndarray, index: int) -> float | None:
    value = distance[index] if index < len(distance) else np.nan
    return round(float(value) / 1000, 2) if np.isfinite(value) else None


def _finite_diff(values: np.ndarray, start: int, end: int) -> float | None:
    a, b = values[start], values[end]
    return float(b - a) if np.isfinite(a) and np.isfinite(b) else None
