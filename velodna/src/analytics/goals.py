"""
Progresso contra as metas do atleta.

Um número sem meta não diz se está bom. "6,7 h/semana" é muito para quem quer 5
e pouco para quem quer 10; "74 kg" só significa algo ao lado de "meta 68 kg". O
que este módulo devolve para cada meta é a distância até ela e um estado — e o
estado sempre acompanha um rótulo em texto, nunca só a cor.

O sentido de cada métrica mora aqui: no peso, menor é melhor; em todo o resto,
maior. Errar o sentido inverteria o veredito sem nenhum sinal de erro.
"""
from __future__ import annotations

from dataclasses import dataclass

# Fração da meta a partir da qual o estado deixa de ser "longe" e vira "perto".
# O peso tem régua própria: 10% de 68 kg são quase 7 kg, e ninguém chama de
# "perto da meta" quem ainda tem 6 kg a perder.
NEAR_RATIO = 0.10

GOAL_SPECS: dict[str, dict] = {
    "weight_kg": {
        "label": "Peso", "unit": "kg", "lower_is_better": True, "near_ratio": 0.03,
    },
    "weekly_hours": {"label": "Volume semanal", "unit": "h/sem", "lower_is_better": False},
    "ftp_w": {"label": "FTP", "unit": "W", "lower_is_better": False},
    "w_per_kg": {"label": "W/kg", "unit": "W/kg", "lower_is_better": False},
    "ctl": {"label": "Condicionamento (CTL)", "unit": "", "lower_is_better": False},
}


@dataclass(frozen=True)
class GoalProgress:
    """Uma meta lida contra o valor atual."""

    metric: str
    target: float
    current: float | None
    target_date: str | None = None
    notes: str | None = None

    @property
    def spec(self) -> dict:
        return GOAL_SPECS.get(self.metric, {"label": self.metric, "unit": ""})

    @property
    def lower_is_better(self) -> bool:
        return bool(self.spec.get("lower_is_better"))

    @property
    def remaining(self) -> float | None:
        """Quanto falta, sempre positivo enquanto a meta não foi atingida.

        No peso, 74 kg com meta de 68 dá 6 (kg a perder); no volume, 6,7 h com
        meta de 10 dá 3,3 (horas a somar). Zero ou negativo: meta atingida.
        """
        if self.current is None:
            return None
        gap = self.current - self.target
        return round(gap if self.lower_is_better else -gap, 2)

    @property
    def pct_of_target(self) -> float | None:
        """Percentual da meta alcançado — só faz sentido quando maior é melhor."""
        if self.current is None or self.lower_is_better or not self.target:
            return None
        return round(self.current / self.target * 100, 1)

    @property
    def status(self) -> str:
        """`achieved`, `near`, `far` ou `unknown`."""
        remaining = self.remaining
        if remaining is None:
            return "unknown"
        if remaining <= 0:
            return "achieved"
        if remaining <= abs(self.target) * self.spec.get("near_ratio", NEAR_RATIO):
            return "near"
        return "far"

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "label": self.spec["label"],
            "unit": self.spec["unit"],
            "lower_is_better": self.lower_is_better,
            "target": self.target,
            "target_date": self.target_date,
            "notes": self.notes,
            "current": self.current,
            "remaining": self.remaining,
            "pct_of_target": self.pct_of_target,
            "status": self.status,
        }


def evaluate_goals(goals: list[dict], current: dict[str, float | None]) -> list[dict]:
    """Lê cada meta contra o valor atual da métrica.

    Args:
        goals: metas cadastradas (`metric`, `target`, `target_date`, `notes`).
        current: valor atual de cada métrica, pela mesma chave.

    Returns:
        Lista de dicionários com distância, percentual e estado.
    """
    return [
        GoalProgress(
            metric=goal["metric"],
            target=float(goal["target"]),
            current=current.get(goal["metric"]),
            target_date=(
                goal["target_date"].isoformat()
                if goal.get("target_date") and hasattr(goal["target_date"], "isoformat")
                else goal.get("target_date")
            ),
            notes=goal.get("notes"),
        ).to_dict()
        for goal in goals
    ]
