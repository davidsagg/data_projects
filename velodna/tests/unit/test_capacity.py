"""
Testes do perfil de capacidade.

O que o perfil precisa acertar é o **formato**, não os valores: alguém a 98% no
curto e 84% no longo tem um problema de base; alguém a 88% em tudo tem outro
problema, mesmo com média parecida. Confundir os dois leva a periodizar errado.
"""
from __future__ import annotations

import pytest

from analytics.capacity import PROFILE_DURATIONS, CapacityPoint, build_profile


def curve(**by_duration) -> dict[int, float]:
    """Monta uma curva {duração: watts} a partir de nomes legíveis."""
    names = {"s5": 5, "m1": 60, "m5": 300, "m12": 720, "m20": 1200, "h1": 3600}
    return {names[k]: v for k, v in by_duration.items()}


BEST = curve(s5=900, m1=500, m5=320, m12=250, m20=240, h1=215)


def test_at_personal_best_everything_is_a_strength():
    profile = build_profile(BEST, BEST)

    assert profile["limiters"] == []
    assert len(profile["strengths"]) == len(PROFILE_DURATIONS)


def test_missing_duration_is_not_scored():
    profile = build_profile(curve(m5=300), BEST)

    points = {p["duration_s"]: p for p in profile["points"]}
    assert points[5]["pct_of_best"] is None
    assert points[5]["classification"] == "sem dados"
    assert points[300]["pct_of_best"] == pytest.approx(93.8, abs=0.2)


def test_weak_duration_becomes_a_limiter():
    current = dict(BEST)
    current[1200] = 200.0  # 83% do recorde de 20 min

    profile = build_profile(current, BEST)

    assert "limiar" in profile["limiters"]


def test_short_preserved_long_weak_reads_as_missing_base():
    current = curve(s5=890, m1=495, m5=315, m12=210, m20=200, h1=178)

    profile = build_profile(current, BEST)

    assert "falta base" in profile["summary"]


def test_long_preserved_short_weak_reads_as_missing_intensity():
    current = curve(s5=700, m1=400, m5=270, m12=248, m20=238, h1=213)

    profile = build_profile(current, BEST)

    assert "falta intensidade" in profile["summary"]


def test_balanced_profile_near_best():
    current = {d: w * 0.99 for d, w in BEST.items()}

    profile = build_profile(current, BEST)

    assert "equilibrado" in profile["summary"]


def test_balanced_but_below_best():
    current = {d: w * 0.88 for d, w in BEST.items()}

    profile = build_profile(current, BEST)

    assert profile["summary"] == "perfil equilibrado, abaixo do melhor histórico"
    assert len(profile["limiters"]) == len(PROFILE_DURATIONS)


def test_empty_current_curve_is_inconclusive():
    profile = build_profile({}, BEST)

    assert "insuficiente" in profile["summary"]


@pytest.mark.parametrize(
    ("current", "best", "expected"),
    [(300.0, 300.0, "força"), (291.0, 300.0, "força"),
     (280.0, 300.0, "normal"), (260.0, 300.0, "limitador")],
)
def test_classification_thresholds(current, best, expected):
    point = CapacityPoint(300, "VO2máx", current, best)

    assert point.classification == expected
