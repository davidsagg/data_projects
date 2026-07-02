"""
PMC Calculator — Performance Management Chart (CTL / ATL / TSB).

Referência: Coggan & Allen, "Training and Racing with a Power Meter".

  CTL (Chronic Training Load)  — fitness   — EWA com janela de 42 dias
  ATL (Acute Training Load)    — fadiga    — EWA com janela de  7 dias
  TSB (Training Stress Balance)— forma     — CTL - ATL
"""
from __future__ import annotations

import math
from datetime import date
from typing import Optional


class PMCCalculator:
    """Calcula CTL, ATL e TSB a partir de séries de TSS por data."""

    def _ewa(self, tss_by_date: dict, decay: int) -> dict:
        """Exponential Weighted Average sobre série diária de TSS.

        Args:
            tss_by_date: dicionário {date: tss_float}
            decay: constante de tempo em dias (42 para CTL, 7 para ATL)

        Returns:
            Dicionário {date: valor_ewa} para cada data da série.
        """
        a = 1 - math.exp(-1 / decay)
        r: dict = {}
        v = 0.0
        for d in sorted(tss_by_date):
            v = a * tss_by_date[d] + (1 - a) * v
            r[d] = round(v, 4)
        return r

    def calculate_ctl(self, tss_by_date: dict, decay: int = 42) -> dict:
        """Retorna série de CTL (fitness) — EWA de 42 dias.

        Args:
            tss_by_date: dicionário {date: tss_float}
            decay: constante de tempo (padrão 42 dias)

        Returns:
            Dicionário {date: ctl_float}
        """
        return self._ewa(tss_by_date, decay)

    def calculate_atl(self, tss_by_date: dict, decay: int = 7) -> dict:
        """Retorna série de ATL (fadiga) — EWA de 7 dias.

        Args:
            tss_by_date: dicionário {date: tss_float}
            decay: constante de tempo (padrão 7 dias)

        Returns:
            Dicionário {date: atl_float}
        """
        return self._ewa(tss_by_date, decay)

    def calculate_tsb(self, ctl: float, atl: float) -> float:
        """Retorna TSB (forma) = CTL - ATL.

        Args:
            ctl: valor de CTL para a data
            atl: valor de ATL para a data

        Returns:
            TSB arredondado a 4 casas decimais.
        """
        return round(ctl - atl, 4)

    def run_and_store(self, store, end_date: date) -> None:
        """Calcula CTL/ATL/TSB para todas as datas até end_date e persiste.

        Args:
            store: instância de CatalogStore com conexão DuckDB ativa
            end_date: data limite para persistência das métricas
        """
        rows = store.conn.execute(
            "SELECT CAST(start_time AS DATE), tss FROM activities "
            "WHERE tss IS NOT NULL ORDER BY 1"
        ).fetchall()
        if not rows:
            return

        tss_by_date = {r[0]: r[1] for r in rows}
        ctl = self.calculate_ctl(tss_by_date)
        atl = self.calculate_atl(tss_by_date)

        for d in ctl:
            if d <= end_date:
                store.upsert_athlete_metrics(
                    d,
                    ctl[d],
                    atl.get(d, 0),
                    self.calculate_tsb(ctl[d], atl.get(d, 0)),
                )


class FTPDetector:
    """Estima o FTP do atleta como 95% da melhor potência média de 20 minutos."""

    MIN = 1200  # 20 minutos em segundos

    def detect(self, streams) -> Optional[float]:
        """Detecta FTP a partir de uma lista de ActivityStream.

        Requer pelo menos 20 minutos (1200 segundos) de dados de potência.

        Args:
            streams: lista de ActivityStream com campo power_w

        Returns:
            FTP estimado em watts, ou None se dados insuficientes.
        """
        pw = [s.power_w for s in streams if s.power_w is not None]
        if len(pw) < self.MIN:
            return None
        best = max(
            sum(pw[i : i + self.MIN]) / self.MIN
            for i in range(len(pw) - self.MIN + 1)
        )
        return round(best * 0.95, 1)
