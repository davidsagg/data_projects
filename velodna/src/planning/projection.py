"""
Projeção de carga de treino — o PMC rodando para frente.

As mesmas médias exponenciais que descrevem o passado projetam o futuro: dado
um plano de TSS diário, dá para saber o CTL e o TSB de qualquer data à frente.
Isso responde às duas perguntas que importam no planejamento:

  - "se eu treinar assim, onde chego?"        → `project`
  - "quanto preciso treinar para chegar lá?"  → `required_daily_tss`

**Limite honesto do modelo:** CTL e ATL são médias de TSS, não de adaptação
fisiológica. A projeção diz quanta carga terá sido absorvida, não que o atleta
vai suportá-la. Uma rampa agressiva o bastante para chegar ao CTL desejado pode
ser exatamente a que causa lesão — por isso `ramp_rate_per_week` é devolvido
junto, para ser confrontado com um limite seguro.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from analytics.pmc_calculator import ATL_DECAY_DAYS, CTL_DECAY_DAYS

# Acima de ~7 pontos de CTL por semana o risco de lesão por sobrecarga cresce
# de forma desproporcional (Coggan, Friel).
SAFE_RAMP_RATE_PER_WEEK = 7.0


@dataclass(frozen=True)
class ProjectedDay:
    """Estado de carga projetado para um dia."""

    date: date
    daily_tss: float
    ctl: float
    atl: float
    tsb: float


def project(
    start_ctl: float,
    start_atl: float,
    daily_tss: dict[date, float],
) -> list[ProjectedDay]:
    """Projeta CTL, ATL e TSB a partir de um plano de TSS diário.

    Args:
        start_ctl: CTL na véspera do primeiro dia projetado.
        start_atl: ATL na véspera do primeiro dia projetado.
        daily_tss: plano {data: tss}; dias ausentes contam como descanso.

    Returns:
        Um `ProjectedDay` por data do plano, em ordem cronológica.
    """
    if not daily_tss:
        return []

    ctl_alpha = 1 - math.exp(-1 / CTL_DECAY_DAYS)
    atl_alpha = 1 - math.exp(-1 / ATL_DECAY_DAYS)

    ctl, atl = start_ctl, start_atl
    projection: list[ProjectedDay] = []

    for day in sorted(daily_tss):
        tss = daily_tss[day]
        ctl = ctl_alpha * tss + (1 - ctl_alpha) * ctl
        atl = atl_alpha * tss + (1 - atl_alpha) * atl
        projection.append(
            ProjectedDay(
                date=day,
                daily_tss=round(tss, 1),
                ctl=round(ctl, 2),
                atl=round(atl, 2),
                tsb=round(ctl - atl, 2),
            )
        )
    return projection


def build_flat_plan(
    start: date,
    days: int,
    weekly_tss: float,
    rest_days: set[int] | None = None,
) -> dict[date, float]:
    """Distribui uma carga semanal em dias de treino.

    Args:
        start: primeiro dia do plano.
        days: quantidade de dias a planejar.
        weekly_tss: TSS total por semana.
        rest_days: dias da semana de descanso (0 = segunda, 6 = domingo).

    Returns:
        Plano {data: tss}, com 0 nos dias de descanso.
    """
    rest_days = rest_days or set()
    training_days_per_week = 7 - len(rest_days)
    if training_days_per_week <= 0:
        return {start + timedelta(days=i): 0.0 for i in range(days)}

    per_training_day = weekly_tss / training_days_per_week

    plan: dict[date, float] = {}
    for offset in range(days):
        day = start + timedelta(days=offset)
        plan[day] = 0.0 if day.weekday() in rest_days else per_training_day
    return plan


def required_daily_tss(
    start_ctl: float,
    target_ctl: float,
    days: int,
) -> float | None:
    """Calcula o TSS diário constante que leva o CTL ao alvo num prazo.

    Invertendo a média exponencial: partindo de CTL₀ e aplicando TSS constante
    por n dias, `CTLₙ = TSS + (CTL₀ − TSS)·(1−α)ⁿ`. Isolar TSS dá a resposta.

    Args:
        start_ctl: CTL atual.
        target_ctl: CTL desejado.
        days: prazo em dias.

    Returns:
        TSS diário necessário, ou None se o alvo é inalcançável no prazo
        (só ocorre quando o prazo é nulo ou o alvo exigiria TSS negativo).
    """
    if days <= 0:
        return None

    alpha = 1 - math.exp(-1 / CTL_DECAY_DAYS)
    decay = (1 - alpha) ** days
    if abs(1 - decay) < 1e-12:
        return None

    tss = (target_ctl - start_ctl * decay) / (1 - decay)
    return round(tss, 1) if tss >= 0 else None


def ramp_rate_per_week(projection: list[ProjectedDay]) -> float | None:
    """Ritmo médio de crescimento do CTL, em pontos por semana.

    Args:
        projection: dias projetados, em ordem cronológica.

    Returns:
        Variação de CTL por semana, ou None se a projeção é curta demais.
    """
    if len(projection) < 2:
        return None

    span_days = (projection[-1].date - projection[0].date).days
    if span_days <= 0:
        return None

    delta = projection[-1].ctl - projection[0].ctl
    return round(delta / span_days * 7, 2)


def summarize(projection: list[ProjectedDay]) -> dict:
    """Resume uma projeção com os números que orientam a decisão.

    Args:
        projection: dias projetados, em ordem cronológica.

    Returns:
        Resumo com CTL/TSB finais, ritmo de rampa e alerta de segurança.
    """
    if not projection:
        return {}

    ramp = ramp_rate_per_week(projection)
    return {
        "start_date": str(projection[0].date),
        "end_date": str(projection[-1].date),
        "days": len(projection),
        "final_ctl": projection[-1].ctl,
        "final_atl": projection[-1].atl,
        "final_tsb": projection[-1].tsb,
        "min_tsb": min(day.tsb for day in projection),
        "total_tss": round(sum(day.daily_tss for day in projection), 1),
        "ramp_rate_per_week": ramp,
        "safe_ramp_limit": SAFE_RAMP_RATE_PER_WEEK,
        "ramp_exceeds_safe_limit": (
            ramp is not None and ramp > SAFE_RAMP_RATE_PER_WEEK
        ),
    }
