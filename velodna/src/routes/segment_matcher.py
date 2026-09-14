"""
Casamento de segmentos — encontrar as passagens de um trecho conhecido dentro
das atividades.

O problema real não é comparar rotas, é reconhecer que dois passeios cruzaram
o **mesmo trecho** em direções e velocidades diferentes, com GPS impreciso e
pontos amostrados em posições distintas a cada passagem.

A abordagem aqui é deliberadamente simples e explicável:

  1. Um segmento é definido por um ponto de início, um de fim e a distância
     entre eles ao longo do traçado.
  2. Uma atividade "passa" pelo segmento se chega perto do início e, depois,
     perto do fim, percorrendo uma distância compatível.
  3. O tempo do esforço é a diferença entre os dois instantes.

Não há indexação espacial: com centenas de atividades e streams decimados, a
varredura direta roda em segundos e o código continua legível. Trocar por um
índice só se justifica quando o acervo crescer uma ordem de grandeza.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass

# Raio da Terra em metros, para a fórmula de haversine.
EARTH_RADIUS_M = 6_371_000.0

# Distância máxima entre o ponto gravado e o marco do segmento para considerar
# que o atleta passou por ali. Cobre o erro típico de GPS civil em ciclismo.
MATCH_RADIUS_M = 35.0

# Tolerância na distância percorrida frente ao comprimento do segmento. Uma
# passagem 25% mais longa provavelmente pegou outro caminho entre os marcos.
DISTANCE_TOLERANCE = 0.25

# Velocidade mínima plausível num esforço registrado (m/s). Abaixo disso o
# atleta parou no meio e o tempo não representa um esforço.
MIN_SPEED_MS = 1.5


@dataclass(frozen=True)
class SegmentEffort:
    """Uma passagem por um segmento."""

    activity_id: str
    started_at_s: int
    elapsed_time_s: int
    distance_m: float
    avg_power_w: float | None
    avg_hr_bpm: float | None

    @property
    def avg_speed_ms(self) -> float:
        """Velocidade média da passagem."""
        return self.distance_m / self.elapsed_time_s if self.elapsed_time_s else 0.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância entre dois pontos geográficos, em metros.

    Args:
        lat1: latitude do primeiro ponto, em graus.
        lon1: longitude do primeiro ponto, em graus.
        lat2: latitude do segundo ponto, em graus.
        lon2: longitude do segundo ponto, em graus.

    Returns:
        Distância em metros sobre a superfície.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def find_efforts(
    points: list[dict],
    start: tuple[float, float],
    end: tuple[float, float],
    expected_distance_m: float,
    radius_m: float = MATCH_RADIUS_M,
) -> list[SegmentEffort]:
    """Localiza as passagens por um segmento dentro de uma atividade.

    Args:
        points: pontos da atividade, cada um com `time_s`, `lat`, `lon`,
            `distance_m` e, opcionalmente, `power_w` e `hr_bpm`.
        start: par (lat, lon) do início do segmento.
        end: par (lat, lon) do fim do segmento.
        expected_distance_m: comprimento do segmento ao longo do traçado.
        radius_m: raio de tolerância para reconhecer os marcos.

    Returns:
        Passagens encontradas, em ordem cronológica. Uma volta que cruze o
        segmento várias vezes devolve uma entrada por passagem.
    """
    if not points or expected_distance_m <= 0:
        return []

    near_start = _local_minima(points, start, radius_m)
    near_end = _local_minima(points, end, radius_m)
    if not near_start or not near_end:
        return []

    efforts: list[SegmentEffort] = []
    used_end_indexes: set[int] = set()

    for start_index in near_start:
        candidate = _first_valid_end(
            points, start_index, near_end, expected_distance_m, used_end_indexes
        )
        if candidate is None:
            continue

        used_end_indexes.add(candidate)
        effort = _build_effort(points, start_index, candidate)
        if effort is not None:
            efforts.append(effort)

    return sorted(efforts, key=lambda e: e.started_at_s)


def _local_minima(
    points: list[dict], target: tuple[float, float], radius_m: float
) -> list[int]:
    """Índices dos pontos mais próximos de um marco, um por aproximação.

    Uma passagem gera vários pontos dentro do raio; interessa apenas o mais
    próximo de cada aproximação, senão uma única passagem viraria dezenas.

    Args:
        points: pontos da atividade.
        target: par (lat, lon) do marco.
        radius_m: raio de tolerância.

    Returns:
        Índices dos pontos de aproximação máxima, em ordem cronológica.
    """
    minima: list[int] = []
    best_index: int | None = None
    best_distance = float("inf")

    for index, point in enumerate(points):
        if point.get("lat") is None or point.get("lon") is None:
            continue

        distance = haversine_m(point["lat"], point["lon"], target[0], target[1])

        if distance <= radius_m:
            if distance < best_distance:
                best_distance, best_index = distance, index
        elif best_index is not None:
            # Saiu do raio: fecha a aproximação corrente.
            minima.append(best_index)
            best_index, best_distance = None, float("inf")

    if best_index is not None:
        minima.append(best_index)
    return minima


def _first_valid_end(
    points: list[dict],
    start_index: int,
    end_indexes: list[int],
    expected_distance_m: float,
    used: set[int],
) -> int | None:
    """Escolhe o marco de chegada compatível com uma partida.

    Args:
        points: pontos da atividade.
        start_index: índice do marco de partida.
        end_indexes: índices candidatos de chegada.
        expected_distance_m: comprimento esperado do segmento.
        used: índices de chegada já consumidos por outras passagens.

    Returns:
        Índice da chegada, ou None se nenhuma serve.
    """
    low = expected_distance_m * (1 - DISTANCE_TOLERANCE)
    high = expected_distance_m * (1 + DISTANCE_TOLERANCE)

    for end_index in end_indexes:
        if end_index <= start_index or end_index in used:
            continue

        travelled = _distance_between(points, start_index, end_index)
        if travelled is None:
            continue
        if low <= travelled <= high:
            return end_index

    return None


def _distance_between(points: list[dict], start: int, end: int) -> float | None:
    """Distância percorrida entre dois índices, pelo odômetro da atividade."""
    first, last = points[start].get("distance_m"), points[end].get("distance_m")
    if first is None or last is None:
        return None
    return last - first


def _build_effort(points: list[dict], start: int, end: int) -> SegmentEffort | None:
    """Monta a passagem a partir do trecho entre dois índices.

    Args:
        points: pontos da atividade.
        start: índice de partida.
        end: índice de chegada.

    Returns:
        SegmentEffort, ou None se o trecho é implausível (parado no meio).
    """
    elapsed = points[end]["time_s"] - points[start]["time_s"]
    distance = _distance_between(points, start, end)
    if not elapsed or distance is None or elapsed <= 0:
        return None

    if distance / elapsed < MIN_SPEED_MS:
        return None

    span = points[start : end + 1]
    return SegmentEffort(
        activity_id=points[start].get("activity_id", ""),
        started_at_s=points[start]["time_s"],
        elapsed_time_s=elapsed,
        distance_m=distance,
        avg_power_w=_mean(span, "power_w"),
        avg_hr_bpm=_mean(span, "hr_bpm"),
    )


def _mean(points: list[dict], key: str) -> float | None:
    """Média de um campo ao longo de um trecho, ignorando ausências."""
    values = [p[key] for p in points if p.get(key) is not None]
    return round(sum(values) / len(values), 1) if values else None


def new_segment_id() -> str:
    """Gera um identificador para um segmento novo."""
    return str(uuid.uuid4())
