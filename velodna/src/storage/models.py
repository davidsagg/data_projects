"""
Modelos de domínio do VeloDNA — contrato entre o parser e a camada de persistência.

O `FITParser` devolve um DTO cru, fiel ao arquivo `.fit` (timestamps absolutos,
nomes de campo do protocolo Garmin). O `CatalogStore` persiste o modelo de
domínio: tempo relativo ao início da atividade, nomes canônicos e as métricas
derivadas (NP, IF, VI) que a analytics preenche depois.

Manter os dois separados evita que uma mudança no formato de arquivo vaze para
o schema do banco.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ingestion.fit_parser import Activity as FITActivity


@dataclass
class ActivityStream:
    """Um ponto da série temporal, com tempo relativo ao início da atividade."""

    time_s: int
    lat: Optional[float] = None
    lon: Optional[float] = None
    altitude_m: Optional[float] = None
    distance_m: Optional[float] = None
    power_w: Optional[float] = None
    hr_bpm: Optional[float] = None
    cadence_rpm: Optional[float] = None
    speed_ms: Optional[float] = None
    temperature_c: Optional[float] = None
    left_right_balance: Optional[float] = None


@dataclass
class Activity:
    """Resumo de uma atividade, como persistido na tabela `activities`."""

    source: str
    sport_type: str
    started_at: datetime
    elapsed_time_s: int

    id: Optional[str] = None
    garmin_id: Optional[str] = None
    strava_id: Optional[int] = None

    moving_time_s: Optional[int] = None
    distance_m: Optional[float] = None
    elevation_gain_m: Optional[float] = None

    avg_power_w: Optional[float] = None
    max_power_w: Optional[float] = None
    normalized_power_w: Optional[float] = None

    avg_hr_bpm: Optional[float] = None
    max_hr_bpm: Optional[int] = None
    avg_cadence_rpm: Optional[float] = None
    avg_speed_ms: Optional[float] = None

    tss: Optional[float] = None
    intensity_factor: Optional[float] = None
    variability_index: Optional[float] = None

    raw_file_path: Optional[str] = None
    streams: list[ActivityStream] = field(default_factory=list)


def stream_from_fit(raw, started_at: datetime) -> ActivityStream:
    """Converte um ponto do parser FIT para o modelo de domínio.

    Args:
        raw: `ingestion.fit_parser.ActivityStream` com timestamp absoluto.
        started_at: início da atividade, usado como origem do tempo relativo.

    Returns:
        ActivityStream com `time_s` relativo, nunca negativo.
    """
    delta = int((raw.timestamp - started_at).total_seconds())
    return ActivityStream(
        time_s=max(delta, 0),
        lat=raw.lat,
        lon=raw.lon,
        altitude_m=raw.altitude_m,
        distance_m=raw.distance_m,
        power_w=raw.power_w,
        hr_bpm=raw.heart_rate_bpm,
        cadence_rpm=raw.cadence_rpm,
        speed_ms=raw.speed_ms,
        temperature_c=raw.temperature_c,
    )


def activity_from_fit(raw: FITActivity, source: str = "fit") -> Activity:
    """Converte a saída do `FITParser` para o modelo de domínio.

    As métricas derivadas (NP, IF, VI, TSS) ficam vazias — são responsabilidade
    da camada de analytics, que roda depois da persistência dos streams.

    Args:
        raw: atividade retornada por `FITParser.parse`.
        source: origem do dado, gravado na coluna `source`.

    Returns:
        Activity de domínio com streams convertidos para tempo relativo.
    """
    return Activity(
        source=source,
        sport_type=raw.sport_type,
        started_at=raw.start_time,
        elapsed_time_s=raw.duration_s,
        garmin_id=raw.garmin_id,
        distance_m=raw.distance_m,
        elevation_gain_m=raw.elevation_m,
        avg_power_w=raw.avg_power_w,
        max_power_w=raw.max_power_w,
        avg_hr_bpm=raw.avg_hr_bpm,
        max_hr_bpm=raw.max_hr_bpm,
        raw_file_path=raw.fit_file_path,
        streams=[stream_from_fit(s, raw.start_time) for s in raw.streams],
    )
