"""
Router: panorama do ciclo, metas do atleta e marcos (exames, planos, provas).

O panorama é a leitura de 13 semanas contra as metas; metas e marcos são as duas
fontes de contexto que não vêm de sensor e sem as quais o panorama seria só um
histórico.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from analytics.goals import GOAL_SPECS
from analytics.panorama import DEFAULT_WEEKS, build_panorama
from api.dependencies import get_athlete_id, get_db
from storage.catalog_store import CatalogStore

router = APIRouter()


def _athlete_or_404(db) -> str:
    athlete_id = get_athlete_id(db)
    if not athlete_id:
        raise HTTPException(404, "Nenhum atleta cadastrado")
    return athlete_id


@router.get("/panorama")
def get_panorama(
    weeks: int = DEFAULT_WEEKS,
    reference: Optional[date] = None,
    zones: bool = True,
    db=Depends(get_db),
):
    """Panorama das últimas N semanas: atleta, metas, volume, zonas e marcos."""
    if not 1 <= weeks <= 52:
        raise HTTPException(422, "weeks deve estar entre 1 e 52")
    athlete_id = _athlete_or_404(db)
    return build_panorama(
        CatalogStore(db), athlete_id, weeks=weeks, reference=reference, with_zones=zones
    )


# ---------------------------------------------------------------------------
# Metas
# ---------------------------------------------------------------------------


class GoalIn(BaseModel):
    metric: Literal["weight_kg", "weekly_hours", "ftp_w", "w_per_kg", "ctl"]
    target: float = Field(gt=0)
    target_date: Optional[date] = None
    notes: Optional[str] = None


@router.get("/goals")
def get_goals(db=Depends(get_db)):
    """Metas cadastradas, cada uma lida contra o valor atual."""
    athlete_id = _athlete_or_404(db)
    return build_panorama(CatalogStore(db), athlete_id, with_zones=False)["goals"]


@router.get("/goals/metrics")
def get_goal_metrics():
    """Métricas que aceitam meta, com rótulo, unidade e sentido."""
    return [{"metric": key, **spec} for key, spec in GOAL_SPECS.items()]


@router.put("/goals")
def put_goal(goal: GoalIn, db=Depends(get_db)):
    """Cria ou substitui a meta de uma métrica."""
    athlete_id = _athlete_or_404(db)
    CatalogStore(db).set_goal(
        athlete_id, goal.metric, goal.target, goal.target_date, goal.notes
    )
    return {"metric": goal.metric, "target": goal.target}


@router.delete("/goals/{metric}")
def delete_goal(metric: str, db=Depends(get_db)):
    """Remove a meta de uma métrica."""
    athlete_id = _athlete_or_404(db)
    CatalogStore(db).delete_goal(athlete_id, metric)
    return {"deleted": metric}


# ---------------------------------------------------------------------------
# Marcos
# ---------------------------------------------------------------------------


class MilestoneIn(BaseModel):
    date: date
    kind: Literal["exame", "plano", "prova", "achado"]
    title: str = Field(min_length=1, max_length=200)
    summary: Optional[str] = None
    measurements: dict[str, float] = Field(default_factory=dict)
    source: Optional[str] = None


@router.get("/milestones")
def get_milestones(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db=Depends(get_db),
):
    """Marcos cadastrados no período, do mais antigo ao mais recente."""
    athlete_id = _athlete_or_404(db)
    return [
        {**m, "date": m["date"].isoformat()}
        for m in CatalogStore(db).get_milestones(athlete_id, start, end)
    ]


@router.post("/milestones", status_code=201)
def post_milestone(milestone: MilestoneIn, db=Depends(get_db)):
    """Registra um exame, início de plano, prova ou achado."""
    athlete_id = _athlete_or_404(db)
    milestone_id = CatalogStore(db).add_milestone(
        athlete_id,
        milestone.date,
        milestone.kind,
        milestone.title,
        milestone.summary,
        milestone.measurements or None,
        milestone.source,
    )
    return {"id": milestone_id}


@router.delete("/milestones/{milestone_id}")
def delete_milestone(milestone_id: str, db=Depends(get_db)):
    """Remove um marco."""
    _athlete_or_404(db)
    CatalogStore(db).delete_milestone(milestone_id)
    return {"deleted": milestone_id}
