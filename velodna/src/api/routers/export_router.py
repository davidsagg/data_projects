"""
Router: /export — exportação de dados em CSV (US-05).

O objetivo é o atleta poder levar os próprios dados embora: abrir na planilha,
analisar em R, migrar para outra plataforma. Por isso o CSV traz nomes de coluna
legíveis e valores já convertidos para as unidades usuais (km, minutos), em vez
de espelhar o schema interno.

A resposta é gerada em streaming: o histórico de streams de uma atividade longa
tem dezenas de milhares de linhas, e montar tudo em memória antes de responder
não escala.
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.dependencies import get_db

router = APIRouter()

# Linhas acumuladas antes de cada envio. Equilibra número de writes e memória.
CHUNK_ROWS = 500

ACTIVITY_COLUMNS = [
    ("data", "Data"),
    ("hora", "Hora"),
    ("esporte", "Esporte"),
    ("distancia_km", "Distância (km)"),
    ("duracao_min", "Duração (min)"),
    ("movimento_min", "Em movimento (min)"),
    ("elevacao_m", "Elevação (m)"),
    ("potencia_media_w", "Potência média (W)"),
    ("potencia_normalizada_w", "Potência normalizada (W)"),
    ("potencia_maxima_w", "Potência máxima (W)"),
    ("fc_media_bpm", "FC média (bpm)"),
    ("fc_maxima_bpm", "FC máxima (bpm)"),
    ("cadencia_media_rpm", "Cadência média (rpm)"),
    ("intensity_factor", "Intensity Factor"),
    ("variability_index", "Variability Index"),
    ("efficiency_factor", "Efficiency Factor"),
    ("decoupling_pct", "Decoupling (%)"),
    ("tss", "TSS"),
    ("tss_origem", "Origem do TSS"),
    ("hrss", "HRSS"),
    ("ftp_na_data_w", "FTP na data (W)"),
    ("id", "ID"),
]


def _stream_csv(header: list[str], rows: Iterator[list]) -> Iterator[str]:
    """Serializa linhas em CSV, liberando o texto em blocos.

    Args:
        header: rótulos das colunas.
        rows: gerador de linhas já na ordem do cabeçalho.

    Yields:
        Trechos de texto CSV.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)

    for index, row in enumerate(rows, start=1):
        writer.writerow(row)
        if index % CHUNK_ROWS == 0:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    remaining = buffer.getvalue()
    if remaining:
        yield remaining


