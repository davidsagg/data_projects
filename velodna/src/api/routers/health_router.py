"""
Router: /health-daily, /readiness/today e /health/alerts — métricas de saúde e recuperação.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from api.query import rows as query_rows
from api.dependencies import get_db
from health.overreaching_alerts import OverreachingAnalyzer
from health.readiness import ReadinessCalculator
from ingestion.garmin_health_client import HealthDaily

router = APIRouter()


@router.get("/health-daily")
def get_health_daily(days: int = 30, end: date | None = None, db=Depends(get_db)):
    """Retorna os últimos N registros de saúde ordenados por data decrescente.

    Com `end`, a janela termina naquela data — a base e as tendências de uma
    semana passada são as daquela época, não as de hoje.
    """
    return query_rows(
        db,
        "SELECT * FROM health_metrics WHERE date <= ? ORDER BY date DESC LIMIT ?",
        [end or date.today(), days],
    )


@router.get("/health/sleep-correlation")
def get_sleep_correlation(
    days: int = 365,
    sport: str = "cycling",
    db=Depends(get_db),
):
    """Correlaciona métricas de recuperação com métricas de performance (US-12).

    Devolve, para cada par testado, o coeficiente, o número de observações, o
    valor-p e uma interpretação em texto. Um coeficiente sem `n` e sem valor-p
    é fácil de superinterpretar, então nenhum dos três é opcional aqui.
    """
    from health.sleep_correlator import (
        SleepCorrelator,
        pair_recovery_with_performance,
    )

    health = query_rows(
        db,
        """
        SELECT date, sleep_hours, sleep_quality_score, hrv_rmssd_ms,
               resting_hr_bpm, body_battery
        FROM health_metrics
        WHERE date >= CURRENT_DATE - ?
        ORDER BY date
        """,
        [days],
    )
    activities = query_rows(
        db,
        """
        SELECT CAST(started_at AS DATE) AS date, normalized_power_w, tss,
               efficiency_factor, decoupling_pct, intensity_factor
        FROM activities
        WHERE CAST(started_at AS DATE) >= CURRENT_DATE - ?
          AND (? = 'all' OR sport_type = ?)
        ORDER BY started_at
        """,
        [days, sport, sport],
    )

    correlator = SleepCorrelator()
    pairs_to_test = [
        ("sleep_hours", "Horas de sono", "normalized_power_w", "Potência normalizada"),
        ("sleep_hours", "Horas de sono", "tss", "TSS"),
        ("sleep_quality_score", "Qualidade do sono", "efficiency_factor", "Efficiency Factor"),
        ("hrv_rmssd_ms", "HRV", "normalized_power_w", "Potência normalizada"),
        ("hrv_rmssd_ms", "HRV", "decoupling_pct", "Decoupling"),
        ("body_battery", "Body battery", "tss", "TSS"),
        ("resting_hr_bpm", "FC de repouso", "efficiency_factor", "Efficiency Factor"),
    ]

    results = []
    for recovery_key, recovery_label, perf_key, perf_label in pairs_to_test:
        pairs = pair_recovery_with_performance(
            health, activities, recovery_key, perf_key
        )
        analysis = correlator.analyze(
            [(p[0], p[1]) for p in pairs], recovery_label, perf_label
        )
        if analysis is None:
            continue
        results.append(
            {
                "x_label": analysis.x_label,
                "y_label": analysis.y_label,
                "x_key": recovery_key,
                "y_key": perf_key,
                "r": analysis.r,
                "n": analysis.n,
                "p_value": analysis.p_value,
                "significant": analysis.significant,
                "strength": analysis.strength,
                "direction": analysis.direction,
                "interpretation": analysis.interpretation,
                "points": [
                    {"x": p[0], "y": p[1], "date": str(p[2])} for p in pairs
                ],
            }
        )

    # Os achados significativos primeiro, e entre eles os de maior magnitude.
    results.sort(key=lambda item: (not item["significant"], -abs(item["r"])))
    return {"window_days": days, "correlations": results}


@router.get("/readiness/today")
def get_readiness_today(db=Depends(get_db)):
    """Calcula e retorna o score de recuperação para hoje."""
    today = date.today()

    health_row = db.execute(
        "SELECT sleep_quality_score, hrv_rmssd_ms, body_battery "
        "FROM health_metrics WHERE date = ?",
        [today],
    ).fetchone()

    metrics_row = db.execute(
        "SELECT tsb FROM training_load WHERE date = ?",
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
def get_health_alerts(reference: date | None = None, db=Depends(get_db)):
    """Retorna alertas ativos de overreaching com base em TSB, ramp rate e HRV.

    Com `reference`, avalia os alertas como estavam naquela data.
    """
    today = min(reference or date.today(), date.today())

    # TSB e ATL mais recentes
    metrics_row = db.execute(
        "SELECT tsb, atl FROM training_load WHERE date <= ? "
        "ORDER BY date DESC LIMIT 1",
        [today],
    ).fetchone()
    tsb = float(metrics_row[0]) if metrics_row else 0.0
    atl = float(metrics_row[1]) if metrics_row else 0.0

    # TSS semanal das últimas 4 semanas
    tss_by_week: list[float] = []
    for week_offset in range(3, -1, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * week_offset)
        week_end = week_start + timedelta(days=6)
        row = db.execute(
            "SELECT COALESCE(SUM(tss), 0) FROM activities "
            "WHERE CAST(started_at AS DATE) BETWEEN ? AND ? AND tss IS NOT NULL",
            [week_start, week_end],
        ).fetchone()
        tss_by_week.append(float(row[0]) if row else 0.0)

    # HRV recente e baseline (média de 14 dias)
    hrv_rows = db.execute(
        "SELECT hrv_rmssd_ms FROM health_metrics "
        "WHERE hrv_rmssd_ms IS NOT NULL AND date <= ? ORDER BY date DESC LIMIT 14",
        [today],
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
