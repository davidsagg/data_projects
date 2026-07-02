"""
Router: /health-daily, /readiness/today e /health/alerts — métricas de saúde e recuperação.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from src.api.dependencies import get_db
from src.health.overreaching_alerts import OverreachingAnalyzer
from src.health.readiness import ReadinessCalculator
from src.ingestion.garmin_health_client import HealthDaily

router = APIRouter()


@router.get("/health-daily")
def get_health_daily(days: int = 30, db=Depends(get_db)):
    """Retorna os últimos N registros de saúde ordenados por data decrescente."""
    rows = db.execute(
        "SELECT * FROM health_daily ORDER BY date DESC LIMIT ?",
        [days],
    ).fetchall()
    cols = [d[0] for d in db.description]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/readiness/today")
def get_readiness_today(db=Depends(get_db)):
    """Calcula e retorna o score de recuperação para hoje."""
    today = date.today()

    health_row = db.execute(
        "SELECT sleep_score, hrv_rmssd_ms, body_battery_max "
        "FROM health_daily WHERE date = ?",
        [today],
    ).fetchone()

    metrics_row = db.execute(
        "SELECT tsb FROM athlete_metrics WHERE date = ?",
        [today],
    ).fetchone()

    health = HealthDaily(
        date=today,
        sleep_score=health_row[0] if health_row else None,
        hrv_rmssd_ms=health_row[1] if health_row else None,
        body_battery_max=health_row[2] if health_row else None,
    )
    tsb = float(metrics_row[0]) if metrics_row else 0.0

    score = ReadinessCalculator().calculate(health, {"tsb": tsb})
    recommendation = ReadinessCalculator().get_recommendation(score)

    return {"score": score, "date": str(today), "recommendation": recommendation}


@router.get("/health/alerts")
def get_health_alerts(db=Depends(get_db)):
    """Retorna alertas ativos de overreaching com base em TSB, ramp rate e HRV."""
    # TSB e ATL mais recentes
    metrics_row = db.execute(
        "SELECT tsb, atl FROM athlete_metrics ORDER BY date DESC LIMIT 1"
    ).fetchone()
    tsb = float(metrics_row[0]) if metrics_row else 0.0
    atl = float(metrics_row[1]) if metrics_row else 0.0

    # TSS semanal das últimas 4 semanas
    today = date.today()
    tss_by_week: list[float] = []
    for week_offset in range(3, -1, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * week_offset)
        week_end = week_start + timedelta(days=6)
        row = db.execute(
            "SELECT COALESCE(SUM(tss), 0) FROM activities "
            "WHERE CAST(start_time AS DATE) BETWEEN ? AND ? AND tss IS NOT NULL",
            [week_start, week_end],
        ).fetchone()
        tss_by_week.append(float(row[0]) if row else 0.0)

    # HRV recente e baseline (média de 14 dias)
    hrv_rows = db.execute(
        "SELECT hrv_rmssd_ms FROM health_daily "
        "WHERE hrv_rmssd_ms IS NOT NULL ORDER BY date DESC LIMIT 14"
    ).fetchall()
    hrv_values = [float(r[0]) for r in hrv_rows]
    hrv_recent = hrv_values[0] if hrv_values else None
    hrv_baseline = sum(hrv_values) / len(hrv_values) if len(hrv_values) >= 3 else None

    alerts = OverreachingAnalyzer().compute_all(
        tsb=tsb,
        atl=atl,
        tss_by_week=tss_by_week,
        hrv_recent=hrv_recent,
        hrv_baseline=hrv_baseline,
    )
    return [
        {
            "type": a.type,
            "severity": a.severity,
            "message": a.message,
            "metric_value": a.metric_value,
            "threshold": a.threshold,
        }
        for a in alerts
    ]
