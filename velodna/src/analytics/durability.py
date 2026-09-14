"""
Durabilidade — o que sobra da potência depois do trabalho acumulado.

Referência: Maunder, Seiler et al. (2021), "The Importance of 'Durability'";
Allen & Coggan tratam o mesmo fenômeno como fadiga-resistência.

Duas pessoas com o mesmo FTP não são o mesmo ciclista. Um teste de 20 minutos
feito descansado mede o teto; o que decide um gran fondo é quanto desse teto
ainda existe depois de 2.000 kJ de trabalho. A curva de potência clássica ignora
isso por construção — ela pega o melhor esforço da atividade inteira, sem
perguntar em que ponto do treino ele aconteceu.

Aqui a atividade é cortada num limiar de trabalho acumulado e a mesma métrica é
medida dos dois lados. O sinal aparece de duas formas complementares:

- **Potência máxima média** por duração, antes e depois do corte. Direto, mas
  só existe se o atleta tiver feito esforços comparáveis nas duas metades.
- **Efficiency Factor** (NP ÷ FC) antes e depois. Funciona em pedal constante,
  onde não há esforço máximo nenhum — é a leitura que serve para os treinos
  longos de base, que são a maioria.

O trabalho acumulado vem da integral da potência no tempo, contada apenas dentro
dos segmentos contínuos: parar 20 minutos num café não acumula quilojoule.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from analytics.power_metrics import rolling_mean
from analytics.timeseries import ActivitySeries

# Limiar padrão de corte. 1.000 kJ é onde a queda começa a aparecer para a
# maioria dos amadores — abaixo disso o atleta ainda não fadigou o bastante
# para a medida dizer alguma coisa.
DEFAULT_KJ_THRESHOLD = 1000.0

# Durações comparadas dos dois lados do corte.
DEFAULT_DURATIONS = (60, 300, 600, 1200)

# Sem pelo menos este tempo de cada lado, a comparação não se sustenta.
MIN_SIDE_DURATION_S = 600


@dataclass(frozen=True)
class DurabilityPoint:
    """Comparação de uma duração antes e depois do limiar de trabalho."""

    duration_s: int
    before_w: float
    after_w: float

    @property
    def change_pct(self) -> float:
        """Variação percentual; negativa quando a potência cai."""
        if self.before_w <= 0:
            return 0.0
        return round((self.after_w / self.before_w - 1) * 100, 1)


@dataclass(frozen=True)
class DurabilityResult:
    """Resultado da análise de durabilidade de uma atividade."""

    kj_threshold: float
    total_kj: float
    split_time_s: int | None
    points: list[DurabilityPoint] = field(default_factory=list)
    ef_before: float | None = None
    ef_after: float | None = None

    @property
    def ef_change_pct(self) -> float | None:
        """Queda do Efficiency Factor depois do limiar, em percentual."""
        if not self.ef_before or not self.ef_after:
            return None
        return round((self.ef_after / self.ef_before - 1) * 100, 1)

    @property
    def is_conclusive(self) -> bool:
        """Indica se houve trabalho suficiente para a comparação valer."""
        return self.split_time_s is not None and (
            bool(self.points) or self.ef_change_pct is not None
        )

    @property
    def verdict(self) -> str:
        """Leitura qualitativa da queda, para exibição direta."""
        if not self.is_conclusive:
            return "inconclusivo"
        decline = self.ef_change_pct
        if decline is None:
            decline = min((p.change_pct for p in self.points), default=0.0)
        if decline >= -3:
            return "excelente"
        if decline >= -8:
            return "boa"
        if decline >= -15:
            return "moderada"
        return "baixa"


def cumulative_work_kj(series: ActivitySeries) -> np.ndarray:
    """Calcula o trabalho acumulado, segundo a segundo, em quilojoules.

    A potência é medida em watts (joules por segundo), então a 1 Hz cada amostra
    contribui com seu próprio valor em joules. As pausas não entram: a soma é
    contínua dentro de cada segmento e apenas carrega o total entre eles.

    Args:
        series: série já segmentada da atividade.

    Returns:
        Array com o acumulado em kJ, alinhado às amostras de potência
        concatenadas dos segmentos.
    """
    if not series.has_data("power"):
        return np.array([])

    parts: list[np.ndarray] = []
    carried = 0.0
    for power in series.channel("power"):
        clean = np.nan_to_num(power, nan=0.0)
        if clean.size == 0:
            continue
        accumulated = np.cumsum(clean) / 1000.0 + carried
        parts.append(accumulated)
        carried = float(accumulated[-1])
    return np.concatenate(parts) if parts else np.array([])


def compute_durability(
    series: ActivitySeries,
    kj_threshold: float = DEFAULT_KJ_THRESHOLD,
    durations: tuple[int, ...] = DEFAULT_DURATIONS,
) -> DurabilityResult:
    """Compara a capacidade do atleta antes e depois do trabalho acumulado.

    Args:
        series: série já segmentada da atividade.
        kj_threshold: trabalho acumulado que define o corte, em kJ.
        durations: durações a comparar dos dois lados.

    Returns:
        DurabilityResult; `is_conclusive` é falso quando a atividade não tem
        trabalho suficiente para a comparação significar algo.
    """
    if not series.has_data("power"):
        return DurabilityResult(kj_threshold, 0.0, None)

    work = cumulative_work_kj(series)
    if work.size == 0:
        return DurabilityResult(kj_threshold, 0.0, None)

    total_kj = round(float(work[-1]), 1)
    crossing = np.flatnonzero(work >= kj_threshold)

    if crossing.size == 0:
        return DurabilityResult(kj_threshold, total_kj, None)

    split = int(crossing[0])
    power = np.nan_to_num(series.concat("power"), nan=0.0)

    if split < MIN_SIDE_DURATION_S or power.size - split < MIN_SIDE_DURATION_S:
        return DurabilityResult(kj_threshold, total_kj, None)

    points = _compare_durations(power[:split], power[split:], durations)
    ef_before, ef_after = _compare_efficiency(series, split)

    return DurabilityResult(
        kj_threshold=kj_threshold,
        total_kj=total_kj,
        split_time_s=split,
        points=points,
        ef_before=ef_before,
        ef_after=ef_after,
    )


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _compare_durations(
    before: np.ndarray,
    after: np.ndarray,
    durations: tuple[int, ...],
) -> list[DurabilityPoint]:
    """Melhor esforço de cada duração dos dois lados do corte."""
    points: list[DurabilityPoint] = []
    for duration in durations:
        if before.size < duration or after.size < duration:
            continue
        best_before = rolling_mean(before, duration)
        best_after = rolling_mean(after, duration)
        if not best_before.size or not best_after.size:
            continue
        points.append(
            DurabilityPoint(
                duration_s=duration,
                before_w=round(float(best_before.max()), 1),
                after_w=round(float(best_after.max()), 1),
            )
        )
    return points


def _compare_efficiency(
    series: ActivitySeries, split: int
) -> tuple[float | None, float | None]:
    """Efficiency Factor (NP ÷ FC) antes e depois do corte."""
    if not series.has_data("hr"):
        return None, None

    power = np.nan_to_num(series.concat("power"), nan=0.0)
    hr = series.concat("hr")

    return (
        _efficiency_factor(power[:split], hr[:split]),
        _efficiency_factor(power[split:], hr[split:]),
    )


def _efficiency_factor(power: np.ndarray, hr: np.ndarray) -> float | None:
    """NP dividida pela FC média de um trecho."""
    if power.size < 30 or hr.size == 0 or not np.isfinite(hr).any():
        return None

    rolled = rolling_mean(power, 30)
    if not rolled.size:
        return None

    np_w = float(np.power(np.power(rolled, 4).mean(), 0.25))
    mean_hr = float(np.nanmean(hr))
    if mean_hr <= 0:
        return None
    return round(np_w / mean_hr, 3)