def _csv_response(filename: str, header: list[str], rows: Iterator[list]):
    """Monta a resposta de download de um CSV."""
    return StreamingResponse(
        _stream_csv(header, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/activities.csv")
def export_activities(
    start: Optional[date] = None,
    end: Optional[date] = None,
    sport: str = "all",
    db=Depends(get_db),
):
    """Exporta o resumo das atividades, uma linha por treino."""
    result = db.execute(
        """
        -- TIMESTAMPTZ não converte direto para TIME no DuckDB; formatar como
        -- texto preserva a hora local sem passar por um cast inválido.
        SELECT CAST(started_at AS DATE), STRFTIME(started_at, '%H:%M'), sport_type,
               distance_m, elapsed_time_s, moving_time_s, elevation_gain_m,
               avg_power_w, normalized_power_w, max_power_w,
               avg_hr_bpm, max_hr_bpm, avg_cadence_rpm,
               intensity_factor, variability_index, efficiency_factor,
               decoupling_pct, tss, tss_source, hrss, ftp_w_at_time, id
        FROM activities
        WHERE (? IS NULL OR CAST(started_at AS DATE) >= ?)
          AND (? IS NULL OR CAST(started_at AS DATE) <= ?)
          AND (? = 'all' OR sport_type = ?)
        ORDER BY started_at
        """,
        [start, start, end, end, sport, sport],
    )

    def rows():
        for r in result.fetchall():
            yield [
                r[0], r[1] or "", r[2],
                _round(r[3] / 1000 if r[3] else None, 2),
                _round(r[4] / 60 if r[4] else None, 1),
                _round(r[5] / 60 if r[5] else None, 1),
                _round(r[6], 0),
                _round(r[7], 0), _round(r[8], 0), _round(r[9], 0),
                _round(r[10], 0), _round(r[11], 0), _round(r[12], 0),
                _round(r[13], 3), _round(r[14], 3), _round(r[15], 3),
                _round(r[16], 2), _round(r[17], 1), r[18], _round(r[19], 1),
                _round(r[20], 0), r[21],
            ]

    return _csv_response(
        "velodna_atividades.csv", [label for _, label in ACTIVITY_COLUMNS], rows()
    )


@router.get("/export/training-load.csv")
def export_training_load(db=Depends(get_db)):
    """Exporta a série diária de carga: CTL, ATL, TSB e TSS do dia."""
    result = db.execute(
        "SELECT date, ctl, atl, tsb, daily_tss FROM training_load ORDER BY date"
    )

    def rows():
        for r in result.fetchall():
            yield [r[0], _round(r[1], 2), _round(r[2], 2), _round(r[3], 2), _round(r[4], 1)]

    return _csv_response(
        "velodna_carga.csv",
        ["Data", "CTL", "ATL", "TSB", "TSS do dia"],
        rows(),
    )


@router.get("/export/health.csv")
def export_health(db=Depends(get_db)):
    """Exporta as métricas diárias de saúde."""
    result = db.execute(
        """
        SELECT date, hrv_rmssd_ms, hrv_status, resting_hr_bpm, sleep_hours,
               sleep_quality_score, deep_sleep_min, rem_sleep_min,
               body_battery, body_battery_min, stress_level, steps
        FROM health_metrics ORDER BY date
        """
    )

    def rows():
        for r in result.fetchall():
            yield [
                r[0], _round(r[1], 1), r[2], _round(r[3], 0), _round(r[4], 2),
                _round(r[5], 0), _round(r[6], 0), _round(r[7], 0),
                _round(r[8], 0), _round(r[9], 0), _round(r[10], 0), _round(r[11], 0),
            ]

    return _csv_response(
        "velodna_saude.csv",
        [
            "Data", "HRV (ms)", "Status HRV", "FC repouso (bpm)", "Sono (h)",
            "Score do sono", "Sono profundo (min)", "Sono REM (min)",
            "Body battery (máx)", "Body battery (mín)", "Estresse", "Passos",
        ],
        rows(),
    )


@router.get("/export/power-curve.csv")
def export_power_curve(sport: str = "cycling", db=Depends(get_db)):
    """Exporta a curva de potência agregada: melhor esforço por duração."""
    result = db.execute(
        """
        SELECT pc.duration_s, MAX(pc.power_w) AS power_w,
               ARG_MAX(pc.date, pc.power_w) AS achieved_on
        FROM power_curves pc
        JOIN activities a ON a.id = pc.activity_id
        WHERE (? = 'all' OR a.sport_type = ?)
        GROUP BY pc.duration_s
        ORDER BY pc.duration_s
        """,
        [sport, sport],
    )

    def rows():
        for r in result.fetchall():
            yield [r[0], _round(r[1], 0), r[2]]

    return _csv_response(
        "velodna_curva_potencia.csv",
        ["Duração (s)", "Potência (W)", "Alcançado em"],
        rows(),
    )


@router.get("/export/activities/{activity_id}/streams.csv")
def export_activity_streams(activity_id: str, db=Depends(get_db)):
    """Exporta a série temporal completa de uma atividade, segundo a segundo."""
    exists = db.execute(
        "SELECT 1 FROM activities WHERE id = ?", [activity_id]
    ).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")

    result = db.execute(
        """
        SELECT time_s, lat, lon, altitude_m, distance_m, power_w, hr_bpm,
               cadence_rpm, speed_ms, temperature_c
        FROM activity_streams WHERE activity_id = ? ORDER BY time_s
        """,
        [activity_id],
    )

    def rows():
        for r in result.fetchall():
            yield [
                r[0], r[1], r[2], _round(r[3], 1), _round(r[4], 1),
                _round(r[5], 0), _round(r[6], 0), _round(r[7], 0),
                _round(r[8], 2), _round(r[9], 1),
            ]

    return _csv_response(
        f"velodna_streams_{activity_id[:8]}.csv",
        [
            "Tempo (s)", "Latitude", "Longitude", "Altitude (m)",
            "Distância (m)", "Potência (W)", "FC (bpm)", "Cadência (rpm)",
            "Velocidade (m/s)", "Temperatura (°C)",
        ],
        rows(),
    )


def _round(value, digits: int):
    """Arredonda mantendo célula vazia para valores ausentes."""
    if value is None:
        return ""
    return round(float(value), digits) if digits else int(round(float(value)))

