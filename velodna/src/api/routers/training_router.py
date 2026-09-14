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
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from analytics.durability import DEFAULT_KJ_THRESHOLD, compute_durability
from analytics.ftp_history import ftp_on
from analytics.intervals import (
    DEFAULT_THRESHOLD_RATIO,
    MIN_INTERVAL_S,
    detect_intervals,
    group_into_sets,
)
from analytics.timeseries import load_series
from analytics.weekly import build_week_series, build_week_summary
from analytics.wprime_model import WPrimeModel
from api.dependencies import get_athlete_id, get_db
from api.query import row as query_row
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
