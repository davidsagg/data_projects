"""Testes do histórico de eFTP."""
import duckdb
import pytest
from datetime import date, datetime, timedelta, timezone

from analytics.ftp_history import (
    DECAY_FLOOR_RATIO,
    estimate_ftp_from_curve,
    ftp_on,
    rebuild_ftp_history,
)
from storage.catalog_store import CatalogStore
from storage.models import Activity

ATHLETE_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def store():
    conn = duckdb.connect(":memory:")
    s = CatalogStore(conn)
    s.initialize_schema()
    conn.execute("INSERT INTO athletes (id, name) VALUES (?, ?)", [ATHLETE_ID, "T"])
    yield s
    conn.close()


def _add_activity(store, when: date, curve: dict[int, float] | None = None) -> str:
    activity_id = store.upsert_activity(
        Activity(
            source="fit",
            sport_type="cycling",
            started_at=datetime.combine(when, datetime.min.time(), tzinfo=timezone.utc),
            elapsed_time_s=3600,
        ),
        ATHLETE_ID,
    )
    if curve:
        store.save_power_curve(activity_id, when, curve)
    return activity_id


# --- Estimativa a partir da curva ------------------------------------------

def test_estimate_prefers_highest_derived_value():
    """Entre 20 e 60 min, vale a estimativa que resultar no maior FTP."""
    ftp, method = estimate_ftp_from_curve({1200: 300.0, 3600: 250.0})
    assert ftp == pytest.approx(285.0)  # 300 * 0.95 supera 250 * 1.00
    assert method == "best_20min"


def test_estimate_ignores_short_efforts():
    """Esforço de 5 min não diz nada sobre o limiar."""
    assert estimate_ftp_from_curve({300: 400.0}) is None


def test_estimate_rejects_zero_power():
    """Atividade gravada com potência zerada não pode virar um FTP de 0 W."""
    assert estimate_ftp_from_curve({1200: 0.0, 3600: 0.0}) is None


# --- Reconstrução do histórico ---------------------------------------------

def test_history_ignores_window_with_too_few_activities(store):
    """Uma única atividade não sustenta uma estimativa de FTP."""
    _add_activity(store, date(2024, 1, 1), {1200: 200.0})
    assert rebuild_ftp_history(store, ATHLETE_ID) == []


def test_history_emits_after_enough_activities(store):
    for i in range(10):
        _add_activity(store, date(2024, 1, 1) + timedelta(days=i * 3), {1200: 200.0})
    points = rebuild_ftp_history(store, ATHLETE_ID)
    assert points
    assert points[0].ftp_w == pytest.approx(190.0)  # 200 * 0.95


def test_history_rises_immediately_on_better_effort(store):
    for i in range(10):
        _add_activity(store, date(2024, 1, 1) + timedelta(days=i * 3), {1200: 200.0})
    for i in range(10):
        _add_activity(store, date(2024, 3, 1) + timedelta(days=i * 3), {1200: 260.0})

    points = rebuild_ftp_history(store, ATHLETE_ID)
    assert max(p.ftp_w for p in points) == pytest.approx(247.0)  # 260 * 0.95


def test_history_does_not_decay_across_a_gap_without_training(store):
    """Sem treino no período não há queda de forma medida — logo, sem decaimento."""
    for i in range(10):
        _add_activity(store, date(2024, 1, 1) + timedelta(days=i * 3), {1200: 300.0})
    for i in range(10):
        _add_activity(store, date(2026, 1, 1) + timedelta(days=i * 3), {1200: 300.0})

    points = rebuild_ftp_history(store, ATHLETE_ID)
    # Dois anos parado a 1,5% por semana zeraria o FTP se houvesse decaimento.
    assert min(p.ftp_w for p in points) > 200.0


def test_decay_respects_the_floor(store):
    """O destreino tem piso: quem construiu base não volta ao nível de sedentário."""
    for i in range(10):
        _add_activity(store, date(2024, 1, 1) + timedelta(days=i * 3), {1200: 300.0})
    # Treino leve e contínuo por dois anos, sem esforço que confirme o limiar.
    for i in range(200):
        _add_activity(store, date(2024, 3, 1) + timedelta(days=i * 4))

    points = rebuild_ftp_history(store, ATHLETE_ID)
    peak = max(p.ftp_w for p in points)
    assert min(p.ftp_w for p in points) >= peak * DECAY_FLOOR_RATIO - 1


# --- Consulta por data -----------------------------------------------------

def test_ftp_on_returns_value_in_force(store):
    for i in range(10):
        _add_activity(store, date(2024, 1, 1) + timedelta(days=i * 3), {1200: 200.0})
    rebuild_ftp_history(store, ATHLETE_ID)

    assert ftp_on(store, ATHLETE_ID, date(2025, 1, 1)) == pytest.approx(190.0, abs=40)


def test_ftp_on_falls_back_to_earliest_for_older_dates(store):
    """Antes do primeiro ponto, usar o mais antigo é melhor que descartar o treino."""
    for i in range(10):
        _add_activity(store, date(2024, 1, 1) + timedelta(days=i * 3), {1200: 200.0})
    rebuild_ftp_history(store, ATHLETE_ID)

    assert ftp_on(store, ATHLETE_ID, date(2020, 1, 1)) is not None


def test_ftp_on_returns_none_without_history(store):
    assert ftp_on(store, ATHLETE_ID, date(2024, 1, 1)) is None


def test_manual_entries_survive_rebuild(store):
    """O FTP informado pelo atleta é verdade e não pode ser apagado pelo recálculo."""
    store.conn.execute(
        """
        INSERT INTO ftp_history (id, athlete_id, effective_from, ftp_w, method, source)
        VALUES (uuid(), ?, ?, 217.0, 'informado', 'manual')
        """,
        [ATHLETE_ID, date(2026, 7, 25)],
    )
    for i in range(10):
        _add_activity(store, date(2024, 1, 1) + timedelta(days=i * 3), {1200: 200.0})
    rebuild_ftp_history(store, ATHLETE_ID)

    assert ftp_on(store, ATHLETE_ID, date(2026, 7, 25)) == pytest.approx(217.0)
