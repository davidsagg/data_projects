"""
W'bal — balanço da reserva anaeróbica ao longo de uma atividade.

Referência: Skiba et al. (2012), "Modeling the Expenditure and Reconstitution of
Work Capacity above Critical Power"; forma diferencial de Froncioni/Skiba (2014).

Acima da potência crítica o atleta consome W' na razão exata do excedente —
essa parte é simples e todo mundo implementa igual. A diferença está na
**recuperação**: abaixo do CP o W' não volta linearmente, mas de forma
exponencial, com uma constante de tempo τ que depende de quão abaixo do CP o
atleta pedala. Recuperar a 100 W abaixo do CP repõe muito mais rápido que a
10 W abaixo, e a versão linear anterior (50% fixos da diferença) errava os dois
extremos: repunha rápido demais na recuperação leve e devagar demais na parada.

    τ = 546 · e^(−0,01 · DCP) + 316,  onde DCP = CP − potência média
                                      dos trechos abaixo do CP

**Pausas.** A série é percorrida por segmento contínuo. Na lacuna entre dois
segmentos o atleta estava parado — recuperando — então o modelo aplica a mesma
exponencial pela duração da pausa, em vez de ignorá-la e retomar o balanço como
se o tempo não tivesse passado.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from analytics.timeseries import ActivitySeries

# Coeficientes do ajuste de Skiba (2012) para a constante de tempo da reposição.
TAU_SCALE = 546.0
TAU_DECAY = 0.01
TAU_OFFSET = 316.0

# Piso para τ. Um DCP enorme (parado com CP alto) levaria τ perto de 316 s, mas
# valores muito baixos tornariam a reposição instantânea e irreal.
MIN_TAU_S = 60.0


@dataclass(frozen=True)
class WPrimeResult:
    """Resultado do balanço de W' de uma atividade."""

    balance_j: list[float]
    w_prime_j: float
    cp_w: float
    tau_s: float

    @property
    def min_balance_j(self) -> float:
        """Menor balanço atingido — o fundo do tanque."""
        return min(self.balance_j) if self.balance_j else self.w_prime_j

    @property
    def depletion_pct(self) -> float:
        """Percentual de W' consumido no ponto mais profundo."""
        if self.w_prime_j <= 0:
            return 0.0
        return round((1 - self.min_balance_j / self.w_prime_j) * 100, 1)

    @property
    def matches_burned(self) -> int:
        """Quantas vezes o atleta desceu abaixo de 50% da reserva e voltou.

        É a leitura prática do gráfico: cada descida funda é um "fósforo"
        queimado, e o número deles explica por que a pernas acabam antes do
        esperado numa prova com muitos ataques.
        """
        if self.w_prime_j <= 0:
            return 0
        threshold = self.w_prime_j * 0.5
        count, below = 0, False
        for value in self.balance_j:
            if value < threshold and not below:
                count += 1
                below = True
            elif value >= threshold * 1.1:
                below = False
        return count


def compute_tau(power: np.ndarray, cp_w: float) -> float:
    """Calcula a constante de tempo da reposição de W'.

    Args:
        power: potências da atividade, em watts, sem NaN.
        cp_w: potência crítica do atleta.

    Returns:
        τ em segundos.
    """
    below = power[power < cp_w]
    # Sem nenhum trecho de recuperação, assume-se o pior caso: DCP nulo, que
    # produz o τ mais longo e portanto a reposição mais conservadora.
    dcp = float(cp_w - below.mean()) if below.size else 0.0
    tau = TAU_SCALE * math.exp(-TAU_DECAY * dcp) + TAU_OFFSET
    return max(tau, MIN_TAU_S)


class WPrimeModel:
    """Modela a depleção e a reposição do W' do atleta."""

    def __init__(self, w_prime_joules: float, cp: float) -> None:
        """Args:
            w_prime_joules: reserva anaeróbica total, em joules.
            cp: potência crítica, em watts.
        """
        self.wp = float(w_prime_joules)
        self.cp = float(cp)

    def compute(self, series: ActivitySeries) -> WPrimeResult:
        """Calcula o balanço de W' de uma atividade, respeitando as pausas.

        Args:
            series: série já segmentada da atividade.

        Returns:
            WPrimeResult com a curva de balanço e suas estatísticas.
        """
        segments = [np.nan_to_num(s, nan=0.0) for s in series.channel("power")]
        if not segments:
            return WPrimeResult([], self.wp, self.cp, MIN_TAU_S)

        tau = compute_tau(np.concatenate(segments), self.cp)

        balance: list[float] = []
        current = self.wp
        previous_end_s: int | None = None

        for segment, raw in zip(segments, series.segments):
            if previous_end_s is not None:
                gap_s = max(raw.start_time_s - previous_end_s, 0)
                current = self._recover(current, gap_s, tau)

            for watts in segment:
                if watts > self.cp:
                    current = max(current - (watts - self.cp), 0.0)
                else:
                    current = self._recover(current, 1, tau)
                balance.append(current)

            previous_end_s = raw.start_time_s + len(segment)

        return WPrimeResult(balance, self.wp, self.cp, tau)

    def _recover(self, current: float, seconds: float, tau: float) -> float:
        """Repõe W' exponencialmente na direção da reserva total."""
        if seconds <= 0:
            return current
        deficit = self.wp - current
        return self.wp - deficit * math.exp(-seconds / tau)

    def calculate_balance(self, streams: list) -> list[float]:
        """Calcula o balanço a partir de uma lista crua de `ActivityStream`.

        Mantido para uso fora do caminho de `ActivitySeries` (testes e scripts
        pontuais). Sem a segmentação, as pausas não são tratadas — prefira
        `compute` sempre que a série estiver disponível.

        Args:
            streams: pontos com o campo `power_w`.

        Returns:
            Lista de balanços de W' em joules, um por ponto.
        """
        tau = compute_tau(
            np.array([s.power_w for s in streams if s.power_w is not None], dtype=float),
            self.cp,
        )

        balance: list[float] = []
        current = self.wp
        for point in streams:
            if point.power_w is None:
                balance.append(current)
                continue
            if point.power_w > self.cp:
                current = max(current - (point.power_w - self.cp), 0.0)
            else:
                current = self._recover(current, 1, tau)
            balance.append(current)
        return balance
