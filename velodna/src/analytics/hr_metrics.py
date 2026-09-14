"""
Métricas de carga baseadas em frequência cardíaca.

Mais da metade do histórico do VeloDNA é anterior ao medidor de potência, e a
FC cobre praticamente todas as atividades. Sem uma carga derivada de FC, esses
anos entrariam no PMC como zero — o que apagaria a base aeróbica construída e
tornaria o CTL histórico inútil.

TRIMP segue Banister: a ponderação exponencial faz um minuto em Z5 valer muito
mais que um minuto em Z1. HRSS reescala o TRIMP de modo que uma hora no limiar
valha 100 — a mesma unidade do TSS de potência, o que permite somar os dois na
mesma série de carga.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from analytics.timeseries import ActivitySeries

# Constantes de Banister. O fator masculino (1,92) é o usado por padrão;
# para atletas do sexo feminino a literatura usa 1,67.
TRIMP_FACTOR = 0.64
TRIMP_EXPONENT = 1.92

# Fração do intervalo de reserva cardíaca correspondente ao limiar, usada como
# âncora do HRSS quando o LTHR do atleta não é conhecido.
DEFAULT_THRESHOLD_RESERVE_RATIO = 0.85


@dataclass(frozen=True)
class HeartRateProfile:
    """Parâmetros do atleta necessários para converter FC em carga."""

    max_hr_bpm: float
    resting_hr_bpm: float
    threshold_hr_bpm: float | None = None

    def reserve_ratio(self, hr_bpm: float) -> float:
        """Converte uma FC absoluta em fração da reserva cardíaca.

        Args:
            hr_bpm: frequência cardíaca em batimentos por minuto.

        Returns:
            Fração entre 0 e 1 da reserva (Karvonen), truncada nas bordas.
        """
        reserve = self.max_hr_bpm - self.resting_hr_bpm
        if reserve <= 0:
            return 0.0
        return float(np.clip((hr_bpm - self.resting_hr_bpm) / reserve, 0.0, 1.0))

    @property
    def threshold_reserve_ratio(self) -> float:
        """Fração da reserva cardíaca correspondente ao limiar."""
        if self.threshold_hr_bpm is None:
            return DEFAULT_THRESHOLD_RESERVE_RATIO
        return self.reserve_ratio(self.threshold_hr_bpm)


def trimp(duration_s: float, reserve_ratio: float) -> float:
    """Calcula o TRIMP de Banister para um trecho de esforço.

    Args:
        duration_s: duração do trecho em segundos.
        reserve_ratio: fração média da reserva cardíaca no trecho.

    Returns:
        TRIMP acumulado no trecho.
    """
    minutes = duration_s / 60.0
    return float(
        minutes
        * reserve_ratio
        * TRIMP_FACTOR
        * np.exp(TRIMP_EXPONENT * reserve_ratio)
    )


def compute_hrss(series: ActivitySeries, profile: HeartRateProfile) -> float | None:
    """Calcula o HRSS de uma atividade a partir da série de FC.

    O TRIMP é acumulado amostra a amostra — usar a FC média da atividade
    subestimaria treinos intervalados, já que a ponderação é exponencial.

    Args:
        series: série já segmentada da atividade.
        profile: parâmetros cardíacos do atleta.

    Returns:
        HRSS na mesma escala do TSS, ou None se não há dados de FC.
    """
    if not series.has_data("hr"):
        return None

    hr = series.concat("hr")
    hr = hr[np.isfinite(hr)]
    if hr.size == 0:
        return None

    reserve = profile.max_hr_bpm - profile.resting_hr_bpm
    if reserve <= 0:
        return None

    ratios = np.clip((hr - profile.resting_hr_bpm) / reserve, 0.0, 1.0)

    # Cada amostra vale 1 s na grade de 1 Hz.
    activity_trimp = float(
        np.sum(
            (1 / 60.0)
            * ratios
            * TRIMP_FACTOR
            * np.exp(TRIMP_EXPONENT * ratios)
        )
    )

    threshold_trimp = trimp(3600, profile.threshold_reserve_ratio)
    if threshold_trimp <= 0:
        return None

    return round(activity_trimp / threshold_trimp * 100, 1)


def decoupling_pct(series: ActivitySeries) -> float | None:
    """Calcula o desacoplamento aeróbico (Pw:HR) entre as metades do treino.

    Um valor acima de ~5% indica que a FC subiu para sustentar a mesma potência
    — sinal de deriva cardíaca e de resistência aeróbica insuficiente para a
    duração do esforço.

    Args:
        series: série já segmentada da atividade.

    Returns:
        Variação percentual da razão potência/FC da primeira para a segunda
        metade, ou None se faltam potência ou FC.
    """
    if not (series.has_data("power") and series.has_data("hr")):
        return None

    power = series.concat("power")
    hr = series.concat("hr")
    usable = np.isfinite(power) & np.isfinite(hr) & (hr > 0)
    if usable.sum() < 2:
        return None

    power, hr = power[usable], hr[usable]
    middle = power.size // 2
    if middle == 0:
        return None

    first = _power_hr_ratio(power[:middle], hr[:middle])
    second = _power_hr_ratio(power[middle:], hr[middle:])
    if first is None or second is None or first == 0:
        return None

    return round((first - second) / first * 100, 2)


def calibrate_threshold_ratio(
    paired_loads: list[tuple[float, float]],
    profile: HeartRateProfile,
) -> float | None:
    """Ajusta a âncora de limiar para que HRSS e TSS de potência coincidam.

    Nas atividades que têm potência e FC, o TSS por potência é a referência.
    Se o HRSS é sistematicamente menor, a âncora de limiar está alta demais.
    Como o HRSS é inversamente proporcional ao TRIMP de limiar, basta escalar a
    âncora pela razão mediana observada e inverter a fórmula de Banister.

    Args:
        paired_loads: pares (tss_por_potência, hrss) das atividades com ambos.
        profile: perfil cardíaco usado para gerar os HRSS informados.

    Returns:
        Nova fração da reserva cardíaca correspondente ao limiar, ou None se
        não há pares suficientes para calibrar.
    """
    ratios = [
        hrss / tss
        for tss, hrss in paired_loads
        if tss and tss > 10 and hrss is not None
    ]
    if len(ratios) < 30:
        return None

    median_ratio = float(np.median(ratios))
    if median_ratio <= 0:
        return None

    target_trimp = trimp(3600, profile.threshold_reserve_ratio) * median_ratio
    return _invert_trimp(target_trimp)


def _invert_trimp(target_trimp: float, hours: float = 1.0) -> float | None:
    """Resolve a fração de reserva que produz um dado TRIMP em uma hora.

    A função de Banister é monotônica em `reserve_ratio`, então uma busca
    binária converge sem risco de mínimo local.

    Args:
        target_trimp: TRIMP desejado para o período.
        hours: duração de referência, em horas.

    Returns:
        Fração da reserva cardíaca entre 0 e 1, ou None se o alvo é inatingível.
    """
    duration_s = hours * 3600
    low, high = 0.01, 1.0
    if trimp(duration_s, high) < target_trimp:
        return None

    for _ in range(60):
        mid = (low + high) / 2
        if trimp(duration_s, mid) < target_trimp:
            low = mid
        else:
            high = mid
    return round((low + high) / 2, 4)


def _power_hr_ratio(power: np.ndarray, hr: np.ndarray) -> float | None:
    """Razão entre potência média e FC média de um trecho.

    Args:
        power: amostras de potência.
        hr: amostras de FC, alinhadas a `power`.

    Returns:
        Razão potência/FC, ou None se a FC média é nula.
    """
    mean_hr = float(hr.mean())
    if mean_hr <= 0:
        return None
    return float(power.mean()) / mean_hr
