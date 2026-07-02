"""
Router: /coach — análise de atividade, plano semanal, nutrição e risco de lesão.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.ai.injury_risk_coach import InjuryRiskCoach
from src.ai.ollama_client import OllamaClient, OllamaUnavailableError
from src.ai.post_activity_coach import PostActivityCoach
from src.ai.weekly_plan_coach import WeeklyPlanCoach
from src.api.dependencies import get_db
from src.ingestion.catalog_store import CatalogStore
from src.ingestion.fit_parser import Activity

router = APIRouter()

NUTRITION_DISCLAIMER = (
    "\n\n---\n"
    "⚠️ Aviso: estas recomendações são orientações gerais baseadas em princípios de "
    "nutrição esportiva e não substituem a avaliação de um nutricionista esportivo. "
    "Necessidades individuais variam — consulte um profissional para protocolo personalizado."
)


class AnalyzeActivityRequest(BaseModel):
    activity_id: str


class WeeklyPlanRequest(BaseModel):
    target_tss_week: Optional[float] = None
    available_days: Optional[List[str]] = None


class NutritionAdviceRequest(BaseModel):
    duration_h: float
    tss_estimate: Optional[float] = None
    intensity: Optional[str] = "moderado"


@router.post("/analyze-activity")
def analyze_activity(req: AnalyzeActivityRequest, db=Depends(get_db)):
    """Analisa uma atividade via AI Coach e retorna insights."""
    store = CatalogStore(db)

    activities = store.get_activities()
    act_dict = next(
        (a for a in activities if a.get("activity_id") == req.activity_id), None
    )
    if act_dict is None:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")

    act_obj = Activity(
        garmin_id=act_dict.get("garmin_id") or "",
        sport_type=act_dict.get("sport_type") or "cycling",
        start_time=act_dict.get("start_time"),
        duration_s=act_dict.get("duration_s") or 0,
        distance_m=act_dict.get("distance_m") or 0.0,
        elevation_m=act_dict.get("elevation_m") or 0.0,
        avg_power_w=act_dict.get("avg_power_w"),
    )

    row = db.execute(
        "SELECT ctl, atl, tsb FROM athlete_metrics ORDER BY date DESC LIMIT 1"
    ).fetchone()
    metrics = {"ctl": row[0], "atl": row[1], "tsb": row[2]} if row else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}

    response = PostActivityCoach(OllamaClient()).analyze(act_obj, metrics)
    return {
        "summary": response.summary,
        "highlights": response.highlights,
        "alerts": response.alerts,
        "recommendations": response.recommendations,
    }


@router.post("/weekly-plan")
def create_weekly_plan(req: WeeklyPlanRequest, db=Depends(get_db)):
    """Gera plano de periodização semanal via AI Coach e persiste em ai_insights."""
    row = db.execute(
        "SELECT ctl, atl, tsb FROM athlete_metrics ORDER BY date DESC LIMIT 1"
    ).fetchone()
    metrics = {"ctl": row[0], "atl": row[1], "tsb": row[2]} if row else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}

    try:
        plan_text = WeeklyPlanCoach(OllamaClient()).suggest_week(
            metrics=metrics,
            target_tss_week=req.target_tss_week,
            available_days=req.available_days,
        )
    except OllamaUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

    insight_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO ai_insights (id, insight_type, content, model, created_at)
        VALUES (?, 'weekly_plan', ?, 'llama3', now())
        """,
        [insight_id, plan_text],
    )
    return {"insight_id": insight_id, "plan": plan_text, "metrics": metrics}


@router.post("/nutrition-advice")
def get_nutrition_advice(req: NutritionAdviceRequest, db=Depends(get_db)):
    """Gera recomendação nutricional para um treino longo via Ollama."""
    duration_min = int(req.duration_h * 60)
    tss_text = f"TSS estimado: {req.tss_estimate:.0f}." if req.tss_estimate else ""

    prompt = (
        "Você é um nutricionista esportivo especializado em ciclismo de endurance. "
        "Forneça uma estratégia nutricional prática para o seguinte treino:\n\n"
        f"Duração: {duration_min} minutos ({req.duration_h:.1f}h)\n"
        f"Intensidade: {req.intensity}\n"
        f"{tss_text}\n\n"
        "Inclua:\n"
        "1. Gramas de carboidrato por hora durante o treino\n"
        "2. Janela pré-treino: o que e quando comer antes\n"
        "3. Hidratação estimada (ml/hora)\n"
        "4. Recuperação pós-treino (janela de 30 min)\n\n"
        "Seja específico com quantidades. Responda em português."
    )

    try:
        advice = OllamaClient().generate(prompt)
    except OllamaUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {
        "duration_h": req.duration_h,
        "intensity": req.intensity,
        "advice": advice + NUTRITION_DISCLAIMER,
    }


@router.get("/insights")
def get_insights(type: Optional[str] = None, db=Depends(get_db)):
    """Retorna insights armazenados. Filtra por type (ex: injury_risk, weekly_plan)."""
    if type:
        rows = db.execute(
            "SELECT id, insight_type, content, model, created_at "
            "FROM ai_insights WHERE insight_type = ? ORDER BY created_at DESC LIMIT 20",
            [type],
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, insight_type, content, model, created_at "
            "FROM ai_insights ORDER BY created_at DESC LIMIT 20"
        ).fetchall()

    cols = ["id", "insight_type", "content", "model", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


@router.post("/assess-injury-risk")
def assess_injury_risk(db=Depends(get_db)):
    """Avalia risco de lesão por overuse e persiste o resultado em ai_insights."""
    today = date.today()

    # TSB atual
    metrics_row = db.execute(
        "SELECT tsb FROM athlete_metrics ORDER BY date DESC LIMIT 1"
    ).fetchone()
    tsb = float(metrics_row[0]) if metrics_row else 0.0

    # TSS e distância por semana (últimas 5 semanas)
    tss_by_week: list[float] = []
    dist_by_week: list[float] = []
    for week_offset in range(4, -1, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * week_offset)
        week_end = week_start + timedelta(days=6)
        row = db.execute(
            "SELECT COALESCE(SUM(tss), 0), COALESCE(SUM(distance_m), 0) / 1000.0 "
            "FROM activities "
            "WHERE CAST(start_time AS DATE) BETWEEN ? AND ? AND tss IS NOT NULL",
            [week_start, week_end],
        ).fetchone()
        tss_by_week.append(float(row[0]) if row else 0.0)
        dist_by_week.append(float(row[1]) if row else 0.0)

    coach = InjuryRiskCoach(OllamaClient())
    try:
        factors = coach.assess_factors(tss_by_week, dist_by_week, tsb)
        assessment = coach.generate_assessment(factors)
    except OllamaUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

    insight_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO ai_insights (id, insight_type, content, model, created_at)
        VALUES (?, 'injury_risk', ?, 'llama3', now())
        """,
        [insight_id, assessment],
    )

    return {
        "insight_id": insight_id,
        "risk_level": factors.risk_level,
        "triggered_factors": factors.triggered_factors,
        "assessment": assessment,
        "metrics": {
            "tsb": tsb,
            "ramp_rate_pct": factors.ramp_rate_pct,
            "volume_ratio_pct": factors.volume_ratio_pct,
        },
    }
