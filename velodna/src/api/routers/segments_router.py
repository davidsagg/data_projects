"""
Router: /segments — segmentos pessoais e histórico de passagens (US-07/08).

Um segmento é criado a partir de um trecho de uma atividade: o atleta escolhe
o instante inicial e o final, e o sistema procura esse mesmo trecho em todo o
histórico. É o inverso do modelo do Strava, onde os segmentos são públicos e
pré-existentes — aqui eles nascem do que a pessoa de fato pedalou.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_athlete_id, get_db
from api.query import row as query_row, rows as query_rows
from routes.segment_matcher import find_efforts, haversine_m, new_segment_id

router = APIRouter()

# Um segmento curto demais não distingue esforço de variação de GPS.
MIN_SEGMENT_LENGTH_M = 200.0


class CreateSegmentRequest(BaseModel):
    activity_id: str
    start_time_s: int
    end_time_s: int
    name: str


def _require_athlete(db) -> str:
    athlete_id = get_athlete_id(db)
    if athlete_id is None:
        raise HTTPException(status_code=404, detail="Nenhum atleta cadastrado")
    return athlete_id


def _points(db, activity_id: str) -> list[dict]:
    """Carrega os pontos com GPS de uma atividade."""
    return query_rows(
        db,
        """
        SELECT time_s, lat, lon, distance_m, power_w, hr_bpm
        FROM activity_streams
        WHERE activity_id = ? AND lat IS NOT NULL AND lon IS NOT NULL
        ORDER BY time_s
        """,
        [activity_id],
    )


@router.get("/segments")
def list_segments(db=Depends(get_db)):
    """Lista os segmentos do atleta com o resumo das passagens."""
    return query_rows(
        db,
        """
        SELECT s.id, s.name, s.distance_m, s.elevation_gain_m, s.avg_grade_pct,
               COUNT(e.id)                     AS efforts,
               MIN(e.elapsed_time_s)           AS best_time_s,
               MAX(e.started_at)               AS last_effort_at
        FROM segments s
        LEFT JOIN segment_efforts e ON e.segment_id = s.id
        GROUP BY s.id, s.name, s.distance_m, s.elevation_gain_m, s.avg_grade_pct
        ORDER BY s.name
        """,
    )


@router.post("/segments", status_code=201)
def create_segment(req: CreateSegmentRequest, db=Depends(get_db)):
    """Cria um segmento a partir de um trecho de atividade e busca as passagens.

    O trecho define o traçado; a varredura por todo o histórico acontece na
    criação, para que o segmento já nasça com o histórico completo.
    """
    athlete_id = _require_athlete(db)
    points = _points(db, req.activity_id)
    if not points:
        raise HTTPException(status_code=404, detail="Atividade sem dados de GPS")

    span = [p for p in points if req.start_time_s <= p["time_s"] <= req.end_time_s]
    if len(span) < 2:
        raise HTTPException(status_code=422, detail="Trecho curto demais")

    first, last = span[0], span[-1]
    length = (last["distance_m"] or 0) - (first["distance_m"] or 0)
    if length < MIN_SEGMENT_LENGTH_M:
        raise HTTPException(
            status_code=422,
            detail=f"Segmento precisa ter ao menos {MIN_SEGMENT_LENGTH_M:.0f} m",
        )

    segment_id = new_segment_id()
    db.execute(
        """
        INSERT INTO segments (id, name, start_lat, start_lon, end_lat, end_lon,
                              distance_m, elevation_gain_m, avg_grade_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            segment_id, req.name,
            first["lat"], first["lon"], last["lat"], last["lon"],
            length, None, None,
        ],
    )

    matched = _rescan(db, athlete_id, segment_id)
    return {"id": segment_id, "distance_m": round(length, 1), "efforts": matched}


@router.post("/segments/{segment_id}/rescan")
def rescan_segment(segment_id: str, db=Depends(get_db)):
    """Reprocessa o histórico à procura de passagens novas."""
    athlete_id = _require_athlete(db)
    return {"efforts": _rescan(db, athlete_id, segment_id)}


