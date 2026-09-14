"""
Correlação entre recuperação e performance (US-12).

Um coeficiente de correlação isolado é fácil de interpretar mal: com sete pares,
um r de 0,6 é ruído com boa aparência. Por isso toda correlação aqui vem
acompanhada do número de pares e do valor-p, e a interpretação textual só
afirma relação quando o resultado é estatisticamente significativo.

**Correlação não é causalidade, e aqui menos ainda.** Dormir bem e render bem
compartilham causas comuns — fim de semana, ausência de estresse, ausência de
doença. O resultado serve para levantar hipótese, não para provar mecanismo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Optional

# Abaixo disso não há amostra para afirmar nada.
MIN_PAIRS = 7

# Limite convencional de significância.
ALPHA = 0.05

# Faixas de força de associação (valores absolutos de r).
STRENGTH_BANDS = (
    (0.7, "forte"),
    (0.5, "moderada"),
    (0.3, "fraca"),
)


@dataclass(frozen=True)
class Correlation:
    """Resultado de uma correlação entre duas séries emparelhadas."""

    x_label: str
    y_label: str
    r: float
    n: int
    p_value: float

    @property
    def significant(self) -> bool:
        """Indica se o resultado passa do limite convencional de significância."""
        return self.p_value < ALPHA

    @property
    def strength(self) -> str:
        """Força da associação, em palavras."""
        magnitude = abs(self.r)
        for threshold, label in STRENGTH_BANDS:
            if magnitude >= threshold:
                return label
        return "desprezível"

    @property
    def direction(self) -> str:
        """Sentido da associação."""
        return "positiva" if self.r > 0 else "negativa"

    @property
    def interpretation(self) -> str:
        """Frase que resume o achado sem exagerar o que ele suporta."""
        if not self.significant:
            return (
                f"Sem associação estatisticamente detectável em {self.n} "
                f"observações (p = {self.p_value:.3f})."
            )
        return (
            f"Associação {self.strength} e {self.direction} "
            f"(r = {self.r:.2f}, n = {self.n}, p = {self.p_value:.3f}). "
            "Associação não implica causa."
        )


class SleepCorrelator:
    """Correlaciona métricas de recuperação com métricas de performance."""

    MIN = MIN_PAIRS

    def correlate(self, data: list[tuple]) -> Optional[float]:
        """Coeficiente de Pearson entre pares (x, y).

        Args:
            data: lista de pares numéricos.

        Returns:
            Coeficiente entre -1 e 1, ou None se há menos de `MIN` pares.
        """
        if len(data) < self.MIN:
            return None

        x = [d[0] for d in data]
        y = [d[1] for d in data]
        n = len(x)
        mean_x, mean_y = sum(x) / n, sum(y) / n

        numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
        denominator = math.sqrt(
            sum((a - mean_x) ** 2 for a in x) * sum((b - mean_y) ** 2 for b in y)
        )
        return round(numerator / denominator, 4) if denominator > 0 else 0.0

    def analyze(
        self,
        data: list[tuple],
        x_label: str,
        y_label: str,
    ) -> Optional[Correlation]:
        """Correlaciona e devolve o resultado com `n` e valor-p.

        Args:
            data: lista de pares numéricos.
            x_label: nome da variável de recuperação.
            y_label: nome da variável de performance.

        Returns:
            Correlation, ou None se há pares insuficientes.
        """
        r = self.correlate(data)
        if r is None:
            return None

        return Correlation(
            x_label=x_label,
            y_label=y_label,
            r=r,
            n=len(data),
            p_value=_pearson_p_value(r, len(data)),
        )


def _pearson_p_value(r: float, n: int) -> float:
    """Valor-p bilateral do coeficiente de Pearson.

    Args:
        r: coeficiente de correlação.
        n: número de pares.

    Returns:
        Probabilidade de observar esse r por acaso, sob a hipótese nula.
    """
    if n <= 2 or abs(r) >= 1.0:
        return 0.0

    # Estatística t de Student com n-2 graus de liberdade.
    t = abs(r) * math.sqrt((n - 2) / (1 - r**2))

    from scipy import stats

    return round(float(2 * stats.t.sf(t, df=n - 2)), 6)


def pair_recovery_with_performance(
    health: list[dict],
    activities: list[dict],
    recovery_key: str,
    performance_key: str,
) -> list[tuple[float, float, date]]:
    """Emparelha a recuperação de um dia com o treino do mesmo dia.

    O sono medido pelo Garmin para a data D é a **noite que termina** em D, ou
    seja, precede o treino de D — por isso o pareamento é pela mesma data e não
    por deslocamento de um dia.

    Quando há mais de um treino no dia, vence o de maior TSS: é a sessão que
    a recuperação daquela noite de fato sustentou.

    Args:
        health: registros diários de saúde, cada um com `date`.
        activities: atividades, cada uma com `date`.
        recovery_key: campo de recuperação (ex.: `sleep_hours`).
        performance_key: campo de performance (ex.: `normalized_power_w`).

    Returns:
        Trios (recuperação, performance, data), em ordem cronológica.
    """
    best_by_date: dict = {}
    for activity in activities:
        value = activity.get(performance_key)
        if value is None:
            continue
        current = best_by_date.get(activity["date"])
        if current is None or (activity.get("tss") or 0) > (current.get("tss") or 0):
            best_by_date[activity["date"]] = activity

    pairs: list[tuple[float, float, date]] = []
    for record in health:
        recovery = record.get(recovery_key)
        activity = best_by_date.get(record["date"])
        if recovery is None or activity is None:
            continue
        pairs.append((float(recovery), float(activity[performance_key]), record["date"]))

    return sorted(pairs, key=lambda p: p[2])
