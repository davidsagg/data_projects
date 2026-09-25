"""
Router: análise avançada de treino — semana executada, intervalos, W'bal e
durabilidade.

São as quatro leituras que o resumo de atividade não dá. A semana porque é a
unidade real de periodização; os intervalos porque a estrutura de um treino
some na média; o W'bal porque mostra quanto tanque sobrou em cada ataque; a
durabilidade porque o FTP medido descansado não diz o que resta depois de
2.000 kJ.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from analytics.capacity import build_profile
from analytics.climbs import detect_climbs, summarize_climbs
from analytics.durability import DEFAULT_KJ_THRESHOLD, compute_durability
from analytics.ftp_history import ftp_on
from analytics.intervals import (
    DEFAULT_THRESHOLD_RATIO,
    MIN_INTERVAL_S,
    detect_intervals,
    group_into_sets,
)
from analytics.pacing_analysis import analyze_pacing, load_density
from analytics.recommendation import recommend
from analytics.timeseries import load_series
from analytics.weekly import build_week_series, build_week_summary
from analytics.wprime_model import WPrimeModel
from analytics.zones import build_power_zones
from api.dependencies import get_athlete_id, get_db
from api.query import row as query_row
from api.query import rows as query_rows
from storage.catalog_store import CatalogStore

router = APIRouter()

# Quantos pontos do balanço de W' cabem numa resposta sem pesar no gráfico.
WBAL_TARGET_POINTS = 900


def _athlete_or_404(db) -> str:
    athlete_id = get_athlete_id(db)
    if not athlete_id:
        raise HTTPException(404, "Nenhum atleta cadastrado")
    return athlete_id


def _activity_or_404(db, activity_id: str) -> dict:
    activity = query_row(
        db,
        "SELECT id, athlete_id, CAST(started_at AS DATE) AS date, sport_type "
        "FROM activities WHERE id = ?",
        [activity_id],
    )
    if not activity:
        raise HTTPException(404, "Atividade não encontrada")
    return activity


# ---------------------------------------------------------------------------
# Semana executada
# ---------------------------------------------------------------------------


@router.get("/week")
def get_week(
    reference: Optional[date] = None,
    zones: bool = True,
    db=Depends(get_db),
):
    """Resumo da semana que contém a data informada (padrão: hoje).

    A semana vai de segunda a domingo — a unidade com que se periodiza. Além do
    volume, devolve a distribuição de intensidade e o veredito de polarização.

    Args:
        reference: qualquer dia da semana desejada.
        zones: calcular o tempo em zona; desligue para uma resposta rápida.
    """
    store = CatalogStore(db)
    athlete_id = _athlete_or_404(db)
    summary = build_week_summary(
        store, athlete_id, reference or date.today(), with_zones=zones
    )
    return summary.to_dict()


@router.get("/weeks")
def get_weeks(
    weeks: int = 12,
    reference: Optional[date] = None,
    zones: bool = False,
    db=Depends(get_db),
):
    """Série das últimas N semanas, da mais antiga para a mais recente.

    Args:
        weeks: quantas semanas incluir (máximo 52).
        reference: semana final; usa hoje se omitido.
        zones: calcular tempo em zona de cada semana — bem mais lento.
    """
    store = CatalogStore(db)
    athlete_id = _athlete_or_404(db)
    series = build_week_series(
        store, athlete_id, weeks=min(weeks, 52), reference=reference, with_zones=zones
    )
    return [week.to_dict() for week in series]


# ---------------------------------------------------------------------------
# Intervalos
# ---------------------------------------------------------------------------


@router.get("/activities/{activity_id}/intervals")
def get_intervals(
    activity_id: str,
    threshold: float = DEFAULT_THRESHOLD_RATIO,
    min_duration: int = MIN_INTERVAL_S,
    db=Depends(get_db),
):
    """Estrutura de esforços de uma atividade, agrupada em séries.

    Args:
        activity_id: UUID da atividade.
        threshold: fração do FTP que separa esforço de recuperação.
        min_duration: duração mínima, em segundos, para contar como intervalo.
    """
    store = CatalogStore(db)
    activity = _activity_or_404(db, activity_id)

    ftp = ftp_on(store, activity["athlete_id"], activity["date"])
    series = load_series(db, activity_id)
    intervals = detect_intervals(series, ftp, threshold, min_duration)

    return {
        "activity_id": activity_id,
        "ftp_w_at_time": ftp,
        "threshold_w": round(ftp * threshold, 1) if ftp else None,
        "interval_count": len(intervals),
        "sets": [
            {
                "count": s.count,
                "label": s.label(ftp),
                "avg_duration_s": s.avg_duration_s,
                "avg_power_w": s.avg_power_w,
                "avg_recovery_s": s.avg_recovery_s,
            }
            for s in group_into_sets(intervals)
        ],
        "intervals": [
            {**asdict(i), "intensity_factor": i.intensity_factor(ftp), "end_s": i.end_s}
            for i in intervals
        ],
    }


# ---------------------------------------------------------------------------
# W'bal
# ---------------------------------------------------------------------------


@router.get("/activities/{activity_id}/wbal")
def get_wbal(
    activity_id: str,
    cp: Optional[float] = None,
    w_prime: Optional[float] = None,
    db=Depends(get_db),
):
    """Balanço da reserva anaeróbica ao longo da atividade.

    CP e W' vêm do teste mais recente registrado antes da atividade; podem ser
    sobrescritos pelos parâmetros para simulação.

    Args:
        activity_id: UUID da atividade.
        cp: potência crítica, em watts.
        w_prime: reserva anaeróbica, em joules.
    """
    activity = _activity_or_404(db, activity_id)

    if cp is None or w_prime is None:
        measured = _critical_power_for(db, activity["athlete_id"], activity["date"])
        cp = cp if cp is not None else measured[0]
        w_prime = w_prime if w_prime is not None else measured[1]

    if not cp or not w_prime:
        raise HTTPException(
            422,
            "Sem CP e W' para esta data. Registre um teste de potência crítica "
            "com scripts/set_athlete_profile.py --cp-test, ou informe cp e w_prime.",
        )

    series = load_series(db, activity_id)
    if not series.has_data("power"):
        raise HTTPException(422, "Atividade sem dados de potência")

    result = WPrimeModel(w_prime, cp).compute(series)

    return {
        "activity_id": activity_id,
        "cp_w": result.cp_w,
        "w_prime_j": result.w_prime_j,
        "tau_s": round(result.tau_s, 1),
        "min_balance_j": round(result.min_balance_j, 1),
        "depletion_pct": result.depletion_pct,
        "matches_burned": result.matches_burned,
        "balance": _decimate(result.balance_j, WBAL_TARGET_POINTS),
    }


# ---------------------------------------------------------------------------
# Durabilidade
# ---------------------------------------------------------------------------


@router.get("/activities/{activity_id}/durability")
def get_durability(
    activity_id: str,
    kj: float = DEFAULT_KJ_THRESHOLD,
    db=Depends(get_db),
):
    """Quanto da capacidade sobrou depois do trabalho acumulado.

    Args:
        activity_id: UUID da atividade.
        kj: limiar de trabalho acumulado que define o corte.
    """
    _activity_or_404(db, activity_id)
    series = load_series(db, activity_id)
    result = compute_durability(series, kj_threshold=kj)

    return {
        "activity_id": activity_id,
        "kj_threshold": result.kj_threshold,
        "total_kj": result.total_kj,
        "split_time_s": result.split_time_s,
        "is_conclusive": result.is_conclusive,
        "verdict": result.verdict,
        "ef_before": result.ef_before,
        "ef_after": result.ef_after,
        "ef_change_pct": result.ef_change_pct,
        "points": [
            {
                "duration_s": p.duration_s,
                "before_w": p.before_w,
                "after_w": p.after_w,
                "change_pct": p.change_pct,
            }
            for p in result.points
        ],
    }


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _critical_power_for(db, athlete_id: str, target: date):
    """Busca CP e W' do teste mais recente anterior à data."""
    found = query_row(
        db,
        """
        SELECT cp_w, w_prime_j FROM ftp_history
        WHERE athlete_id = ? AND effective_from <= ?
          AND cp_w IS NOT NULL AND w_prime_j IS NOT NULL
        ORDER BY effective_from DESC LIMIT 1
        """,
        [athlete_id, target],
    )
    return (found["cp_w"], found["w_prime_j"]) if found else (None, None)


