"""
Testes da recomendação diária.

A ordem de prioridade é o que mais importa acertar: um sinal de alarme tem de
vencer qualquer oportunidade. Recomendar intervalado para quem está com TSB −32
porque o perfil aponta falta de trabalho anaeróbico seria pior que não
recomendar nada — o atleta confiaria e cavaria mais buraco.
"""
from __future__ import annotations

import pytest

from analytics.recommendation import (
    READINESS_GOOD,
    TSB_OVERREACHED,
    recommend,
)


def test_deep_negative_tsb_forces_rest_over_any_opportunity():
    """O alarme vence mesmo com prontidão boa e limitador identificado."""
    result = recommend(
        readiness=80.0, tsb=-32.0, ctl=50.0,
        week_tss=100.0, baseline_weekly_tss=400.0,
        limiters=["capacidade anaeróbica"],
    )

    assert result.intensity == "recuperação"
    assert result.focus is None, "não sugerir foco a quem precisa parar"


def test_poor_readiness_forces_rest():
    result = recommend(
        readiness=32.0, tsb=-5.0, ctl=50.0, week_tss=50.0, baseline_weekly_tss=400.0
    )

    assert result.intensity == "recuperação"
    assert "Prontidão" in result.detail


def test_very_fresh_tsb_asks_for_volume():
    """Fresco demais por muito tempo é destreinamento, não forma."""
    result = recommend(
        readiness=75.0, tsb=22.0, ctl=45.0, week_tss=60.0, baseline_weekly_tss=400.0
    )

    assert result.intensity == "endurance longo"
    assert "carregar" in result.headline.lower()


def test_week_already_full_holds_the_load():
    result = recommend(
        readiness=75.0, tsb=-5.0, ctl=50.0,
        week_tss=400.0, baseline_weekly_tss=400.0,
    )

    assert "cumprido" in result.headline.lower()
    assert result.intensity == "leve ou descanso"


def test_green_light_targets_the_limiter():
    """Com sinal verde, o limitador do perfil decide o foco."""
    result = recommend(
        readiness=78.0, tsb=2.0, ctl=50.0,
        week_tss=80.0, baseline_weekly_tss=400.0,
        limiters=["capacidade anaeróbica", "VO2máx"],
    )

    assert result.intensity == "intervalado"
    assert result.focus == "capacidade anaeróbica"
    assert "capacidade anaeróbica" in result.detail


def test_green_light_without_limiters_still_allows_intensity():
    result = recommend(
        readiness=78.0, tsb=2.0, ctl=50.0, week_tss=80.0, baseline_weekly_tss=400.0
    )

    assert result.intensity == "intervalado"
    assert result.focus is None


def test_middle_ground_is_moderate():
    """Nem alarme nem sinal verde: mantém a base."""
    result = recommend(
        readiness=55.0, tsb=-18.0, ctl=50.0,
        week_tss=120.0, baseline_weekly_tss=400.0,
    )

    assert result.intensity == "endurance"


def test_signals_are_always_listed():
    """Recomendação sem os sinais à vista é palpite com cara de resultado."""
    result = recommend(
        readiness=67.0, tsb=5.6, ctl=48.0,
        week_tss=107.0, baseline_weekly_tss=329.0,
    )

    joined = " ".join(result.signals)
    assert "prontidão 67" in joined
    assert "TSB +6" in joined
    assert "%" in joined


def test_missing_signals_do_not_crash():
    """Atleta sem saúde sincronizada ainda recebe leitura da carga."""
    result = recommend(
        readiness=None, tsb=None, ctl=None, week_tss=0.0, baseline_weekly_tss=None
    )

    assert result.headline
    assert result.intensity


@pytest.mark.parametrize("tsb", [TSB_OVERREACHED - 1, TSB_OVERREACHED - 20])
def test_overreached_boundary(tsb):
    assert recommend(70.0, tsb, 50.0, 0.0, 400.0).intensity == "recuperação"


@pytest.mark.parametrize("readiness", [READINESS_GOOD, READINESS_GOOD + 20])
def test_readiness_boundary_allows_intensity(readiness):
    assert recommend(readiness, 0.0, 50.0, 0.0, 400.0).intensity == "intervalado"
