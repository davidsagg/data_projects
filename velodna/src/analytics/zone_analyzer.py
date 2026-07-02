"""
Zone Analyzer — distribui tempo em zonas de potência de Coggan.

Zonas calculadas como fração do FTP do atleta (Z1–Z6).
"""
from __future__ import annotations


class ZoneAnalyzer:
    """Calcula o tempo gasto em cada zona de potência a partir de streams."""

    ZONES = {
        "Z1": (0,    0.55),
        "Z2": (0.55, 0.75),
        "Z3": (0.75, 0.90),
        "Z4": (0.90, 1.05),
        "Z5": (1.05, 1.20),
        "Z6": (1.20, 99),
    }

    def __init__(self, ftp: float) -> None:
        """Args:
            ftp: FTP do atleta em watts.
        """
        self.ftp = ftp

    def time_in_zones(self, streams: list) -> dict[str, int]:
        """Conta segundos em cada zona de potência.

        Args:
            streams: lista de ActivityStream com campo power_w

        Returns:
            Dicionário {zona: segundos} para Z1–Z6.
        """
        c = {z: 0 for z in self.ZONES}
        for s in streams:
            if s.power_w is None:
                continue
            p = s.power_w / self.ftp
            for z, (lo, hi) in self.ZONES.items():
                if lo <= p < hi:
                    c[z] += 1
                    break
        return c