def _decimate(values: list[float], target: int) -> list[float]:
    """Reduz a série para caber no gráfico, preservando início e fim."""
    if len(values) <= target:
        return [round(v, 1) for v in values]
    step = len(values) / target
    return [round(values[int(i * step)], 1) for i in range(target)]


@router.get("/today")
def get_today(db=Depends(get_db)):
    """Painel do dia: prontidão, forma, semana em curso e o que ela sugere.

    Junta num só lugar os sinais que estavam espalhados por quatro telas. A
    recomendação vem com os sinais que a produziram — recomendação sem os
    sinais à vista é palpite com cara de resultado.
    """
    store = CatalogStore(db)
    athlete_id = _athlete_or_404(db)

    pmc = query_rows(
        db,
        """
        SELECT date, ctl, atl, tsb, daily_tss FROM training_load
        WHERE athlete_id = ? ORDER BY date DESC LIMIT 90
        """,
        [athlete_id],
    )
    pmc.reverse()
    latest = pmc[-1] if pmc else {}

    week = build_week_summary(store, athlete_id, date.today(), with_zones=False)
    readiness = _readiness_today(db, athlete_id)
    profile = _capacity_limiters(db, athlete_id)

    advice = recommend(
        readiness=readiness.get("score") if readiness else None,
        tsb=latest.get("tsb"),
        ctl=latest.get("ctl"),
        week_tss=week.total_tss,
        baseline_weekly_tss=week.baseline_tss,
        limiters=profile,
    )

    return {
        "date": date.today().isoformat(),
        "readiness": readiness,
        "form": {
            "ctl": latest.get("ctl"),
            "atl": latest.get("atl"),
            "tsb": latest.get("tsb"),
        },
        "pmc": pmc,
        "week": {
            "total_tss": week.total_tss,
            "baseline_tss": week.baseline_tss,
            "session_count": week.session_count,
            "total_km": week.total_km,
            "days": [d.to_dict() for d in week.days],
        },
        "recommendation": advice.to_dict(),
    }


