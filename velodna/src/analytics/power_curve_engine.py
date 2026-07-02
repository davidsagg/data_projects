"""
Power Curve Engine — Mean Maximal Power (MMP) por duração.

PowerCurveEngine: classe com método compute() para uso nos testes e rotas.
compute_power_curve: função legada (mantida para compatibilidade).
update_curve_in_db:  busca streams no CatalogStore, computa e persiste a curva.
"""
from __future__ import annotations

from datetime import date


class PowerCurveEngine:
    """Calcula a curva de potência (MMP) a partir de streams de atividade."""

    def compute(self, streams: list, durations: list[int]) -> dict[int, float]:
        """Retorna {duration_s: melhor_potência_média_w} via janela deslizante.

        Args:
            streams: lista de ActivityStream com campo power_w
            durations: lista de durações em segundos a calcular

        Returns:
            Dicionário {duration: best_avg_power}; 0.0 se dados insuficientes.
        """
        pw = [s.power_w for s in streams if s.power_w is not None]
        r = {}
        for d in durations:
            if len(pw) >= d:
                r[d] = round(
                    max(sum(pw[i : i + d]) / d for i in range(len(pw) - d + 1)),
                    2,
                )
            else:
                r[d] = 0.0
        return r

from src.ingestion.fit_parser import ActivityStream

DEFAULT_DURATIONS: list[int] = [1, 5, 10, 20, 30, 60, 120, 300, 600, 1200, 1800, 3600]


def compute_power_curve(
    streams: list[ActivityStream],
    durations: list[int],
) -> dict[int, float]:
    """
    Retorna {duration_s: max_avg_power_w} para cada duração solicitada.

    Assume streams amostrados a 1 Hz (um ponto por segundo). Lacunas no
    time_s são preenchidas com 0 W. Streams com power_w=None contam como 0 W.
    Se a duração excede o comprimento da série, retorna 0.0.
    """
    power = _resample_power(streams)
    return {d: _best_avg_power(power, d) for d in durations}


def update_curve_in_db(
    store,              # CatalogStore — import circular evitado com duck-typing
    activity_id: str,
    activity_date: date,
    durations: list[int] | None = None,
) -> None:
    """
    Busca streams da atividade no store, computa a curva de potência e persiste.

    Upsert por (activity_id, duration_s) — chamadas repetidas são idempotentes.
    """
    if durations is None:
        durations = DEFAULT_DURATIONS
    streams = store.get_streams_for_activity(activity_id)
    curve = compute_power_curve(streams, durations)
    store.save_power_curve(activity_id, activity_date, curve)


# ---------------------------------------------------------------------------
# Funções privadas
# ---------------------------------------------------------------------------

def _resample_power(streams: list[ActivityStream]) -> list[float]:
    """
    Projeta streams sobre array de tamanho (max_time_s + 1), base 0.
    Posições sem stream ficam em 0.0 W.
    """
    if not streams:
        return []
    max_t = max(s.time_s for s in streams)
    power = [0.0] * (max_t + 1)
    for s in streams:
        power[s.time_s] = s.power_w if s.power_w is not None else 0.0
    return power


def _best_avg_power(power: list[float], duration: int) -> float:
    """
    Janela deslizante O(n): retorna a maior média de 'duration' amostras.
    Retorna 0.0 se duration > len(power).
    """
    n = len(power)
    if n == 0 or duration > n:
        return 0.0

    window = sum(power[:duration])
    best = window
    for i in range(1, n - duration + 1):
        window += power[i + duration - 1] - power[i - 1]
        if window > best:
            best = window
    return best / duration
