"""Testes do casamento de segmentos."""
import pytest

from routes.segment_matcher import (
    MATCH_RADIUS_M,
    find_efforts,
    haversine_m,
)

# Um grau de latitude ≈ 111,32 km; usar isso mantém as fixtures legíveis.
DEG_PER_M = 1 / 111_320.0


def track(length_m: float, speed_ms: float, start_offset_s: int = 0, power=200.0):
    """Trilha retilínea para o norte, a velocidade constante e 1 Hz."""
    points = []
    steps = int(length_m / speed_ms)
    for i in range(steps + 1):
        travelled = i * speed_ms
        points.append(
            {
                "time_s": start_offset_s + i,
                "lat": -23.5 + travelled * DEG_PER_M,
                "lon": -46.6,
                "distance_m": travelled,
                "power_w": power,
                "hr_bpm": 140.0,
            }
        )
    return points


# --- Distância geográfica --------------------------------------------------

def test_haversine_zero_for_same_point():
    assert haversine_m(-23.5, -46.6, -23.5, -46.6) == pytest.approx(0.0)


def test_haversine_matches_known_degree_length():
    """Um grau de latitude mede cerca de 111 km."""
    assert haversine_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(111_195, rel=0.01)


def test_haversine_is_symmetric():
    a = haversine_m(-23.5, -46.6, -23.6, -46.7)
    b = haversine_m(-23.6, -46.7, -23.5, -46.6)
    assert a == pytest.approx(b)


# --- Casamento -------------------------------------------------------------

def test_finds_single_effort_on_matching_track():
    points = track(2000, 10.0)
    start = (points[0]["lat"], points[0]["lon"])
    end = (points[-1]["lat"], points[-1]["lon"])

    efforts = find_efforts(points, start, end, 2000)
    assert len(efforts) == 1
    assert efforts[0].elapsed_time_s == pytest.approx(200, abs=3)


def test_effort_carries_average_power_and_hr():
    points = track(2000, 10.0, power=250.0)
    efforts = find_efforts(
        points,
        (points[0]["lat"], points[0]["lon"]),
        (points[-1]["lat"], points[-1]["lon"]),
        2000,
    )
    assert efforts[0].avg_power_w == pytest.approx(250.0)
    assert efforts[0].avg_hr_bpm == pytest.approx(140.0)


def test_no_effort_when_track_misses_the_segment():
    """Uma trilha longe dos marcos não produz passagem."""
    points = track(2000, 10.0)
    assert find_efforts(points, (-10.0, -50.0), (-10.1, -50.0), 2000) == []


def test_no_effort_when_distance_is_incompatible():
    """Chegar ao marco final por um caminho muito mais longo não é a mesma passagem."""
    points = track(2000, 10.0)
    start = (points[0]["lat"], points[0]["lon"])
    end = (points[-1]["lat"], points[-1]["lon"])

    # O segmento real tem 500 m; a trilha percorre 2000 m entre os marcos.
    assert find_efforts(points, start, end, 500) == []


def test_ignores_effort_slower_than_plausible():
    """Ficar parado no meio não configura um esforço no segmento."""
    points = track(2000, 0.5)  # 0,5 m/s está abaixo do piso
    efforts = find_efforts(
        points,
        (points[0]["lat"], points[0]["lon"]),
        (points[-1]["lat"], points[-1]["lon"]),
        2000,
    )
    assert efforts == []


def test_finds_two_efforts_on_a_repeated_lap():
    """Duas passagens pelo mesmo trecho geram duas entradas, não uma nem dezenas."""
    first = track(1500, 10.0, start_offset_s=0)
    second = track(1500, 12.0, start_offset_s=600)
    # A segunda volta continua o odômetro, e o atleta se afasta entre elas.
    offset = first[-1]["distance_m"] + 3000
    for point in second:
        point["distance_m"] += offset

    points = first + second
    start = (first[0]["lat"], first[0]["lon"])
    end = (first[-1]["lat"], first[-1]["lon"])

    efforts = find_efforts(points, start, end, 1500)
    assert len(efforts) == 2
    # A segunda passagem foi mais rápida.
    assert efforts[1].elapsed_time_s < efforts[0].elapsed_time_s


def test_effort_speed_is_derived_from_distance_and_time():
    points = track(3000, 10.0)
    effort = find_efforts(
        points,
        (points[0]["lat"], points[0]["lon"]),
        (points[-1]["lat"], points[-1]["lon"]),
        3000,
    )[0]
    assert effort.avg_speed_ms == pytest.approx(10.0, rel=0.05)


def test_empty_input_returns_no_efforts():
    assert find_efforts([], (-23.5, -46.6), (-23.6, -46.6), 1000) == []


def test_zero_length_segment_returns_no_efforts():
    points = track(1000, 10.0)
    assert find_efforts(points, (-23.5, -46.6), (-23.5, -46.6), 0) == []


def test_radius_controls_tolerance():
    """Um marco fora do raio não casa; ampliando o raio, passa a casar."""
    points = track(2000, 10.0)
    end = points[-1]
    # Desloca o marco final para além do raio padrão.
    far = (end["lat"] + (MATCH_RADIUS_M * 2) * DEG_PER_M, end["lon"])
    start = (points[0]["lat"], points[0]["lon"])

    assert find_efforts(points, start, far, 2000) == []
    assert find_efforts(points, start, far, 2000, radius_m=MATCH_RADIUS_M * 4)