def _readiness_today(db, athlete_id: str) -> dict | None:
    """Prontidão de hoje, com as medidas que a compuseram.

    Reusa `ReadinessCalculator` pela mesma porta que `/readiness/today` usa —
    duplicar a fórmula aqui faria as duas telas divergirem no dia em que uma
    delas fosse ajustada.
    """
    from health.readiness import ReadinessCalculator
    from ingestion.garmin_health_client import HealthDaily

    today = date.today()
    metrics = query_row(
        db,
        """
        SELECT date, hrv_rmssd_ms, resting_hr_bpm, sleep_hours, body_battery,
               sleep_quality_score, stress_level
        FROM health_metrics WHERE athlete_id = ? ORDER BY date DESC LIMIT 1
        """,
        [athlete_id],
    )
    if not metrics:
        return None

    load = query_row(db, "SELECT tsb FROM training_load WHERE date = ?", [today])

    health = HealthDaily(
        date=today,
        sleep_score=metrics.get("sleep_quality_score"),
        hrv_rmssd_ms=metrics.get("hrv_rmssd_ms"),
        body_battery_max=metrics.get("body_battery"),
    )
    score = ReadinessCalculator().calculate(
        health, {"tsb": float(load["tsb"]) if load and load.get("tsb") else 0.0}
    )

    return {
        "score": score,
        "recommendation": ReadinessCalculator().get_recommendation(score),
        "measured_on": metrics["date"].isoformat(),
        "is_stale": (today - metrics["date"]).days > 1,
        "hrv_rmssd_ms": metrics.get("hrv_rmssd_ms"),
        "resting_hr_bpm": metrics.get("resting_hr_bpm"),
        "sleep_hours": metrics.get("sleep_hours"),
        "sleep_quality_score": metrics.get("sleep_quality_score"),
        "body_battery": metrics.get("body_battery"),
    }


