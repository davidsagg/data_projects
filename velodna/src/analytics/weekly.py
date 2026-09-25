"""
Resumo da semana executada — a unidade real de periodização do ciclismo.

O dia isolado engana. Uma terça de 180 TSS não diz nada sozinha: pode ser o pico
de uma semana pesada ou o único treino de uma semana perdida. Quem periodiza
pensa em blocos de sete dias, e é nessa granularidade que as perguntas fazem
sentido — subi a carga rápido demais? a semana foi realmente fácil no fácil e
forte no forte? fiz o que estava planejado?

Três leituras compõem o resumo:

**Volume e carga.** TSS, horas, quilômetros, elevação e número de sessões, com a
comparação contra a semana anterior e contra a média das quatro anteriores — um
número sozinho não informa tendência.

**Distribuição de intensidade.** O tempo em cada zona de potência, agregado na
semana e condensado no modelo de três zonas (fácil / limiar / forte) que a
literatura de polarização usa. Daí sai o veredito: polarizado, piramidal,
limiar ou base.

**Aderência.** Quanto do TSS planejado virou TSS executado.

A semana começa na segunda-feira e as zonas são as vigentes na data de cada
atividade — a mesma sessão pedalada em 2024 e em 2026 cai em zonas diferentes
porque o FTP mudou, e agregar contra um FTP único falsearia o histórico.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from analytics.ftp_history import ftp_on
from analytics.timeseries import load_series
from analytics.zones import build_power_zones, time_in_zones
from storage.query import rows

# Fronteiras do modelo de três zonas, em número de zona de Coggan.
# Z1-Z2 é o domínio moderado, Z3-Z4 o pesado (em torno do limiar) e Z5+ o severo.
EASY_ZONES = ("Z1", "Z2")
THRESHOLD_ZONES = ("Z3", "Z4")
HARD_ZONES = ("Z5", "Z6", "Z7")

# Acima deste percentual em zona fácil, e com trabalho forte presente, a semana
# é polarizada no sentido de Seiler.
POLARIZED_EASY_MIN_PCT = 75.0
POLARIZED_HARD_MIN_PCT = 5.0

# Acima disso em torno do limiar, a semana é "de limiar" — o padrão que a
# literatura associa a estagnação quando sustentado por muitas semanas.
THRESHOLD_HEAVY_PCT = 25.0

# Quantas semanas anteriores entram na média de comparação.
BASELINE_WEEKS = 4

# Aumento semanal de TSS acima do qual a rampa deixa de ser segura.
SAFE_RAMP_PCT = 15.0


@dataclass(frozen=True)
class ZoneBucket:
    """Tempo agregado numa faixa do modelo de três zonas."""

    seconds: int
    pct: float


@dataclass(frozen=True)
class DayEntry:
    """Um dia da semana com treino e saúde lado a lado.

    É o que alimenta a timeline unificada: os dois eixos compartilham a data,
    e é desse compartilhamento que sai a leitura que nenhuma plataforma entrega —
    a noite de 6h30 na quarta antecedeu o treino fraco de quinta.
    """

    date: date
    weekday: int
    tss: float
    planned_tss: float
    duration_s: int
    distance_m: float
    activity_count: int
    hrv_rmssd_ms: float | None = None
    sleep_hours: float | None = None
    resting_hr_bpm: int | None = None
    body_battery: int | None = None
    sleep_quality_score: int | None = None
    rpe: int | None = None
    feel: int | None = None
    notes: str | None = None

    @property
    def is_rest(self) -> bool:
        """Indica um dia sem nenhuma atividade registrada."""
        return self.activity_count == 0

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "weekday": self.weekday,
            "tss": self.tss,
            "planned_tss": self.planned_tss,
            "duration_s": self.duration_s,
            "distance_m": self.distance_m,
            "activity_count": self.activity_count,
            "is_rest": self.is_rest,
            "hrv_rmssd_ms": self.hrv_rmssd_ms,
            "sleep_hours": self.sleep_hours,
            "resting_hr_bpm": self.resting_hr_bpm,
            "body_battery": self.body_battery,
            "sleep_quality_score": self.sleep_quality_score,
            "rpe": self.rpe,
            "feel": self.feel,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class WeekSummary:
    """Resumo de uma semana de treino."""

    week_start: date
    week_end: date
    total_tss: float
    planned_tss: float
    total_hours: float
    total_km: float
    total_elevation_m: float
    session_count: int
    rest_days: int
    zone_seconds: dict[str, int] = field(default_factory=dict)
    easy: ZoneBucket | None = None
    threshold: ZoneBucket | None = None
    hard: ZoneBucket | None = None
    activities: list[dict] = field(default_factory=list)
    days: list[DayEntry] = field(default_factory=list)

    previous_tss: float | None = None
    baseline_tss: float | None = None

    @property
    def compliance_pct(self) -> float | None:
        """Percentual do TSS planejado que foi cumprido."""
        if self.planned_tss <= 0:
            return None
        return round(self.total_tss / self.planned_tss * 100, 1)

    @property
    def tss_change_pct(self) -> float | None:
        """Variação do TSS frente à semana anterior."""
        if not self.previous_tss:
            return None
        return round((self.total_tss / self.previous_tss - 1) * 100, 1)

    @property
    def ramp_is_safe(self) -> bool | None:
        """Indica se o aumento de carga ficou dentro do limite seguro."""
        change = self.tss_change_pct
        return None if change is None else change <= SAFE_RAMP_PCT

    @property
    def distribution(self) -> str:
        """Classifica o padrão de intensidade da semana.

        Returns:
            `polarizado`, `piramidal`, `limiar`, `base` ou `sem dados`.
        """
        if not self.easy or not self.easy.seconds and not self.hard:
            return "sem dados"

        easy = self.easy.pct if self.easy else 0.0
        threshold = self.threshold.pct if self.threshold else 0.0
        hard = self.hard.pct if self.hard else 0.0

        if easy + threshold + hard == 0:
            return "sem dados"

        if threshold >= THRESHOLD_HEAVY_PCT:
            return "limiar"
        if easy >= POLARIZED_EASY_MIN_PCT and hard >= POLARIZED_HARD_MIN_PCT:
            return "polarizado" if hard >= threshold else "piramidal"
        if hard < 1.0 and threshold < 10.0:
            return "base"
        return "piramidal"

    @property
    def avg_sleep_hours(self) -> float | None:
        """Média de sono da semana, ignorando noites sem registro."""
        return _mean([d.sleep_hours for d in self.days])

    @property
    def avg_hrv_ms(self) -> float | None:
        """HRV médio da semana, ignorando dias sem registro."""
        return _mean([d.hrv_rmssd_ms for d in self.days])

    def to_dict(self) -> dict:
        """Serializa o resumo para a API."""
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "total_tss": self.total_tss,
            "planned_tss": self.planned_tss,
            "compliance_pct": self.compliance_pct,
            "total_hours": self.total_hours,
            "total_km": self.total_km,
            "total_elevation_m": self.total_elevation_m,
            "session_count": self.session_count,
            "rest_days": self.rest_days,
            "previous_tss": self.previous_tss,
            "baseline_tss": self.baseline_tss,
            "tss_change_pct": self.tss_change_pct,
            "ramp_is_safe": self.ramp_is_safe,
            "distribution": self.distribution,
            "zone_seconds": self.zone_seconds,
            "intensity": {
                "easy": _bucket_dict(self.easy),
                "threshold": _bucket_dict(self.threshold),
                "hard": _bucket_dict(self.hard),
            },
            "activities": self.activities,
            "days": [day.to_dict() for day in self.days],
            "avg_sleep_hours": self.avg_sleep_hours,
            "avg_hrv_ms": self.avg_hrv_ms,
        }


def week_bounds(reference: date) -> tuple[date, date]:
    """Devolve a segunda e o domingo da semana que contém a data.

    Args:
        reference: qualquer dia da semana desejada.

    Returns:
        Par (segunda-feira, domingo).
    """
    monday = reference - timedelta(days=reference.weekday())
    return monday, monday + timedelta(days=6)


def build_week_summary(
    store,
    athlete_id: str,
    reference: date,
    with_zones: bool = True,
) -> WeekSummary:
    """Monta o resumo da semana que contém a data de referência.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        reference: qualquer dia da semana desejada.
        with_zones: calcula o tempo em zona percorrendo os streams; desligar
            torna a resposta muito mais rápida quando só o volume interessa.

    Returns:
        WeekSummary da semana pedida.
    """
    start, end = week_bounds(reference)
    activities = _activities_between(store.conn, athlete_id, start, end)

    zone_seconds = (
        _aggregate_zones(store, athlete_id, activities) if with_zones else {}
    )
    easy, threshold, hard = _split_intensity(zone_seconds)
    days = _build_days(store.conn, athlete_id, start, end, activities)

    return WeekSummary(
        week_start=start,
        week_end=end,
        total_tss=round(sum(a["tss"] or 0 for a in activities), 1),
        planned_tss=_planned_tss(store.conn, athlete_id, start, end),
        total_hours=round(
            sum(a["moving_time_s"] or a["elapsed_time_s"] or 0 for a in activities)
            / 3600,
            2,
        ),
        total_km=round(sum(a["distance_m"] or 0 for a in activities) / 1000, 1),
        total_elevation_m=round(sum(a["elevation_gain_m"] or 0 for a in activities), 0),
        session_count=len(activities),
        rest_days=_rest_days(activities, start),
        zone_seconds=zone_seconds,
        easy=easy,
        threshold=threshold,
        hard=hard,
        activities=activities,
        days=days,
        previous_tss=_tss_between(
            store.conn, athlete_id, start - timedelta(days=7), start - timedelta(days=1)
        ),
        baseline_tss=_baseline_tss(store.conn, athlete_id, start),
    )


def build_week_series(
    store,
    athlete_id: str,
    weeks: int = 12,
    reference: date | None = None,
    with_zones: bool = False,
) -> list[WeekSummary]:
    """Monta o resumo das últimas N semanas, da mais antiga para a mais recente.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        weeks: quantas semanas incluir, contando a da referência.
        reference: semana final; usa hoje se omitido.
        with_zones: calcula tempo em zona de cada semana (bem mais lento).

    Returns:
        Lista de WeekSummary em ordem cronológica.
    """
    reference = reference or date.today()
    return [
        build_week_summary(
            store, athlete_id, reference - timedelta(weeks=offset), with_zones
        )
        for offset in reversed(range(weeks))
    ]


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _mean(values: list) -> float | None:
    """Média dos valores presentes, ou None se não houver nenhum."""
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 2) if present else None


def _build_days(
    conn,
    athlete_id: str,
    start: date,
    end: date,
    activities: list[dict],
) -> list[DayEntry]:
    """Monta os sete dias da semana com treino e saúde na mesma linha.

    Os dois lados são incompletos por natureza — há dia de descanso sem treino e
    há dia sem sincronização do Garmin. O eixo é a data, e cada lado preenche o
    que tem; nenhum dia some por falta de um dos dois.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.
        start: segunda-feira da semana.
        end: domingo da semana.
        activities: atividades já carregadas do período.

    Returns:
        Sete `DayEntry`, de segunda a domingo.
    """
    health = {
        row["date"]: row
        for row in rows(
            conn,
            """
            SELECT date, hrv_rmssd_ms, sleep_hours, resting_hr_bpm,
                   body_battery, sleep_quality_score
            FROM health_metrics
            WHERE athlete_id = ? AND date BETWEEN ? AND ?
            """,
            [athlete_id, start, end],
        )
    }

    planned = {
        row["date"]: row["planned_tss"]
        for row in rows(
            conn,
            """
            SELECT date, COALESCE(SUM(planned_tss), 0) AS planned_tss
            FROM planned_workouts
            WHERE athlete_id = ? AND date BETWEEN ? AND ?
            GROUP BY date
            """,
            [athlete_id, start, end],
        )
    }

    # Feedback da atividade vence o do dia: quando os dois existem, o do treino
    # é o mais específico. A nota do dia cobre justamente os dias sem treino.
    feedback: dict[date, dict] = {}
    for row in rows(
        conn,
        """
        SELECT date, activity_id, rpe, feel, notes
        FROM activity_feedback
        WHERE athlete_id = ? AND date BETWEEN ? AND ?
        ORDER BY date, activity_id NULLS FIRST
        """,
        [athlete_id, start, end],
    ):
        feedback[row["date"]] = row

    by_date: dict[date, list[dict]] = {}
    for activity in activities:
        by_date.setdefault(activity["date"], []).append(activity)

    entries: list[DayEntry] = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        done = by_date.get(day, [])
        vitals = health.get(day, {})
        felt = feedback.get(day, {})
        entries.append(
            DayEntry(
                date=day,
                weekday=offset,
                tss=round(sum(a["tss"] or 0 for a in done), 1),
                planned_tss=round(float(planned.get(day) or 0), 1),
                duration_s=sum(
                    a["moving_time_s"] or a["elapsed_time_s"] or 0 for a in done
                ),
                distance_m=round(sum(a["distance_m"] or 0 for a in done), 1),
                activity_count=len(done),
                hrv_rmssd_ms=vitals.get("hrv_rmssd_ms"),
                sleep_hours=vitals.get("sleep_hours"),
                resting_hr_bpm=vitals.get("resting_hr_bpm"),
                body_battery=vitals.get("body_battery"),
                sleep_quality_score=vitals.get("sleep_quality_score"),
                rpe=felt.get("rpe"),
                feel=felt.get("feel"),
                notes=felt.get("notes"),
            )
        )
    return entries


def _bucket_dict(bucket: ZoneBucket | None) -> dict | None:
    return {"seconds": bucket.seconds, "pct": bucket.pct} if bucket else None


def _activities_between(conn, athlete_id: str, start: date, end: date) -> list[dict]:
    """Atividades da semana, com o que o resumo precisa."""
    return rows(
        conn,
        """
        SELECT id, CAST(started_at AS DATE) AS date, started_at, sport_type,
               elapsed_time_s, moving_time_s, distance_m, elevation_gain_m,
               tss, tss_source, normalized_power_w, intensity_factor,
               avg_hr_bpm, efficiency_factor
        FROM activities
        WHERE athlete_id = ? AND CAST(started_at AS DATE) BETWEEN ? AND ?
        ORDER BY started_at
        """,
        [athlete_id, start, end],
    )


def _planned_tss(conn, athlete_id: str, start: date, end: date) -> float:
    """Soma do TSS planejado para a semana."""
    found = conn.execute(
        """
        SELECT COALESCE(SUM(planned_tss), 0) FROM planned_workouts
        WHERE athlete_id = ? AND date BETWEEN ? AND ?
        """,
        [athlete_id, start, end],
    ).fetchone()
    return round(float(found[0] or 0), 1)


def _tss_between(conn, athlete_id: str, start: date, end: date) -> float | None:
    """TSS total de um intervalo, ou None se não houve atividade."""
    found = conn.execute(
        """
        SELECT SUM(tss) FROM activities
        WHERE athlete_id = ? AND CAST(started_at AS DATE) BETWEEN ? AND ?
        """,
        [athlete_id, start, end],
    ).fetchone()
    return round(float(found[0]), 1) if found and found[0] else None


def _baseline_tss(conn, athlete_id: str, week_start: date) -> float | None:
    """Média de TSS das semanas anteriores, para dar escala à semana atual."""
    totals = [
        _tss_between(
            conn,
            athlete_id,
            week_start - timedelta(days=7 * offset),
            week_start - timedelta(days=7 * (offset - 1) + 1),
        )
        for offset in range(1, BASELINE_WEEKS + 1)
    ]
    present = [t for t in totals if t is not None]
    return round(sum(present) / len(present), 1) if present else None


def _rest_days(activities: list[dict], start: date) -> int:
    """Dias da semana sem nenhuma atividade registrada."""
    trained = {a["date"] for a in activities}
    return sum(1 for offset in range(7) if start + timedelta(days=offset) not in trained)


def _aggregate_zones(store, athlete_id: str, activities: list[dict]) -> dict[str, int]:
    """Soma o tempo em zona de potência de todas as atividades da semana.

    Cada atividade é classificada contra o FTP vigente na **sua** data: agregar
    tudo contra o FTP de hoje deslocaria as sessões antigas de zona.
    """
    totals: dict[str, int] = {}

    for activity in activities:
        ftp = ftp_on(store, athlete_id, activity["date"])
        if not ftp:
            continue
        series = load_series(store.conn, activity["id"])
        if not series.has_data("power"):
            continue
        for zone, seconds in time_in_zones(series, build_power_zones(ftp)).items():
            totals[zone] = totals.get(zone, 0) + seconds

    return totals


def _split_intensity(
    zone_seconds: dict[str, int],
) -> tuple[ZoneBucket | None, ZoneBucket | None, ZoneBucket | None]:
    """Condensa as sete zonas de Coggan no modelo de três domínios."""
    total = sum(zone_seconds.values())
    if total == 0:
        return None, None, None

    def bucket(names: tuple[str, ...]) -> ZoneBucket:
        seconds = sum(zone_seconds.get(name, 0) for name in names)
        return ZoneBucket(seconds=seconds, pct=round(seconds / total * 100, 1))

    return bucket(EASY_ZONES), bucket(THRESHOLD_ZONES), bucket(HARD_ZONES)
