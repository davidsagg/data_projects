"""
Modelo de Potência Crítica (CP) e capacidade anaeróbica (W').

O modelo hiperbólico de Monod & Scherrer descreve a relação entre potência
sustentável e duração:

    P(t) = W' / t + CP

CP é a assíntota — a potência teoricamente sustentável de forma indefinida.
W' é a energia disponível acima de CP, em joules: uma "bateria" que esvazia
quando se pedala acima do limiar e recarrega abaixo dele.

Na forma linear `P = W' · (1/t) + CP`, o ajuste vira uma regressão simples de
P contra 1/t: o coeficiente angular é W' e o intercepto é CP.

**Faixa de validade:** o modelo só vale entre ~2 e ~20 minutos. Abaixo disso a
potência é limitada pelo sistema neuromuscular, não pelo metabólico; acima, a
depleção de glicogênio e a deriva cardíaca derrubam a potência abaixo do que o
modelo prevê. Incluir um sprint de 5 s ou um esforço de 3 h distorce o ajuste.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Faixa em que a hipérbole descreve bem a fisiologia.
MIN_VALID_DURATION_S = 120
MAX_VALID_DURATION_S = 1200

# Mínimo de pontos para uma regressão com significado.
MIN_POINTS_FOR_FIT = 3

# A literatura situa o FTP entre 95% e 100% de CP. Para este atleta a razão é
# 1:1 — o CP de dois pontos dos testes de jan/2024 e jan/2026 deu 218,1 W contra
# os 218 e 217 W que ele reporta dos mesmos testes. Ajustar para 0,95 introduziria
# um viés de 10 W contra um valor medido.
FTP_FROM_CP = 1.00


@dataclass(frozen=True)
class CriticalPowerFit:
    """Resultado do ajuste do modelo de potência crítica."""

    cp_w: float
    w_prime_j: float
    r_squared: float | None
    n_points: int
    durations_s: tuple[int, ...]

    @property
    def ftp_w(self) -> float:
        """FTP derivado de CP."""
        return round(self.cp_w * FTP_FROM_CP, 1)

    @property
    def w_prime_kj(self) -> float:
        """W' expresso em quilojoules, unidade usual nos relatórios."""
        return round(self.w_prime_j / 1000, 2)

    def predict(self, duration_s: float) -> float:
        """Potência prevista para uma duração.

        Args:
            duration_s: duração do esforço em segundos.

        Returns:
            Potência média prevista, em watts.
        """
        return self.w_prime_j / duration_s + self.cp_w

    def time_to_exhaustion(self, power_w: float) -> float | None:
        """Tempo até a exaustão a uma potência acima de CP.

        Args:
            power_w: potência sustentada, em watts.

        Returns:
            Tempo em segundos, ou None se a potência está em CP ou abaixo —
            nesse caso o modelo não prevê exaustão.
        """
        if power_w <= self.cp_w:
            return None
        return self.w_prime_j / (power_w - self.cp_w)


def fit_two_point(
    short: tuple[int, float],
    long: tuple[int, float],
) -> CriticalPowerFit | None:
    """Ajusta CP e W' a partir de dois esforços máximos.

    É o protocolo clássico de dois pontos: um esforço curto e um longo, ambos
    máximos. Com apenas dois pontos não há resíduo, logo não há R².

    Args:
        short: par (duração_s, potência_w) do esforço curto.
        long: par (duração_s, potência_w) do esforço longo.

    Returns:
        CriticalPowerFit, ou None se as durações são iguais ou o resultado é
        fisiologicamente impossível (CP ou W' não positivos).
    """
    (t1, p1), (t2, p2) = short, long
    if t1 == t2:
        return None

    # De P = W'/t + CP em dois pontos: W' = (P1 - P2) / (1/t1 - 1/t2).
    w_prime = (p1 - p2) / (1 / t1 - 1 / t2)
    cp = p2 - w_prime / t2

    if cp <= 0 or w_prime <= 0:
        return None

    return CriticalPowerFit(
        cp_w=round(cp, 1),
        w_prime_j=round(w_prime, 1),
        r_squared=None,
        n_points=2,
        durations_s=(t1, t2),
    )


def fit_curve(curve: dict[int, float]) -> CriticalPowerFit | None:
    """Ajusta CP e W' por regressão linear sobre a curva de potência.

    Apenas as durações dentro da faixa de validade entram no ajuste.

    Args:
        curve: {duração_s: melhor_potência_w}.

    Returns:
        CriticalPowerFit, ou None se faltam pontos válidos ou o ajuste é
        fisiologicamente impossível.
    """
    points = sorted(
        (duration, power)
        for duration, power in curve.items()
        if MIN_VALID_DURATION_S <= duration <= MAX_VALID_DURATION_S and power > 0
    )
    if len(points) < MIN_POINTS_FOR_FIT:
        return None

    durations = np.array([p[0] for p in points], dtype=float)
    powers = np.array([p[1] for p in points], dtype=float)
    inverse_time = 1 / durations

    slope, intercept = np.polyfit(inverse_time, powers, 1)
    if intercept <= 0 or slope <= 0:
        return None

    predicted = slope * inverse_time + intercept
    residual = float(np.sum((powers - predicted) ** 2))
    total = float(np.sum((powers - powers.mean()) ** 2))
    r_squared = 1 - residual / total if total > 0 else None

    return CriticalPowerFit(
        cp_w=round(float(intercept), 1),
        w_prime_j=round(float(slope), 1),
        r_squared=round(r_squared, 4) if r_squared is not None else None,
        n_points=len(points),
        durations_s=tuple(int(d) for d in durations),
    )
