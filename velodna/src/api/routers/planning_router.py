"""
Router: /calendar e /planning — treinos planejados e projeção de carga.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_athlete_id, get_db
from planning.calendar import build_calendar, create_planned_workout, reconcile
from planning.projection import (
    build_flat_plan,
    project,
    required_daily_tss,
    summarize,
)

router = APIRouter()

DEFAULT_CALENDAR_DAYS = 28
DEFAULT_PROJECTION_DAYS = 42


class PlannedWorkoutRequest(BaseModel):
    date: date
    name: Optional[str] = None
    sport_type: str = "cycling"
    planned_tss: Optional[float] = None
    planned_duration_s: Optional[int] = None
    planned_if: Optional[float] = None
    description: Optional[str] = None


class ProjectionRequest(BaseModel):
    days: int = DEFAULT_PROJECTION_DAYS
    weekly_tss: Optional[float] = None
    target_ctl: Optional[float] = None
    rest_days: Optional[list[int]] = None


def _current_load(db, athlete_id: str) -> tuple[float, float]:
    """Retorna o CTL e o ATL mais recentes do atleta.

    Args:
        db: conexão DuckDB.
        athlete_id: UUID do atleta.

    Returns:
        Par (ctl, atl); zeros quando não há série de carga.
    """
    row = db.execute(
        """
        SELECT ctl, atl FROM training_load
        WHERE athlete_id = ? ORDER BY date DESC LIMIT 1
        """,
        [athlete_id],
    ).fetchone()
    return (float(row[0] or 0), float(row[1] or 0)) if row else (0.0, 0.0)


def _require_athlete(db) -> str:
    athlete_id = get_athlete_id(db)
    if athlete_id is None:
        raise HTTPException(status_code=404, detail="Nenhum atleta cadastrado")
    return athlete_id


@router.get("/calendar")
def get_calendar(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db=Depends(get_db),
):
    """Calendário com planejado e realizado lado a lado, dia a dia."""
    athlete_id = _require_athlete(db)
    start = start or date.today() - timedelta(days=DEFAULT_CALENDAR_DAYS // 2)
    end = end or start + timedelta(days=DEFAULT_CALENDAR_DAYS)

    days = build_calendar(db, athlete_id, start, end)
    return {
        "start": str(start),
        "end": str(end),
        "planned_tss": round(sum(d.planned_tss for d in days), 1),
        "actual_tss": round(sum(d.actual_tss for d in days), 1),
        "days": [
            {
                "date": str(d.date),
                "planned_tss": d.planned_tss,
                "actual_tss": d.actual_tss,
                "compliance_pct": d.compliance_pct,
                "status": d.status,
                "planned_workouts": d.planned_workouts,
                "activities": d.activities,
            }
            for d in days
        ],
    }


@router.post("/planning/workouts", status_code=201)
def add_planned_workout(req: PlannedWorkoutRequest, db=Depends(get_db)):
    """Cria um treino planejado no calendário."""
    athlete_id = _require_athlete(db)
    workout_id = create_planned_workout(db, athlete_id, req.model_dump())
    return {"id": workout_id}


@router.delete("/planning/workouts/{workout_id}", status_code=204)
def delete_planned_workout(workout_id: str, db=Depends(get_db)):
    """Remove um treino planejado."""
    db.execute("DELETE FROM planned_workouts WHERE id = ?", [workout_id])


@router.post("/planning/reconcile")
def reconcile_calendar(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db=Depends(get_db),
):
    """Liga treinos planejados às atividades executadas no mesmo dia."""
    athlete_id = _require_athlete(db)
    start = start or date.today() - timedelta(days=DEFAULT_CALENDAR_DAYS)
    end = end or date.today()
    return {"reconciled": reconcile(db, athlete_id, start, end)}


@router.post("/planning/projection")
def project_load(req: ProjectionRequest, db=Depends(get_db)):
    """Projeta CTL/ATL/TSB a partir de uma carga semanal ou de um CTL alvo.

    Informe `weekly_tss` para saber onde a carga leva, ou `target_ctl` para
    descobrir quanta carga o alvo exige. O resultado traz o ritmo de rampa,
    para ser confrontado com o limite seguro.
    """
    athlete_id = _require_athlete(db)
    ctl, atl = _current_load(db, athlete_id)

    if req.target_ctl is not None and req.weekly_tss is None:
        daily = required_daily_tss(ctl, req.target_ctl, req.days)
        if daily is None:
            raise HTTPException(
                status_code=422,
                detail="Alvo de CTL inalcançável no prazo informado",
            )
        weekly_tss = daily * 7
    elif req.weekly_tss is not None:
        weekly_tss = req.weekly_tss
    else:
        raise HTTPException(
            status_code=422, detail="Informe weekly_tss ou target_ctl"
        )

    start = date.today() + timedelta(days=1)
    plan = build_flat_plan(
        start, req.days, weekly_tss, set(req.rest_days or [])
    )
    projection = project(ctl, atl, plan)

    return {
        "current_ctl": round(ctl, 1),
        "current_atl": round(atl, 1),
        "weekly_tss": round(weekly_tss, 1),
        "rest_days": req.rest_days or [],
        "summary": summarize(projection),
        "days": [
            {
                "date": str(d.date),
                "daily_tss": d.daily_tss,
                "ctl": d.ctl,
                "atl": d.atl,
                "tsb": d.tsb,
            }
            for d in projection
        ],
    }


@router.post("/planning/projection/from-plan")
def project_from_planned_workouts(
    days: int = DEFAULT_PROJECTION_DAYS,
    db=Depends(get_db),
):
    """Projeta a carga usando os treinos já planejados no calendário."""
    athlete_id = _require_athlete(db)
    ctl, atl = _current_load(db, athlete_id)

    start = date.today() + timedelta(days=1)
    end = start + timedelta(days=days - 1)

    rows = db.execute(
        """
        SELECT date, COALESCE(SUM(planned_tss), 0)
        FROM planned_workouts
        WHERE athlete_id = ? AND date BETWEEN ? AND ?
        GROUP BY date
        """,
        [athlete_id, start, end],
    ).fetchall()
    planned = {row[0]: float(row[1]) for row in rows}

    plan = {
        start + timedelta(days=offset): planned.get(
            start + timedelta(days=offset), 0.0
        )
        for offset in range(days)
    }
    projection = project(ctl, atl, plan)

    return {
        "current_ctl": round(ctl, 1),
        "planned_days": len(planned),
        "summary": summarize(projection),
        "days": [
            {"date": str(d.date), "daily_tss": d.daily_tss, "ctl": d.ctl,
             "atl": d.atl, "tsb": d.tsb}
            for d in projection
        ],
    }
