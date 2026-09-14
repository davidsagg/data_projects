"""
Router: /efficiency e /zones — métricas de eficiência aeróbica e distribuição
de intensidade.

Estas métricas são o que sobra quando não há potência, e o que mais revela
adaptação aeróbica quando há: se a mesma potência custa menos batimentos ao
longo dos meses, houve ganho de base — mesmo que o FTP não tenha mudado.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from analytics.ftp_history import ftp_on
from analytics.timeseries import load_series
from analytics.zones import (
    build_hr_zones,
    build_power_zones,
    zone_distribution,
)
from api.query import rows as query_rows
from api.dependencies import get_athlete_id, get_db
from storage.catalog_store import CatalogStore

router = APIRouter()

# Acima deste percentual, a deriva cardíaca indica resistência aeróbica
# insuficiente para a duração do esforço (Friel).
DECOUPLING_THRESHOLD_PCT = 5.0

# Esforços curtos não têm metades comparáveis para medir deriva.
MIN_DURATION_FOR_DECOUPLING_S = 1800


@router.get("/efficiency")
def get_efficiency(
    start: Optional[date] = None,
    end: Optional[date] = None,
    sport: str = "cycling",
    db=Depends(get_db),
):
    """Série de Efficiency Factor e desacoplamento por atividade.

    EF é NP dividido pela FC média: quanto mais alto, mais potência por
    batimento. Comparar EF entre atividades só faz sentido em intensidades
    semelhantes, por isso o IF vem junto.
    """
    return query_rows(db, """
        SELECT CAST(started_at AS DATE) AS date, id, sport_type,
               elapsed_time_s, normalized_power_w, avg_hr_bpm,
               efficiency_factor, decoupling_pct, intensity_factor, tss
        FROM activities
        WHERE efficiency_factor IS NOT NULL
          AND (? IS NULL OR CAST(started_at AS DATE) >= ?)
          AND (? IS NULL OR CAST(started_at AS DATE) <= ?)
          AND (? = 'all' OR sport_type = ?)
        ORDER BY started_at
        """, [start, start, end, end, sport, sport])


@router.get("/decoupling")
def get_decoupling(
    days: int = 180,
    sport: str = "cycling",
    db=Depends(get_db),
):
    """Desacoplamento aeróbico dos treinos longos do período.

    Só considera esforços com duração suficiente para ter duas metades
    comparáveis — medir deriva cardíaca num treino de 20 minutos não diz nada.
    """
    items = query_rows(
        db,
        """
        SELECT CAST(started_at AS DATE) AS date, id, elapsed_time_s,
               normalized_power_w, avg_hr_bpm, decoupling_pct, intensity_factor
        FROM activities
        WHERE decoupling_pct IS NOT NULL
          AND elapsed_time_s >= ?
          AND CAST(started_at AS DATE) >= CURRENT_DATE - ?
          AND (? = 'all' OR sport_type = ?)
        ORDER BY started_at
        """,
        [MIN_DURATION_FOR_DECOUPLING_S, days, sport, sport],
    )

    for item in items:
        item["aerobically_durable"] = (
            item["decoupling_pct"] is not None
            and item["decoupling_pct"] <= DECOUPLING_THRESHOLD_PCT
        )

    return {
        "threshold_pct": DECOUPLING_THRESHOLD_PCT,
        "min_duration_s": MIN_DURATION_FOR_DECOUPLING_S,
        "activities": items,
    }


@router.get("/zones/definitions")
def get_zone_definitions(on: Optional[date] = None, db=Depends(get_db)):
    """Zonas de potência e de FC vigentes numa data.

    As zonas acompanham o limiar: consultar uma data antiga devolve as zonas
    que valiam à época, não as de hoje.
    """
    target = on or date.today()
    store = CatalogStore(db)
    athlete_id = get_athlete_id(db)
    if athlete_id is None:
        raise HTTPException(status_code=404, detail="Nenhum atleta cadastrado")

    ftp = ftp_on(store, athlete_id, target)
    athlete = db.execute(
        "SELECT threshold_hr_bpm, weight_kg, max_hr_bpm, resting_hr_bpm "
        "FROM athletes WHERE id = ?",
        [athlete_id],
    ).fetchone()
    threshold_hr = (athlete[0],) if athlete else None

    response: dict = {
        "date": str(target),
        "ftp_w": ftp,
        "weight_kg": float(athlete[1]) if athlete and athlete[1] else None,
        "max_hr_bpm": int(athlete[2]) if athlete and athlete[2] else None,
        "resting_hr_bpm": int(athlete[3]) if athlete and athlete[3] else None,
    }
    if ftp:
        response["power"] = [
            {"zone": z.name, "label": z.label, "min_w": z.low,
             "max_w": None if z.high == float("inf") else z.high}
            for z in build_power_zones(ftp)
        ]
    if threshold_hr and threshold_hr[0]:
        response["threshold_hr_bpm"] = float(threshold_hr[0])
        response["hr"] = [
            {"zone": z.name, "label": z.label, "min_bpm": z.low,
             "max_bpm": None if z.high == float("inf") else z.high}
            for z in build_hr_zones(float(threshold_hr[0]))
        ]
    return response


@router.get("/activities/{activity_id}/zone-distribution")
def get_activity_zone_distribution(activity_id: str, db=Depends(get_db)):
    """Distribuição de tempo por zona de potência e de FC numa atividade."""
    store = CatalogStore(db)
    athlete_id = get_athlete_id(db)

    row = db.execute(
        "SELECT CAST(started_at AS DATE) FROM activities WHERE id = ?", [activity_id]
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")

    series = load_series(db, activity_id)
    if not series.segments:
        raise HTTPException(status_code=404, detail="Atividade sem streams")

    response: dict = {"activity_id": activity_id, "date": str(row[0])}

    ftp = ftp_on(store, athlete_id, row[0]) if athlete_id else None
    if ftp and series.has_data("power"):
        response["ftp_w"] = ftp
        response["power"] = zone_distribution(series, build_power_zones(ftp), "power")

    threshold_hr = db.execute(
        "SELECT threshold_hr_bpm FROM athletes WHERE id = ?", [athlete_id]
    ).fetchone() if athlete_id else None

    if threshold_hr and threshold_hr[0] and series.has_data("hr"):
        response["threshold_hr_bpm"] = float(threshold_hr[0])
        response["hr"] = zone_distribution(
            series, build_hr_zones(float(threshold_hr[0])), "hr"
        )

    return response
