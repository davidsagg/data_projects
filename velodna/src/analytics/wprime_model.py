"""
W' Prime Model — modelo de balanço de energia anaeróbica.

Referência: Skiba et al., "Modeling the Expenditure and Reconstitution of Work Capacity".

Calcula o balanço de W' segundo a segundo a partir de streams de potência.
"""
from __future__ import annotations


class WPrimeModel:
    """Modela a depleção e recuperação do W' (capacidade anaeróbica) do atleta."""

    def __init__(self, w_prime_joules: float, cp: float) -> None:
        """Args:
            w_prime_joules: reserva anaeróbica total do atleta em joules.
            cp: potência crítica (Critical Power) em watts.
        """
        self.wp = w_prime_joules
        self.cp = cp

    def calculate_balance(self, streams: list) -> list[float]:
        """Calcula o balanço de W' segundo a segundo.

        Acima do CP, W' é depletado na proporção (potência − CP).
        Abaixo do CP, W' se recupera a 50% da diferença (cp − potência),
        limitado ao valor inicial.

        Args:
            streams: lista de ActivityStream com campo power_w

        Returns:
            Lista de balanços de W' (joules) para cada instante da série.
        """
        b: list[float] = []
        w = self.wp
        for s in streams:
            if s.power_w is None:
                b.append(w)
                continue
            if s.power_w > self.cp:
                w = w - (s.power_w - self.cp)
            else:
                w = min(w + (self.cp - s.power_w) * 0.5, self.wp)
            b.append(max(w, 0))
        return b
