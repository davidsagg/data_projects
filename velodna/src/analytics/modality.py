"""
Modalidade de uma atividade — pedal na rua, pedal no rolo, força ou outro.

O `sport` do `.fit` diz `cycling` para as duas formas de pedalar, e elas não são
o mesmo treino. No rolo não há descida, vento nem semáforo: a potência é
contínua, o TSS por hora sobe, e uma hora indoor cansa mais que uma hora na rua.
Quem quer ler o próprio volume precisa ver as duas separadas — e a musculação ao
lado, que hoje some do volume por não ser bike.

A fonte da distinção é o Strava (`sport_type` e a marcação `trainer`), anotada no
acervo pelo sync. Sem ela, a atividade de ciclismo cai em "rua" — é o caso comum
e o erro menos danoso.
"""
from __future__ import annotations

OUTDOOR = "outdoor"
INDOOR = "indoor"
STRENGTH = "strength"
OTHER = "other"

# Ordem de exibição — a mesma das cores categóricas no frontend.
MODALITIES = (OUTDOOR, INDOOR, STRENGTH, OTHER)

MODALITY_LABELS = {
    OUTDOOR: "Pedal na rua",
    INDOOR: "Pedal no rolo",
    STRENGTH: "Força",
    OTHER: "Outros",
}

_INDOOR_STRAVA_TYPES = frozenset({"VirtualRide"})
_STRENGTH_STRAVA_TYPES = frozenset({"WeightTraining", "Crossfit", "Workout"})
_STRENGTH_SPORTS = frozenset({"training"})


def classify(
    sport_type: str | None,
    strava_sport_type: str | None = None,
    trainer: bool | None = None,
) -> str:
    """Classifica uma atividade numa das quatro modalidades.

    Args:
        sport_type: esporte canônico do catálogo (`cycling`, `running`...).
        strava_sport_type: valor cru do Strava, quando sincronizado.
        trainer: marcação de rolo do Strava.

    Returns:
        Uma de `MODALITIES`.
    """
    if strava_sport_type in _STRENGTH_STRAVA_TYPES:
        return STRENGTH
    if sport_type == "cycling":
        if strava_sport_type in _INDOOR_STRAVA_TYPES or trainer:
            return INDOOR
        return OUTDOOR
    if sport_type in _STRENGTH_SPORTS:
        return STRENGTH
    return OTHER