def _capacity_limiters(db, athlete_id: str) -> list[str]:
    """Durações em que o atleta está mais abaixo do próprio recorde."""
    end = date.today()
    recent = _aggregate_curve(db, athlete_id, end - timedelta(days=90), end, "cycling")
    best = _aggregate_curve(db, athlete_id, None, None, "cycling")
    return build_profile(recent, best)["limiters"]


# ---------------------------------------------------------------------------
# Subidas
# ---------------------------------------------------------------------------


@router.get("/activities/{activity_id}/climbs")
def get_climbs(
    activity_id: str,
    min_gain: float = 30.0,
    min_gradient: float = 3.0,
    db=Depends(get_db),
):
    """Subidas da atividade, com VAM, inclinação e potência de cada uma.

    Num pedal de montanha a média da atividade não descreve nada — o que
    descreve é o que aconteceu subindo.

    Args:
        activity_id: UUID da atividade.
        min_gain: ganho mínimo de elevação, em metros.
        min_gradient: inclinação média mínima, em percentual.
    """
    _activity_or_404(db, activity_id)

    weight = query_row(
        db,
        "SELECT weight_kg FROM athletes WHERE id = ?",
        [get_athlete_id(db)],
    )
    weight_kg = weight["weight_kg"] if weight else None

    series = load_series(db, activity_id)
    climbs = detect_climbs(series, min_gain, min_gradient)

    return {
        "activity_id": activity_id,
        "summary": summarize_climbs(climbs),
        "climbs": [
            {
                **asdict(climb),
                "end_s": climb.end_s,
                "category": climb.category(),
                "watts_per_kg": climb.watts_per_kg(weight_kg),
            }
            for climb in climbs
        ],
    }


# ---------------------------------------------------------------------------
# Execução e densidade de carga
# ---------------------------------------------------------------------------


@router.get("/activities/{activity_id}/pacing")
def get_pacing(activity_id: str, db=Depends(get_db)):
    """Distribuição de intensidade por quarto do esforço.

    Revela o erro mais comum de prova: sair forte demais. Se o primeiro quarto
    está nas zonas altas e o último desabou, a leitura é imediata.
    """
    store = CatalogStore(db)
    activity = _activity_or_404(db, activity_id)

    ftp = ftp_on(store, activity["athlete_id"], activity["date"])
    if not ftp:
        raise HTTPException(422, "Sem FTP vigente para esta data")

    series = load_series(db, activity_id)
    if not series.has_data("power"):
        raise HTTPException(422, "Atividade sem dados de potência")

    return {
        "activity_id": activity_id,
        "ftp_w_at_time": ftp,
        **analyze_pacing(series, build_power_zones(ftp)),
    }


@router.get("/activities/{activity_id}/load-density")
def get_load_density(
    activity_id: str,
    power_bin: int = 25,
    hr_bin: int = 5,
    db=Depends(get_db),
):
    """Densidade conjunta de potência (carga externa) e FC (carga interna).

    A nuvem inteira se desloca para cima e para a esquerda quando há ganho de
    base: a mesma potência passa a custar menos batimentos.
    """
    _activity_or_404(db, activity_id)
    series = load_series(db, activity_id)
    return {"activity_id": activity_id, **load_density(series, power_bin, hr_bin)}


# ---------------------------------------------------------------------------
# Perfil de capacidade
# ---------------------------------------------------------------------------


