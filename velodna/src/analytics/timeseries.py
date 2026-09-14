"""
Camada de séries temporais — base de todas as métricas derivadas de stream.

Arquivos `.fit` não são séries contínuas: gravação inteligente pula amostras,
o ciclocomputador pausa em semáforos e há falhas de sensor. Tratar isso como um
vetor contíguo (ou preencher as lacunas com 0 W) distorce qualquer janela móvel
— uma parada de 10 minutos vira 600 amostras de potência zero no meio de um
esforço.

Aqui a atividade é quebrada em **segmentos contínuos**: trechos separados por
pausas, cada um reamostrado a 1 Hz. Toda janela móvel (NP, MMP, decoupling)
roda dentro de um segmento e nunca atravessa uma pausa.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Intervalo acima do qual a lacuna deixa de ser falha de gravação e passa a ser
# pausa real. Gravação inteligente da Garmin chega a espaçar ~7 s em trechos
# de ritmo constante, então o corte fica acima disso.
PAUSE_GAP_S = 10

CHANNELS = ("power", "hr", "cadence", "speed", "altitude", "distance")

# Limites fisiológicos usados para descartar artefato de sensor. O histórico tem
# picos de 3609 W e 239 bpm — valores que nenhum humano produz e que, sem filtro,
# viram "recordes" na curva de potência e na FC máxima estimada.
PLAUSIBLE_RANGE = {
    "power": (0.0, 2500.0),
    "hr": (25.0, 220.0),
    "cadence": (0.0, 200.0),
    "speed": (0.0, 40.0),
}

_COLUMN_BY_CHANNEL = {
    "power": "power_w",
    "hr": "hr_bpm",
    "cadence": "cadence_rpm",
    "speed": "speed_ms",
    "altitude": "altitude_m",
    "distance": "distance_m",
}


@dataclass(frozen=True)
class Segment:
    """Trecho contínuo de gravação, reamostrado a 1 Hz."""

    start_time_s: int
    channels: dict[str, np.ndarray]

    def __len__(self) -> int:
        return len(next(iter(self.channels.values())))


class ActivitySeries:
    """Série temporal de uma atividade, já segmentada por pausas."""

    def __init__(self, activity_id: str, segments: list[Segment]) -> None:
        """Args:
            activity_id: UUID da atividade.
            segments: trechos contínuos, em ordem cronológica.
        """
        self.activity_id = activity_id
        self.segments = segments

    @property
    def moving_time_s(self) -> int:
        """Soma da duração dos segmentos, excluindo as pausas."""
        return sum(len(s) for s in self.segments)

    @property
    def elapsed_time_s(self) -> int:
        """Tempo do início ao fim da atividade, pausas incluídas."""
        if not self.segments:
            return 0
        last = self.segments[-1]
        return last.start_time_s + len(last) - 1

    def channel(self, name: str) -> list[np.ndarray]:
        """Retorna o canal por segmento, preservando as fronteiras de pausa.

        Um canal ausente equivale a um canal sem medida: devolve NaN no
        comprimento do segmento, para que quem consome não precise distinguir
        "sensor não existia" de "sensor não mediu".

        Args:
            name: um de `CHANNELS`.

        Returns:
            Lista de arrays, um por segmento.
        """
        return [
            segment.channels.get(name, np.full(len(segment), np.nan))
            for segment in self.segments
        ]

    def concat(self, name: str) -> np.ndarray:
        """Retorna o canal concatenado, como se as pausas não existissem.

        Use apenas para estatísticas sem noção de vizinhança (média, máximo,
        histograma de zonas). Para janelas móveis, use `channel`.

        Args:
            name: um de `CHANNELS`.

        Returns:
            Array 1-D com todas as amostras do canal.
        """
        parts = self.channel(name)
        return np.concatenate(parts) if parts else np.array([])

    def has_data(self, name: str) -> bool:
        """Indica se o canal tem ao menos uma amostra válida.

        Args:
            name: um de `CHANNELS`.

        Returns:
            True se existe algum valor não-NaN.
        """
        values = self.concat(name)
        return values.size > 0 and bool(np.isfinite(values).any())


def load_series(
    conn,
    activity_id: str,
    pause_gap_s: int = PAUSE_GAP_S,
) -> ActivitySeries:
    """Carrega os streams de uma atividade e os organiza em segmentos contínuos.

    Args:
        conn: conexão DuckDB.
        activity_id: UUID da atividade.
        pause_gap_s: lacuna, em segundos, a partir da qual há pausa.

    Returns:
        ActivitySeries com os segmentos reamostrados a 1 Hz. Vazia se a
        atividade não tem streams.
    """
    columns = ", ".join(_COLUMN_BY_CHANNEL[c] for c in CHANNELS)
    frame = conn.execute(
        f"SELECT time_s, {columns} FROM activity_streams "
        "WHERE activity_id = ? ORDER BY time_s",
        [activity_id],
    ).df()

    if frame.empty:
        return ActivitySeries(activity_id, [])

    times = frame["time_s"].to_numpy(dtype=np.int64)
    raw = {
        channel: _drop_implausible(
            frame[_COLUMN_BY_CHANNEL[channel]].to_numpy(dtype=np.float64), channel
        )
        for channel in CHANNELS
    }

    return ActivitySeries(
        activity_id,
        [
            _build_segment(times[lo:hi], {c: raw[c][lo:hi] for c in CHANNELS})
            for lo, hi in _segment_bounds(times, pause_gap_s)
        ],
    )


def _drop_implausible(values: np.ndarray, channel: str) -> np.ndarray:
    """Substitui por NaN os valores fora da faixa fisiológica do canal.

    Marcar como NaN (e não zerar) mantém a distinção entre "sensor falhou" e
    "atleta parou de pedalar"; a reamostragem interpola sobre a falha.

    Args:
        values: amostras brutas do canal.
        channel: nome do canal em `CHANNELS`.

    Returns:
        Cópia do array com os artefatos marcados como NaN.
    """
    limits = PLAUSIBLE_RANGE.get(channel)
    if limits is None:
        return values

    low, high = limits
    cleaned = values.copy()
    cleaned[(cleaned < low) | (cleaned > high)] = np.nan
    return cleaned


def _segment_bounds(times: np.ndarray, pause_gap_s: int) -> list[tuple[int, int]]:
    """Localiza os trechos contínuos de uma série de tempos.

    Args:
        times: tempos das amostras, em segundos e ordenados.
        pause_gap_s: lacuna mínima que caracteriza uma pausa.

    Returns:
        Lista de pares (início, fim) como índices semiabertos.
    """
    if times.size == 0:
        return []

    breaks = np.flatnonzero(np.diff(times) > pause_gap_s) + 1
    edges = [0, *breaks.tolist(), times.size]
    return [
        (lo, hi)
        for lo, hi in zip(edges, edges[1:])
        if hi > lo
    ]


def _build_segment(times: np.ndarray, channels: dict[str, np.ndarray]) -> Segment:
    """Reamostra um trecho contínuo para uma grade de 1 Hz.

    Lacunas curtas (falhas de gravação dentro do trecho) são interpoladas
    linearmente; amostras ausentes do sensor permanecem NaN para que os
    cálculos possam distinguir "não medido" de "zero".

    Args:
        times: tempos das amostras do trecho.
        channels: valores brutos por canal, alinhados a `times`.

    Returns:
        Segment com todos os canais na grade de 1 Hz.
    """
    start = int(times[0])
    grid = np.arange(start, int(times[-1]) + 1)

    resampled: dict[str, np.ndarray] = {}
    for name, values in channels.items():
        valid = np.isfinite(values)
        if not valid.any():
            resampled[name] = np.full(grid.size, np.nan)
            continue
        # np.interp estende as bordas com o primeiro/último valor válido, o que
        # é o comportamento desejado para falhas nas pontas do trecho.
        resampled[name] = np.interp(grid, times[valid], values[valid])

    return Segment(start_time_s=start, channels=resampled)
