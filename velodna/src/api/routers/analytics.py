"""
Router: /pmc e /power-curve — métricas analíticas de treino.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from analytics.critical_power import fit_curve
from api.query import rows as query_rows
from api.dependencies import get_db

router = APIRouter()

# Janela padrão do ajuste de CP: longa o bastante para conter um teste,
# curta o bastante para refletir a forma atual.
CP_LOOKBACK_DAYS = 90


@router.get("/pmc")
def get_pmc(db=Depends(get_db)):
    """Retorna série histórica de CTL/ATL/TSB ordenada por data."""
    return query_rows(
        db,
        """
        SELECT date, ctl, atl, tsb, daily_tss
        FROM training_load
        ORDER BY date
        """,
    )


@router.get("/ftp-history")
def get_ftp_history(db=Depends(get_db)):
    """Retorna a evolução do FTP, distinguindo medição de estimativa."""
    return query_rows(db, """
        SELECT effective_from, ftp_w, cp_w, w_prime_j, method, source
        FROM ftp_history
        ORDER BY effective_from
        """)


@router.get("/critical-power")
def get_critical_power(
    days: int = CP_LOOKBACK_DAYS,
    sport: str = "cycling",
    db=Depends(get_db),
):
    """Ajusta CP e W' sobre os melhores esforços do período.

    O ajuste por regressão pressupõe que cada ponto da curva seja um esforço
    máximo. Numa janela de treino normal isso raramente vale para todas as
    durações, então o resultado tende a subestimar o CP frente a um teste
    dedicado — compare com `/ftp-history`, onde os testes têm `source='test'`.
    """
    rows = db.execute(
        """
        SELECT pc.duration_s, MAX(pc.power_w)
        FROM power_curves pc
        JOIN activities a ON a.id = pc.activity_id
        WHERE pc.date >= (SELECT MAX(date) FROM power_curves) - ?
          AND (? = 'all' OR a.sport_type = ?)
        GROUP BY pc.duration_s
        """,
        [days, sport, sport],
    ).fetchall()

    fit = fit_curve({int(r[0]): float(r[1]) for r in rows})
    if fit is None:
        raise HTTPException(
            status_code=404,
            detail="Esforços insuficientes na janela para ajustar o modelo",
        )

    return {
        "cp_w": fit.cp_w,
        "w_prime_j": fit.w_prime_j,
        "w_prime_kj": fit.w_prime_kj,
        "ftp_w": fit.ftp_w,
        "r_squared": fit.r_squared,
        "n_points": fit.n_points,
        "durations_s": list(fit.durations_s),
        "window_days": days,
    }


@router.get("/power-curve")
def get_power_curve(
    start: Optional[date] = None,
    end: Optional[date] = None,
    sport: str = "cycling",
    db=Depends(get_db),
):
    """Retorna a curva de potência agregada (MMP) por duração.

    Para cada duração, devolve a melhor potência já registrada no período —
    é o envelope das curvas por atividade, não a curva de um treino isolado.

    O filtro por esporte é obrigatório na prática: potência de corrida (Stryd)
    e de ciclismo compartilham a unidade mas não a escala, e misturá-las produz
    uma curva sem sentido. Use `sport=all` para desligar o filtro.
    """
    return query_rows(
        db,
        """
        SELECT pc.duration_s,
               MAX(pc.power_w)                     AS power_w,
               ARG_MAX(pc.activity_id, pc.power_w) AS activity_id,
               ARG_MAX(pc.date, pc.power_w)        AS date
        FROM power_curves pc
        JOIN activities a ON a.id = pc.activity_id
        WHERE (? IS NULL OR pc.date >= ?)
          AND (? IS NULL OR pc.date <= ?)
          AND (? = 'all' OR a.sport_type = ?)
        GROUP BY pc.duration_s
        ORDER BY pc.duration_s
        """,
        [start, start, end, end, sport, sport],
    )
