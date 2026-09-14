"""Testes do chat com o coach (US-14)."""
import duckdb
import pytest
from datetime import date, datetime, time

from ai.chat_coach import (
    HISTORY_TURNS,
    ChatCoach,
    ChatTurn,
    build_athlete_context,
)
from storage.catalog_store import CatalogStore
from storage.models import Activity

ATHLETE_ID = "11111111-1111-1111-1111-111111111111"


class FakeClient:
    """Cliente que devolve texto fixo e guarda o prompt recebido."""

    def __init__(self, reply="Resposta do treinador."):
        self.reply = reply
        self.prompt = None

    def generate(self, prompt, model="llama3"):
        self.prompt = prompt
        return f"  {self.reply}  "


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    store = CatalogStore(conn)
    store.initialize_schema()
    conn.execute(
        """
        INSERT INTO athletes (id, name, ftp_w, max_hr_bpm, resting_hr_bpm,
                              threshold_hr_bpm, weight_kg)
        VALUES (?, 'Teste', 217, 186, 53, 153, 71)
        """,
        [ATHLETE_ID],
    )
    yield conn
    conn.close()


# --- Montagem do prompt ----------------------------------------------------

def test_prompt_includes_athlete_context():
    coach = ChatCoach(FakeClient())
    prompt = coach.build_prompt("E amanhã?", "FTP 217 W")
    assert "FTP 217 W" in prompt


def test_prompt_includes_the_question():
    coach = ChatCoach(FakeClient())
    assert "Devo descansar?" in coach.build_prompt("Devo descansar?", "ctx")


def test_prompt_omits_history_section_when_empty():
    coach = ChatCoach(FakeClient())
    assert "Conversa até aqui" not in coach.build_prompt("Oi", "ctx")


def test_prompt_includes_history_with_readable_roles():
    coach = ChatCoach(FakeClient())
    history = [
        ChatTurn("user", "Quanto treinar?"),
        ChatTurn("assistant", "Umas 8 horas."),
    ]
    prompt = coach.build_prompt("E na semana que vem?", "ctx", history)

    assert "Atleta: Quanto treinar?" in prompt
    assert "Treinador: Umas 8 horas." in prompt


def test_prompt_truncates_long_history():
    """Histórico longo não pode empurrar o contexto do atleta fora da janela."""
    coach = ChatCoach(FakeClient())
    history = [ChatTurn("user", f"pergunta {i}") for i in range(40)]
    prompt = coach.build_prompt("nova", "ctx", history)

    assert "pergunta 39" in prompt
    assert "pergunta 0" not in prompt
    assert prompt.count("Atleta:") == HISTORY_TURNS + 1  # histórico + a nova


def test_prompt_forbids_inventing_missing_data():
    """A instrução de não supor dados ausentes é parte do contrato do prompt."""
    prompt = ChatCoach(FakeClient()).build_prompt("q", "ctx")
    assert "não tem essa informação" in prompt


def test_answer_strips_whitespace():
    client = FakeClient("Descanse hoje.")
    assert ChatCoach(client).answer("q", "ctx") == "Descanse hoje."


def test_answer_sends_prompt_to_client():
    client = FakeClient()
    ChatCoach(client).answer("Pergunta específica", "contexto único")
    assert "Pergunta específica" in client.prompt
    assert "contexto único" in client.prompt


# --- Contexto do atleta ----------------------------------------------------

def test_context_includes_profile_and_power_to_weight(db):
    context = build_athlete_context(db.cursor(), ATHLETE_ID)
    assert "FTP 217" in context
    assert "3.06 W/kg" in context


def test_context_marks_missing_values_explicitly(db):
    """Campo ausente aparece como 'não informado', nunca como zero."""
    db.execute("UPDATE athletes SET weight_kg = NULL")
    context = build_athlete_context(db.cursor(), ATHLETE_ID)
    assert "não informado" in context
    assert "W/kg" not in context


def test_context_includes_training_load(db):
    CatalogStore(db).upsert_training_load(
        ATHLETE_ID, date.today(), 56.8, 63.9, -7.1, 120.0
    )
    context = build_athlete_context(db.cursor(), ATHLETE_ID)
    assert "CTL 56.8" in context
    assert "TSB -7.1" in context


def test_context_includes_recent_health(db):
    CatalogStore(db).insert_health_daily(
        ATHLETE_ID, date.today(), hrv_rmssd_ms=30.0, hrv_status="UNBALANCED"
    )
    context = build_athlete_context(db.cursor(), ATHLETE_ID)
    assert "HRV 30" in context
    assert "UNBALANCED" in context


def test_context_includes_recent_activities(db):
    CatalogStore(db).upsert_activity(
        Activity(
            source="fit",
            sport_type="cycling",
            started_at=datetime.combine(date.today(), time(12, 0)).astimezone(),
            elapsed_time_s=3600,
            distance_m=40000,
            normalized_power_w=200.0,
            tss=85.0,
        ),
        ATHLETE_ID,
    )
    context = build_athlete_context(db.cursor(), ATHLETE_ID)
    assert "Últimos treinos:" in context
    assert "40.0 km" in context


def test_context_without_data_is_explicit(db):
    db.execute("DELETE FROM athletes")
    assert build_athlete_context(db.cursor(), ATHLETE_ID) == "Nenhum dado disponível."
