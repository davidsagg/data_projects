"""
Perfil de capacidade — onde o atleta é forte e onde é limitado.

A curva de potência diz quanto o atleta produz em cada duração, mas sozinha não
responde à pergunta que importa para periodizar: *em qual duração eu estou pior
em relação a mim mesmo?* Um número de 5 minutos alto não significa nada se o de
20 minutos estiver ainda mais alto — o limitador é relativo, não absoluto.

Aqui a curva de um período é comparada com o melhor histórico do atleta, duração
por duração. O que sobra é um perfil: 98% do recorde em 1 minuto e 84% em 20
minutos descreve alguém que manteve o topo mas perdeu resistência — e diz
exatamente o que treinar.

A referência é o próprio atleta, não uma tabela populacional. Tabelas de
percentil dependem de peso, idade e categoria, e erram feio no indivíduo; a
evolução contra o próprio histórico não erra.
"""
from __future__ import annotations

from dataclasses import dataclass

# Durações do perfil. Cobrem os domínios fisiológicos usuais: neuromuscular,
# anaeróbico, VO2máx, limiar e resistência.
PROFILE_DURATIONS = (5, 60, 300, 720, 1200, 3600)

DURATION_LABEL = {
    5: "pico neuromuscular",
    60: "capacidade anaeróbica",
    300: "VO2máx",
    720: "limiar (teste)",
    1200: "limiar",
    3600: "resistência",
}

# Abaixo deste percentual do recorde, a duração entra como limitador.
LIMITER_THRESHOLD_PCT = 90.0

# Acima deste, entra como força.
STRENGTH_THRESHOLD_PCT = 97.0


@dataclass(frozen=True)
class CapacityPoint:
    """Uma duração comparada com o melhor histórico do atleta."""

    duration_s: int
    label: str
    current_w: float | None
    best_w: float | None

    @property
    def pct_of_best(self) -> float | None:
        """Percentual do recorde pessoal atingido no período."""
        if not self.current_w or not self.best_w:
            return None
        return round(self.current_w / self.best_w * 100, 1)

    @property
    def classification(self) -> str:
        """Força, limitador ou dentro da faixa normal."""
        pct = self.pct_of_best
        if pct is None:
            return "sem dados"
        if pct >= STRENGTH_THRESHOLD_PCT:
            return "força"
        if pct < LIMITER_THRESHOLD_PCT:
            return "limitador"
        return "normal"

    def to_dict(self) -> dict:
        return {
            "duration_s": self.duration_s,
            "label": self.label,
            "current_w": self.current_w,
            "best_w": self.best_w,
            "pct_of_best": self.pct_of_best,
            "classification": self.classification,
        }


def build_profile(
    current_curve: dict[int, float],
    best_curve: dict[int, float],
    durations: tuple[int, ...] = PROFILE_DURATIONS,
) -> dict:
    """Compara a curva de um período com o melhor histórico.

    Args:
        current_curve: {duração: watts} do período analisado.
        best_curve: {duração: watts} do melhor de todo o histórico.
        durations: durações a incluir no perfil.

    Returns:
        Os pontos do perfil, mais as listas de forças e limitadores.
    """
    points = [
        CapacityPoint(
            duration_s=duration,
            label=DURATION_LABEL.get(duration, f"{duration}s"),
            current_w=current_curve.get(duration),
            best_w=best_curve.get(duration),
        )
        for duration in durations
    ]

    return {
        "points": [p.to_dict() for p in points],
        "strengths": [p.label for p in points if p.classification == "força"],
        "limiters": [p.label for p in points if p.classification == "limitador"],
        "summary": _summarize(points),
    }


def _summarize(points: list[CapacityPoint]) -> str:
    """Frase que descreve o formato do perfil.

    O formato importa mais que os valores: alguém a 98% no curto e 84% no longo
    tem um problema diferente de quem está a 88% em tudo, mesmo que a média seja
    parecida.
    """
    scored = [p for p in points if p.pct_of_best is not None]
    if len(scored) < 2:
        return "histórico insuficiente para traçar o perfil"

    short = [p for p in scored if p.duration_s <= 300]
    long = [p for p in scored if p.duration_s >= 1200]
    if not short or not long:
        return "faixa de durações insuficiente para comparar curto e longo"

    short_avg = sum(p.pct_of_best for p in short) / len(short)
    long_avg = sum(p.pct_of_best for p in long) / len(long)
    gap = short_avg - long_avg

    if gap > 8:
        return "topo preservado, resistência abaixo — falta base"
    if gap < -8:
        return "base preservada, topo abaixo — falta intensidade"
    if (short_avg + long_avg) / 2 >= STRENGTH_THRESHOLD_PCT:
        return "perfil equilibrado e perto do melhor histórico"
    return "perfil equilibrado, abaixo do melhor histórico"
