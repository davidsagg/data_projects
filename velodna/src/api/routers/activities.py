"""
Router: /activities — upload, listagem e streams de atividades.
"""
from __future__ import annotations

import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from analytics.zone_analyzer import ZoneAnalyzer
from api.query import row as query_row, rows as query_rows
from api.dependencies import get_athlete_id, get_db
from ingestion.pipeline import IngestionPipeline
from storage.catalog_store import CatalogStore
from storage.models import ActivityStream

router = APIRouter()

DEFAULT_FTP_W = 200.0


@router.get("/")
def list_activities(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db=Depends(get_db),
):
    """Retorna lista de atividades com filtro opcional por intervalo de datas."""
    athlete_id = get_athlete_id(db)
    if athlete_id is None:
        return []
    return CatalogStore(db).query_activities_by_date_range(
        athlete_id,
        datetime.combine(start, datetime.min.time()) if start else datetime.min,
        datetime.combine(end, datetime.max.time()) if end else datetime.max,
    )


@router.get("/latest")
def get_latest_activity(db=Depends(get_db)):
    """Retorna a atividade mais recente."""
    latest = query_row(
        db, "SELECT * FROM activities ORDER BY started_at DESC LIMIT 1"
    )
    if latest is None:
        raise HTTPException(status_code=404, detail="Nenhuma atividade encontrada")
    return latest


@router.get("/{activity_id}/streams")
def get_activity_streams(activity_id: str, every_n: int = 10, db=Depends(get_db)):
    """
    Retorna streams GPS de uma atividade decimados a cada N pontos.
    every_n=10 retorna ~1 ponto a cada 10 segundos — suficiente para o mapa.
    """
    rows = db.execute(
        """
        SELECT time_s, lat, lon, altitude_m, distance_m, power_w, hr_bpm,
               speed_ms, cadence_rpm
        FROM activity_streams
        WHERE activity_id = ?
          AND lat IS NOT NULL
          AND lon IS NOT NULL
        ORDER BY time_s
        """,
        [activity_id],
    ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404, detail="Nenhum stream GPS para esta atividade"
        )

    cols = ["time_s", "lat", "lon", "altitude_m", "power_w", "hr_bpm", "speed_ms"]
    return [dict(zip(cols, r)) for r in rows[::every_n]]


@router.get("/{activity_id}/power-curve")
def get_activity_power_curve(activity_id: str, db=Depends(get_db)):
    """Retorna a curva de potência de uma única atividade.

    Distinta de `/power-curve`, que devolve o envelope de todo o histórico:
    esta é a curva daquele treino, e é o que permite comparar dois esforços
    duração a duração.
    """
    curve = query_rows(
        db,
        """
        SELECT duration_s, power_w FROM power_curves
        WHERE activity_id = ? ORDER BY duration_s
        """,
        [activity_id],
    )
    if not curve:
        raise HTTPException(
            status_code=404, detail="Sem curva de potência para esta atividade"
        )
    return curve


@router.get("/{activity_id}/zones")
def get_activity_zones(activity_id: str, db=Depends(get_db)):
    """Retorna distribuição de tempo em zonas de potência Coggan para uma atividade."""
    ftp = _resolve_ftp(db, activity_id)

    rows = db.execute(
        """
        SELECT power_w FROM activity_streams
        WHERE activity_id = ? AND power_w IS NOT NULL
        ORDER BY time_s
        """,
        [activity_id],
    ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404, detail="Sem dados de potência para esta atividade"
        )

    streams = [ActivityStream(time_s=i, power_w=r[0]) for i, r in enumerate(rows)]
    zones = ZoneAnalyzer(ftp).time_in_zones(streams)

    total = sum(zones.values()) or 1
    return {
        z: {"seconds": v, "pct": round(v / total * 100, 1)}
        for z, v in zones.items()
        if v > 0
    }


@router.post("/ingest/fit", status_code=201)
def ingest_fit(file: UploadFile = File(...), db=Depends(get_db)):
    """Recebe arquivo .FIT, parseia e persiste atividade + recalcula PMC."""
    from analytics.pmc_calculator import PMCCalculator

    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        activity_id = IngestionPipeline(db).ingest_fit(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    PMCCalculator().run_and_store(CatalogStore(db), date.today())
    return {"activity_id": activity_id}


def _resolve_ftp(db, activity_id: str) -> float:
    """Resolve o FTP a usar nas zonas, do mais específico ao mais genérico.

    Args:
        db: conexão DuckDB.
        activity_id: atividade em análise.

    Returns:
        FTP em watts: o do atleta quando cadastrado; senão 105% da potência
        média da atividade; senão o padrão de 200 W.
    """
    row = db.execute(
        "SELECT ftp_w FROM athletes WHERE ftp_w IS NOT NULL ORDER BY created_at LIMIT 1"
    ).fetchone()
    if row and row[0]:
        return float(row[0])

    row = db.execute(
        "SELECT avg_power_w FROM activities WHERE id = ?", [activity_id]
    ).fetchone()
    if row and row[0]:
        return float(row[0]) * 1.05

    return DEFAULT_FTP_W