@router.get("/capacity-profile")
def get_capacity_profile(
    days: int = 90,
    sport: str = "cycling",
    db=Depends(get_db),
):
    """Forças e limitadores por duração, contra o melhor histórico do atleta.

    A referência é o próprio atleta, não uma tabela populacional: percentis
    dependem de peso, idade e categoria, e erram feio no indivíduo.

    Args:
        days: janela recente a comparar.
        sport: esporte a filtrar; corrida tem outra escala de potência.
    """
    athlete_id = _athlete_or_404(db)
    end = date.today()
    start = end - timedelta(days=days)

    recent = _aggregate_curve(db, athlete_id, start, end, sport)
    best = _aggregate_curve(db, athlete_id, None, None, sport)

    return {
        "window_days": days,
        "sport": sport,
        "start": start.isoformat(),
        "end": end.isoformat(),
        **build_profile(recent, best),
    }


def _aggregate_curve(
    db,
    athlete_id: str,
    start: date | None,
    end: date | None,
    sport: str,
) -> dict[int, float]:
    """Melhor potência por duração no período, a partir das curvas persistidas."""
    rows_found = query_rows(
        db,
        """
        SELECT pc.duration_s, max(pc.power_w) AS power_w
        FROM power_curves pc
        JOIN activities a ON a.id = pc.activity_id
        WHERE a.athlete_id = ?
          AND a.sport_type = ?
          AND (? IS NULL OR pc.date >= ?)
          AND (? IS NULL OR pc.date <= ?)
        GROUP BY pc.duration_s
        """,
        [athlete_id, sport, start, start, end, end],
    )
    return {int(r["duration_s"]): float(r["power_w"]) for r in rows_found}


# ---------------------------------------------------------------------------
# Feedback subjetivo
# ---------------------------------------------------------------------------


class FeedbackIn(BaseModel):
    """Feedback do atleta sobre um treino ou sobre o dia.

    Todos os campos são opcionais: gravar só o RPE é um caso legítimo, e o
    upsert preserva o que já estava lá. `activity_id` nulo significa nota do
    dia, que é como um dia de descanso entra no registro.
    """

    date: date
    activity_id: Optional[str] = None
    rpe: Optional[int] = Field(None, ge=1, le=10, description="Borg CR10")
    feel: Optional[int] = Field(None, ge=1, le=5, description="1 péssimo, 5 ótimo")
    soreness: Optional[int] = Field(None, ge=1, le=5)
    motivation: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None


@router.get("/feedback")
def list_feedback(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db=Depends(get_db),
):
    """Feedback registrado no período.

    Args:
        start: primeiro dia; padrão é 90 dias atrás.
        end: último dia; padrão é hoje.
    """
    store = CatalogStore(db)
    athlete_id = _athlete_or_404(db)
    end = end or date.today()
    start = start or (end - timedelta(days=90))
    return store.get_feedback(athlete_id, start, end)


@router.get("/activities/{activity_id}/feedback")
def get_feedback(activity_id: str, db=Depends(get_db)):
    """Feedback de uma atividade, ou `null` se ainda não houver."""
    _activity_or_404(db, activity_id)
    return CatalogStore(db).get_activity_feedback(activity_id)


@router.put("/feedback")
def put_feedback(payload: FeedbackIn, db=Depends(get_db)):
    """Grava ou atualiza o feedback de um treino ou de um dia.

    Idempotente por (atleta, data, atividade): reenviar o mesmo corpo não cria
    duplicata, e campos omitidos preservam o valor anterior.
    """
    store = CatalogStore(db)
    athlete_id = _athlete_or_404(db)

    if payload.activity_id:
        _activity_or_404(db, payload.activity_id)

    try:
        feedback_id = store.upsert_feedback(
            athlete_id,
            payload.date,
            payload.activity_id,
            rpe=payload.rpe,
            feel=payload.feel,
            soreness=payload.soreness,
            motivation=payload.motivation,
            notes=payload.notes,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    return {"id": feedback_id, "date": payload.date.isoformat()}


@router.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: str, db=Depends(get_db)):
    """Remove um registro de feedback."""
    CatalogStore(db).delete_feedback(feedback_id)
    return {"deleted": feedback_id}
