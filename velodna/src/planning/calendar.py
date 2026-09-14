"""
Calendário de treino — planejado versus realizado.

O valor do calendário não é listar treinos, é expor a diferença entre o que foi
planejado e o que aconteceu. Um bloco cumprido a 60% não é um bloco cumprido, e
essa informação some quando se olha só o que foi executado.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from storage.query import rows

# Abaixo deste percentual do TSS planejado, o dia conta como não cumprido.
COMPLIANCE_THRESHOLD_PCT = 80.0


@dataclass(frozen=True)
class CalendarDay:
    """Um dia do calendário, com o planejado e o realizado lado a lado."""

    date: date
    planned_tss: float
    actual_tss: float
    planned_workouts: list[dict]
    activities: list[dict]

    @property
    def compliance_pct(self) -> float | None:
        """Percentual do TSS planejado que foi cumprido."""
        if self.planned_tss <= 0:
            return None
        return round(self.actual_tss / self.planned_tss * 100, 1)

    @property
    def status(self) -> str:
        """Classificação do dia frente ao plano.

        Um dia futuro nunca é falha: enquanto a data não chegou, o treino está
        agendado, não perdido.
        """
        is_future = self.date > date.today()

        if self.planned_tss <= 0:
            if self.actual_tss > 0:
                return "unplanned"
            return "rest"

        if self.actual_tss <= 0:
            return "scheduled" if is_future else "missed"

        compliance = self.compliance_pct or 0
        if compliance >= COMPLIANCE_THRESHOLD_PCT:
            return "completed"
        return "in_progress" if is_future else "partial"


def build_calendar(conn, athlete_id: str, start: date, end: date) -> list[CalendarDay]:
    """Monta o calendário do período, dia a dia.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.
        start: primeiro dia, inclusive.
        end: último dia, inclusive.

    Returns:
        Um `CalendarDay` por data do intervalo, incluindo dias vazios.
    """
    planned = _planned_by_date(conn, athlete_id, start, end)
    actual = _activities_by_date(conn, athlete_id, start, end)

    days: list[CalendarDay] = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        day_planned = planned.get(day, [])
        day_actual = actual.get(day, [])
        days.append(
            CalendarDay(
                date=day,
                planned_tss=round(
                    sum(w["planned_tss"] or 0 for w in day_planned), 1
                ),
                actual_tss=round(sum(a["tss"] or 0 for a in day_actual), 1),
                planned_workouts=day_planned,
                activities=day_actual,
            )
        )
    return days


def create_planned_workout(conn, athlete_id: str, workout: dict) -> str:
    """Cria um treino planejado.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.
        workout: campos do treino; `date` é obrigatório.

    Returns:
        UUID do treino criado.
    """
    workout_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO planned_workouts (
            id, athlete_id, date, name, sport_type, planned_tss,
            planned_duration_s, planned_if, description, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned')
        """,
        [
            workout_id,
            athlete_id,
            workout["date"],
            workout.get("name"),
            workout.get("sport_type", "cycling"),
            workout.get("planned_tss"),
            workout.get("planned_duration_s"),
            workout.get("planned_if"),
            workout.get("description"),
        ],
    )
    return workout_id


def reconcile(conn, athlete_id: str, start: date, end: date) -> int:
    """Liga cada treino planejado à atividade executada no mesmo dia.

    Quando há mais de uma atividade no dia, vence a de maior TSS — é a que
    corresponde à sessão principal do plano.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.
        start: primeiro dia, inclusive.
        end: último dia, inclusive.

    Returns:
        Número de treinos conciliados.
    """
    before = _count_reconciled(conn, athlete_id, start, end)

    conn.execute(
        """
        UPDATE planned_workouts
        SET activity_id = (
                SELECT a.id FROM activities a
                WHERE a.athlete_id = planned_workouts.athlete_id
                  AND CAST(a.started_at AS DATE) = planned_workouts.date
                ORDER BY a.tss DESC NULLS LAST
                LIMIT 1
            ),
            status = 'completed'
        WHERE athlete_id = ?
          AND date BETWEEN ? AND ?
          AND activity_id IS NULL
          AND EXISTS (
                SELECT 1 FROM activities a
                WHERE a.athlete_id = planned_workouts.athlete_id
                  AND CAST(a.started_at AS DATE) = planned_workouts.date
            )
        """,
        [athlete_id, start, end],
    )

    return _count_reconciled(conn, athlete_id, start, end) - before


def _count_reconciled(conn, athlete_id: str, start: date, end: date) -> int:
    """Conta treinos planejados já ligados a uma atividade no período."""
    return conn.execute(
        """
        SELECT COUNT(*) FROM planned_workouts
        WHERE athlete_id = ? AND date BETWEEN ? AND ? AND activity_id IS NOT NULL
        """,
        [athlete_id, start, end],
    ).fetchone()[0]


def _planned_by_date(conn, athlete_id: str, start: date, end: date) -> dict:
    """Agrupa os treinos planejados do período por data."""
    records = rows(
        conn,
        """
        SELECT id, date, name, sport_type, planned_tss, planned_duration_s,
               planned_if, description, status, activity_id
        FROM planned_workouts
        WHERE athlete_id = ? AND date BETWEEN ? AND ?
        ORDER BY date
        """,
        [athlete_id, start, end],
    )

    grouped: dict[date, list[dict]] = {}
    for item in records:
        grouped.setdefault(item["date"], []).append(item)
    return grouped


def _activities_by_date(conn, athlete_id: str, start: date, end: date) -> dict:
    """Agrupa as atividades executadas do período por data."""
    records = rows(
        conn,
        """
        SELECT id, CAST(started_at AS DATE) AS date, sport_type, elapsed_time_s,
               distance_m, tss, tss_source, normalized_power_w, intensity_factor
        FROM activities
        WHERE athlete_id = ? AND CAST(started_at AS DATE) BETWEEN ? AND ?
        ORDER BY started_at
        """,
        [athlete_id, start, end],
    )

    grouped: dict[date, list[dict]] = {}
    for item in records:
        grouped.setdefault(item["date"], []).append(item)
    return grouped
