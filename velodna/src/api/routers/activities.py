"""
Router: /activities — upload, listagem e streams de atividades.
"""
from __future__ import annotations

import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.analytics.zone_analyzer import ZoneAnalyzer
from src.api.dependencies import get_db
from src.ingestion.catalog_store import CatalogStore
from src.ingestion.fit_parser import ActivityStream
from src.ingestion.pipeline import IngestionPipeline

router = APIRouter()


@router.get("/")
def list_activities(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db=Depends(get_db),
):
    """Retorna lista de atividades com filtro opcional por intervalo de datas."""
    return CatalogStore(db).get_activities(start, end)


@router.get("/latest")
def get_latest_activity(db=Depends(get_db)):
    """Retorna a atividade mais recente."""
    rows = db.execute(
        "SELECT * FROM activities ORDER BY start_time DESC LIMIT 1"
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Nenhuma atividade encontrada")
    cols = [d[0] for d in db.description]
    return dict(zip(cols, rows[0]))


@router.get("/{activity_id}/streams")
def get_activity_streams(activity_id: str, every_n: int = 10, db=Depends(get_db)):
    """
    Retorna streams GPS de uma atividade decimados a cada N pontos.
    every_n=10 retorna ~1 ponto a cada 10 segundos — suficiente para o mapa.
    """
    rows = db.execute(
        """
        SELECT lat, lon, altitude_m, power_w, heart_rate_bpm, speed_ms
        FROM activity_streams
        WHERE activity_id = ?
          AND lat IS NOT NULL
          AND lon IS NOT NULL
        ORDER BY stream_id
        """,
        [activity_id],
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Nenhum stream GPS para esta atividade")

    cols = ["lat", "lon", "altitude_m", "power_w", "heart_rate_bpm", "speed_ms"]
    decimated = rows[::every_n]
    return [dict(zip(cols, r)) for r in decimated]


@router.get("/{activity_id}/zones")
def get_activity_zones(activity_id: str, db=Depends(get_db)):
    """Retorna distribuição de tempo em zonas de potência Coggan para uma atividade."""
    # Busca FTP mais recente
    ftp_row = db.execute(
        "SELECT ftp_w FROM athlete_metrics WHERE ftp_w IS NOT NULL ORDER BY date DESC LIMIT 1"
    ).fetchone()
    ftp = float(ftp_row[0]) if ftp_row else 200.0

    # Busca atividade para pegar avg_power como fallback
    act_row = db.execute(
        "SELECT avg_power_w FROM activities WHERE activity_id = ?", [activity_id]
    ).fetchone()
    if act_row and act_row[0] and not ftp_row:
        ftp = float(act_row[0]) * 1.05

    # Busca streams de potência
    rows = db.execute(
        "SELECT power_w FROM activity_streams WHERE activity_id = ? AND power_w IS NOT NULL ORDER BY stream_id",
        [activity_id],
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Sem dados de potência para esta atividade")

    from datetime import datetime as _dt
    streams = [ActivityStream(timestamp=_dt.utcnow(), power_w=r[0]) for r in rows]
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
    from src.analytics.pmc_calculator import PMCCalculator

    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    store = CatalogStore(db)
    activity_id = IngestionPipeline(db).ingest_fit(tmp_path)
    tmp_path.unlink(missing_ok=True)

    # Estima TSS se activity não tem potência suficiente
    db.execute("""
        UPDATE activities SET tss = ROUND((duration_s/3600.0)*POWER(avg_power_w/200.0,2)*100, 1)
        WHERE activity_id = ? AND tss IS NULL AND avg_power_w IS NOT NULL
    """, [activity_id])
    db.execute("""
        UPDATE activities SET tss = ROUND(duration_s/3600.0*45, 1)
        WHERE activity_id = ? AND tss IS NULL
    """, [activity_id])

    PMCCalculator().run_and_store(store, date.today())
    return {"activity_id": activity_id}
