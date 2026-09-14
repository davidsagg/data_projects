"""
Router: /coach — análise de atividade, plano semanal, nutrição e risco de lesão.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai.injury_risk_coach import InjuryRiskCoach
from ai.ollama_client import OllamaClient, OllamaUnavailableError
from ai.post_activity_coach import PostActivityCoach
from ai.weekly_plan_coach import WeeklyPlanCoach
from api.query import rows as query_rows
from api.dependencies import get_db
from storage.models import Activity

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
    row = db.execute(
        """
        SELECT garmin_id, sport_type, started_at, elapsed_time_s, distance_m,
               elevation_gain_m, avg_power_w, normalized_power_w, tss,
               intensity_factor
        FROM activities WHERE id = ?
        """,
        [req.activity_id],
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")

    act_obj = Activity(
        source="fit",
        garmin_id=row[0],
        sport_type=row[1] or "cycling",
        started_at=row[2],
        elapsed_time_s=row[3] or 0,
        distance_m=row[4] or 0.0,
        elevation_gain_m=row[5] or 0.0,
        avg_power_w=row[6],
        normalized_power_w=row[7],
        tss=row[8],
        intensity_factor=row[9],
    )

    row = db.execute(
        "SELECT ctl, atl, tsb FROM training_load ORDER BY date DESC LIMIT 1"
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
        "SELECT ctl, atl, tsb FROM training_load ORDER BY date DESC LIMIT 1"
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


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


@router.post("/chat")
def chat(req: ChatRequest, db=Depends(get_db)):
    """Conversa livre com o coach, com o estado do atleta como contexto (US-14).

    O histórico da sessão é persistido e reenviado a cada turno: o endpoint de
    geração do Ollama não guarda estado entre chamadas.
    """
    from ai.chat_coach import (
        ChatCoach,
        ChatTurn,
        build_athlete_context,
        new_session_id,
    )
    from api.dependencies import get_athlete_id

    athlete_id = get_athlete_id(db)
    if athlete_id is None:
        raise HTTPException(status_code=404, detail="Nenhum atleta cadastrado")

    session_id = req.session_id or new_session_id()

    history = [
        ChatTurn(role=row[0], content=row[1])
        for row in db.execute(
            """
            SELECT role, content FROM ai_conversations
            WHERE session_id = ? ORDER BY created_at
            """,
            [session_id],
        ).fetchall()
    ]

    context = build_athlete_context(db, athlete_id)
    try:
        answer = ChatCoach(OllamaClient()).answer(req.question, context, history)
    except OllamaUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

    db.executemany(
        """
        INSERT INTO ai_conversations (id, athlete_id, session_id, role, content, model)
        VALUES (?, ?, ?, ?, ?, 'llama3')
        """,
        [
            (str(uuid.uuid4()), athlete_id, session_id, "user", req.question),
            (str(uuid.uuid4()), athlete_id, session_id, "assistant", answer),
        ],
    )

    return {"session_id": session_id, "answer": answer, "turns": len(history) + 2}


@router.get("/chat/{session_id}")
def get_chat_history(session_id: str, db=Depends(get_db)):
    """Histórico de uma sessão de conversa."""
    return query_rows(
        db,
        """
        SELECT role, content, created_at FROM ai_conversations
        WHERE session_id = ? ORDER BY created_at
        """,
        [session_id],
    )


@router.get("/chat-sessions")
def list_chat_sessions(db=Depends(get_db)):
    """Sessões de conversa, da mais recente para a mais antiga."""
    return query_rows(
        db,
        """
        SELECT session_id,
               MIN(created_at) AS started_at,
               MAX(created_at) AS last_message_at,
               COUNT(*)        AS turns,
               MIN(CASE WHEN role = 'user' THEN content END) AS first_question
        FROM ai_conversations
        GROUP BY session_id
        ORDER BY last_message_at DESC
        LIMIT 30
        """,
    )


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
        "SELECT tsb FROM training_load ORDER BY date DESC LIMIT 1"
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
            "WHERE CAST(started_at AS DATE) BETWEEN ? AND ? AND tss IS NOT NULL",
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
