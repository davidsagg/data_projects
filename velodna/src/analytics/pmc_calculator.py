"""
PMC Calculator — Performance Management Chart (CTL / ATL / TSB).

Referência: Coggan & Allen, "Training and Racing with a Power Meter".

  CTL (Chronic Training Load)  — fitness  — média exponencial de 42 dias
  ATL (Acute Training Load)    — fadiga   — média exponencial de  7 dias
  TSB (Training Stress Balance)— forma    — CTL do dia anterior menos ATL

Duas propriedades são essenciais e fáceis de errar:

1. A série precisa ser **diária e contínua**. Dias de descanso entram com
   TSS = 0 — é exatamente neles que o decaimento exponencial acontece. Iterar
   apenas sobre os dias com atividade faz a fadiga nunca baixar.
2. O TSS de um dia é a **soma** de todas as atividades daquele dia. Quem treina
   duas vezes no mesmo dia não pode ter a primeira sessão descartada.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

CTL_DECAY_DAYS = 42
ATL_DECAY_DAYS = 7


class PMCCalculator:
    """Calcula CTL, ATL e TSB a partir da série diária de TSS."""

    def _ewa(
        self, daily_tss: dict[date, float], decay: int, seed: float = 0.0
    ) -> dict[date, float]:
        """Média exponencial sobre a série diária de TSS.

        Args:
            daily_tss: série contínua {data: tss}, já sem lacunas.
            decay: constante de tempo em dias (42 para CTL, 7 para ATL).
            seed: valor de partida, para quando existe treino anterior ao
                início da série.

        Returns:
            Dicionário {data: valor} para cada data da série.
        """
        alpha = 1 - math.exp(-1 / decay)
        result: dict[date, float] = {}
        value = seed
        for day in sorted(daily_tss):
            value = alpha * daily_tss[day] + (1 - alpha) * value
            result[day] = round(value, 4)
        return result

    def calculate_ctl(
        self,
        daily_tss: dict[date, float],
        decay: int = CTL_DECAY_DAYS,
        seed: float = 0.0,
    ) -> dict[date, float]:
        """Retorna a série de CTL (fitness).

        Args:
            daily_tss: série diária contínua de TSS.
            decay: constante de tempo, em dias.
            seed: CTL na véspera do início da série.

        Returns:
            Dicionário {data: ctl}.
        """
        return self._ewa(daily_tss, decay, seed)

    def calculate_atl(
        self,
        daily_tss: dict[date, float],
        decay: int = ATL_DECAY_DAYS,
        seed: float = 0.0,
    ) -> dict[date, float]:
        """Retorna a série de ATL (fadiga).

        Args:
            daily_tss: série diária contínua de TSS.
            decay: constante de tempo, em dias.
            seed: ATL na véspera do início da série.

        Returns:
            Dicionário {data: atl}.
        """
        return self._ewa(daily_tss, decay, seed)

    def calculate_tsb(self, ctl: float, atl: float) -> float:
        """Retorna o TSB (forma) a partir de CTL e ATL.

        Args:
            ctl: fitness na data.
            atl: fadiga na data.

        Returns:
            TSB arredondado a 4 casas decimais.
        """
        return round(ctl - atl, 4)

    def build_daily_series(
        self,
        tss_rows: list[tuple[date, float]],
        end_date: date,
        start_date: date | None = None,
    ) -> dict[date, float]:
        """Monta a série diária contínua de TSS.

        Args:
            tss_rows: pares (data, tss), possivelmente com datas repetidas.
            end_date: última data da série.
            start_date: primeira data; usa a menor data observada se omitido.

        Returns:
            Dicionário {data: tss_somado} com todos os dias do intervalo,
            inclusive os de descanso, com valor 0.0.
        """
        if not tss_rows:
            return {}

        totals: dict[date, float] = {}
        for day, tss in tss_rows:
            totals[day] = totals.get(day, 0.0) + float(tss or 0.0)

        first = start_date or min(totals)
        if end_date < first:
            return {}

        return {
            first + timedelta(days=offset): totals.get(first + timedelta(days=offset), 0.0)
            for offset in range((end_date - first).days + 1)
        }

    def run_and_store(
        self,
        store,
        end_date: date,
        athlete_id: str | None = None,
        seed_ctl: float = 0.0,
        seed_atl: float = 0.0,
    ) -> None:
        """Recalcula a série completa de carga e a persiste.

        Args:
            store: CatalogStore com conexão ativa.
            end_date: última data a persistir.
            athlete_id: atleta alvo; resolvido do catálogo quando omitido.
            seed_ctl: CTL na véspera da primeira atividade. Relevante quando o
                histórico foi truncado: sem semente, o primeiro treino forte
                aparece contra um CTL zero e gera um TSB implausível.
            seed_atl: ATL na véspera da primeira atividade.
        """
        athlete_id = athlete_id or store.resolve_athlete_id()

        rows = store.conn.execute(
            """
            SELECT CAST(started_at AS DATE) AS day, SUM(tss)
            FROM activities
            WHERE tss IS NOT NULL AND athlete_id = ?
            GROUP BY day
            ORDER BY day
            """,
            [athlete_id],
        ).fetchall()
        if not rows:
            return

        daily_tss = self.build_daily_series(
            [(r[0], r[1]) for r in rows], end_date
        )
        if not daily_tss:
            return

        ctl = self.calculate_ctl(daily_tss, seed=seed_ctl)
        atl = self.calculate_atl(daily_tss, seed=seed_atl)

        store.bulk_upsert_training_load(
            athlete_id,
            [
                (day, ctl[day], atl[day], self.calculate_tsb(ctl[day], atl[day]),
                 daily_tss[day])
                for day in sorted(daily_tss)
            ],
        )


class FTPDetector:
    """Estima o FTP como 95% da melhor potência média de 20 minutos."""

    WINDOW_S = 1200

    def detect(self, series) -> float | None:
        """Detecta o FTP a partir de uma ActivitySeries.

        Args:
            series: série já segmentada da atividade.

        Returns:
            FTP estimado em watts, ou None se não há 20 minutos contínuos
            de potência.
        """
        from analytics.power_metrics import rolling_mean

        best = 0.0
        for segment_power in series.channel("power"):
            import numpy as np

            clean = np.nan_to_num(segment_power, nan=0.0)
            if clean.size < self.WINDOW_S:
                continue
            rolled = rolling_mean(clean, self.WINDOW_S)
            if rolled.size:
                best = max(best, float(rolled.max()))

        return round(best * 0.95, 1) if best > 0 else None
