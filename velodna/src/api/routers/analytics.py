"""
Router: /pmc e /power-curve — métricas analíticas de treino.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies import get_db

router = APIRouter()


@router.get("/pmc")
def get_pmc(db=Depends(get_db)):
    """Retorna série histórica de CTL/ATL/TSB ordenada por data."""
    rows = db.execute(
        "SELECT date, ctl, atl, tsb, ftp_w FROM athlete_metrics ORDER BY date"
    ).fetchall()
    cols = [d[0] for d in db.description]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/power-curve")
def get_power_curve(db=Depends(get_db)):
    """Retorna curva de potência (MMP) ordenada por duração."""
    rows = db.execute(
        "SELECT * FROM power_curve ORDER BY duration_s"
    ).fetchall()
    cols = [d[0] for d in db.description]
    return [dict(zip(cols, r)) for r in rows]
