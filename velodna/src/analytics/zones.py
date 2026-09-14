"""
Zonas de treino de potência e de frequência cardíaca.

As zonas mudam quando o limiar muda: uma sessão de 2024 pedalada a 200 W estava
em Z4 com FTP de 218 W, mas estaria em Z3 com o FTP de 260 W. Por isso as zonas
são **derivadas do limiar vigente na data**, não de uma tabela fixa.

Potência segue as sete zonas de Coggan, ancoradas no FTP. Frequência cardíaca
segue as cinco zonas ancoradas no limiar (LTHR) — e não em percentual da FC
máxima, que é menos preciso porque a FC máxima quase não responde ao treino
enquanto o limiar responde muito.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

import numpy as np

from analytics.timeseries import ActivitySeries

# Limites como fração do FTP. O topo aberto vira infinito.
COGGAN_POWER_ZONES: tuple[tuple[str, str, float, float], ...] = (
    ("Z1", "Recuperação ativa", 0.00, 0.55),
    ("Z2", "Endurance",         0.55, 0.75),
    ("Z3", "Tempo",             0.75, 0.90),
    ("Z4", "Limiar",            0.90, 1.05),
    ("Z5", "VO2máx",            1.05, 1.20),
    ("Z6", "Anaeróbico",        1.20, 1.50),
    ("Z7", "Neuromuscular",     1.50, float("inf")),
)

# Limites como fração da FC de limiar.
COGGAN_HR_ZONES: tuple[tuple[str, str, float, float], ...] = (
    ("Z1", "Recuperação ativa", 0.00, 0.81),
    ("Z2", "Endurance",         0.81, 0.89),
    ("Z3", "Tempo",             0.89, 0.94),
    ("Z4", "Limiar",            0.94, 1.00),
    ("Z5", "VO2máx",            1.00, float("inf")),
)


@dataclass(frozen=True)
class Zone:
    """Uma faixa de intensidade, em unidade absoluta."""

    number: int
    label: str
    low: float
    high: float

    @property
    def name(self) -> str:
        """Rótulo curto da zona (Z1…Z7)."""
        return f"Z{self.number}"


def build_power_zones(ftp_w: float) -> list[Zone]:
    """Constrói as zonas de potência de Coggan para um dado FTP.

    Args:
        ftp_w: FTP em watts.

    Returns:
        Sete zonas em watts, em ordem crescente.
    """
    return [
        Zone(index + 1, label, round(low * ftp_w, 1), round(high * ftp_w, 1))
        for index, (_, label, low, high) in enumerate(COGGAN_POWER_ZONES)
    ]


def build_hr_zones(threshold_hr_bpm: float) -> list[Zone]:
    """Constrói as zonas de FC ancoradas no limiar.

    Args:
        threshold_hr_bpm: FC de limiar (LTHR) em bpm.

    Returns:
        Cinco zonas em bpm, em ordem crescente.
    """
    return [
        Zone(index + 1, label, round(low * threshold_hr_bpm, 1),
             round(high * threshold_hr_bpm, 1))
        for index, (_, label, low, high) in enumerate(COGGAN_HR_ZONES)
    ]


def time_in_zones(
    series: ActivitySeries,
    zones: list[Zone],
    channel: str = "power",
) -> dict[str, int]:
    """Conta os segundos passados em cada zona.

    A série está em grade de 1 Hz, então contar amostras é contar segundos.
    Amostras sem medida (NaN) ficam de fora — não são zero.

    Args:
        series: série já segmentada da atividade.
        zones: zonas em unidade absoluta, em ordem crescente.
        channel: canal a classificar (`power` ou `hr`).

    Returns:
        Dicionário {zona: segundos}, incluindo zonas com zero.
    """
    result = {zone.name: 0 for zone in zones}

    values = series.concat(channel)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return result

    edges = [zone.low for zone in zones] + [zones[-1].high]
    # np.digitize devolve o índice da faixa de cada amostra; `right=False`
    # deixa o limite inferior pertencendo à zona de cima, como manda Coggan.
    indices = np.digitize(values, edges[1:-1], right=False)

    for index, count in zip(*np.unique(indices, return_counts=True)):
        if 0 <= index < len(zones):
            result[zones[index].name] = int(count)
    return result


def zone_distribution(
    series: ActivitySeries,
    zones: list[Zone],
    channel: str = "power",
) -> list[dict]:
    """Distribuição de tempo por zona, com percentuais e limites.

    Args:
        series: série já segmentada da atividade.
        zones: zonas em unidade absoluta.
        channel: canal a classificar.

    Returns:
        Lista por zona com segundos, percentual e faixa de valores.
    """
    seconds = time_in_zones(series, zones, channel)
    total = sum(seconds.values()) or 1

    return [
        {
            "zone": zone.name,
            "label": zone.label,
            "low": zone.low,
            "high": None if zone.high == float("inf") else zone.high,
            "seconds": seconds[zone.name],
            "pct": round(seconds[zone.name] / total * 100, 1),
        }
        for zone in zones
    ]


def persist_zones(
    store,
    athlete_id: str,
    effective_from: date,
    power_zones: list[Zone] | None = None,
    hr_zones: list[Zone] | None = None,
) -> None:
    """Grava as zonas vigentes a partir de uma data.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        effective_from: data a partir da qual as zonas valem.
        power_zones: zonas de potência a gravar.
        hr_zones: zonas de FC a gravar.
    """
    if power_zones:
        store.conn.execute(
            "DELETE FROM power_zones WHERE athlete_id = ? AND effective_from = ?",
            [athlete_id, effective_from],
        )
        store.conn.executemany(
            """
            INSERT INTO power_zones (id, athlete_id, zone, label, min_w, max_w,
                                     effective_from)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(uuid.uuid4()), athlete_id, zone.number, zone.label,
                    zone.low, None if zone.high == float("inf") else zone.high,
                    effective_from,
                )
                for zone in power_zones
            ],
        )

    if hr_zones:
        store.conn.execute(
            "DELETE FROM hr_zones WHERE athlete_id = ? AND effective_from = ?",
            [athlete_id, effective_from],
        )
        store.conn.executemany(
            """
            INSERT INTO hr_zones (id, athlete_id, zone, label, min_bpm, max_bpm,
                                  effective_from)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(uuid.uuid4()), athlete_id, zone.number, zone.label,
                    int(zone.low),
                    None if zone.high == float("inf") else int(zone.high),
                    effective_from,
                )
                for zone in hr_zones
            ],
        )