@router.get("/segments/{segment_id}/efforts")
def list_efforts(segment_id: str, db=Depends(get_db)):
    """Histórico de passagens por um segmento, da mais rápida para a mais lenta."""
    segment = query_row(db, "SELECT * FROM segments WHERE id = ?", [segment_id])
    if segment is None:
        raise HTTPException(status_code=404, detail="Segmento não encontrado")

    efforts = query_rows(
        db,
        """
        SELECT e.id, e.activity_id, e.started_at, e.elapsed_time_s,
               e.avg_power_w, e.avg_hr_bpm, e.avg_speed_ms, e.rank, e.is_pr,
               a.sport_type
        FROM segment_efforts e
        JOIN activities a ON a.id = e.activity_id
        WHERE e.segment_id = ?
        ORDER BY e.elapsed_time_s
        """,
        [segment_id],
    )
    return {"segment": segment, "efforts": efforts}


@router.delete("/segments/{segment_id}", status_code=204)
def delete_segment(segment_id: str, db=Depends(get_db)):
    """Remove um segmento e suas passagens."""
    db.execute("DELETE FROM segment_efforts WHERE segment_id = ?", [segment_id])
    db.execute("DELETE FROM segments WHERE id = ?", [segment_id])


def _rescan(db, athlete_id: str, segment_id: str) -> int:
    """Varre o histórico e regrava as passagens de um segmento.

    Args:
        db: conexão DuckDB.
        athlete_id: UUID do atleta.
        segment_id: segmento a reprocessar.

    Returns:
        Número de passagens encontradas.
    """
    segment = query_row(db, "SELECT * FROM segments WHERE id = ?", [segment_id])
    if segment is None:
        raise HTTPException(status_code=404, detail="Segmento não encontrado")

    start = (segment["start_lat"], segment["start_lon"])
    end = (segment["end_lat"], segment["end_lon"])

    # Só as atividades que passaram perto do início entram na varredura fina —
    # comparar ponto a ponto todo o acervo seria desnecessariamente caro.
    candidates = query_rows(
        db,
        """
        SELECT DISTINCT a.id, a.started_at
        FROM activities a
        JOIN activity_streams s ON s.activity_id = a.id
        WHERE a.athlete_id = ?
          AND s.lat BETWEEN ? AND ?
          AND s.lon BETWEEN ? AND ?
        """,
        [athlete_id, *_bounding_box(start[0], start[1])],
    )

    db.execute("DELETE FROM segment_efforts WHERE segment_id = ?", [segment_id])

    found: list[tuple] = []
    for candidate in candidates:
        points = _points(db, str(candidate["id"]))
        for effort in find_efforts(points, start, end, segment["distance_m"]):
            found.append((candidate, effort))

    if not found:
        return 0

    # `rank` e `is_pr` são derivados da ordenação por tempo.
    found.sort(key=lambda pair: pair[1].elapsed_time_s)
    db.executemany(
        """
        INSERT INTO segment_efforts (
            id, activity_id, segment_id, athlete_id, started_at,
            elapsed_time_s, avg_power_w, avg_hr_bpm, avg_speed_ms, is_pr, rank
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                new_segment_id(),
                candidate["id"],
                segment_id,
                athlete_id,
                _effort_timestamp(candidate["started_at"], effort.started_at_s),
                effort.elapsed_time_s,
                effort.avg_power_w,
                effort.avg_hr_bpm,
                round(effort.avg_speed_ms, 2),
                index == 0,
                index + 1,
            )
            for index, (candidate, effort) in enumerate(found)
        ],
    )
    return len(found)


def _bounding_box(lat: float, lon: float, radius_m: float = 60.0):
    """Caixa geográfica em torno de um ponto, para filtrar candidatos em SQL.

    Args:
        lat: latitude do centro.
        lon: longitude do centro.
        radius_m: meia-largura da caixa, em metros.

    Returns:
        Tupla (lat_min, lat_max, lon_min, lon_max).
    """
    delta_lat = radius_m / 111_320.0
    # Meridianos se aproximam com a latitude: sem o cosseno, a caixa fica
    # estreita demais perto dos polos e larga demais no equador.
    import math

    delta_lon = radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))
    return lat - delta_lat, lat + delta_lat, lon - delta_lon, lon + delta_lon


def _effort_timestamp(activity_start, offset_s: int) -> Optional[datetime]:
    """Instante absoluto de uma passagem, a partir do início da atividade."""
    if activity_start is None:
        return None
    from datetime import timedelta

    return activity_start + timedelta(seconds=int(offset_s))
