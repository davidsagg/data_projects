"""
Panorama de um ciclo — as últimas N semanas lidas contra as metas.

O Resumo responde "como foi esta semana?". O Panorama responde a pergunta do
ciclo: "como estou indo em relação ao que quero, nos últimos três meses?". A
diferença não é de layout, é de horizonte — treze semanas é o tamanho de um
bloco de preparação, e é nessa escala que volume, peso e FTP se movem o
suficiente para serem lidos.

O que entra:

- **Atleta agora**: FTP vigente, peso, W/kg — e o W/kg projetado no peso alvo,
  que mostra o ganho que vem só da balança.
- **Metas**: cada uma com a distância até ela (`analytics.goals`).
- **Volume por modalidade**: rua, rolo, força e outros, semana a semana.
- **Maior esforço**: a sessão de maior TSS, comparada ao treino típico.
- **Condicionamento**: CTL diário da janela, com os marcos por cima.
- **Zonas**: o tempo do ciclo em cada zona de potência, só ciclismo.
- **Marcos**: exames, planos, provas e achados — e os testes de CP registrados.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from analytics.ftp_history import POWER_SPORTS, ftp_on
from analytics.goals import evaluate_goals
from analytics.modality import MODALITIES, MODALITY_LABELS, classify
from analytics.weekly import (
    _aggregate_zones,
    _bucket_dict,
    _median,
    _split_intensity,
    classify_distribution,
    week_bounds,
)
from analytics.zones import build_power_zones
from storage.query import row, rows

DEFAULT_WEEKS = 13
RECENT_ACTIVITIES = 12

# Peso medido pelo Garmin vale sobre o cadastro se for recente o bastante.
WEIGHT_FRESH_DAYS = 30


def build_panorama(
    store,
    athlete_id: str,
    weeks: int = DEFAULT_WEEKS,
    reference: date | None = None,
    with_zones: bool = True,
) -> dict:
    """Monta o panorama das últimas `weeks` semanas, terminando na da referência.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        weeks: número de semanas (segunda a domingo), contando a da referência.
        reference: qualquer dia da última semana; hoje se omitido.
        with_zones: percorre os streams para o tempo em zona (mais lento).

    Returns:
        Dicionário serializável com todas as seções do panorama.
    """
    reference = reference or date.today()
    last_monday, last_sunday = week_bounds(reference)
    first_monday = last_monday - timedelta(weeks=weeks - 1)

    activities = _activities(store.conn, athlete_id, first_monday, last_sunday)
    weekly = _weekly_volume(activities, first_monday, weeks)

    # A semana em curso ainda está incompleta: entra no gráfico, não na média.
    complete = [w for w in weekly if date.fromisoformat(w["week_end"]) < reference]
    avg_hours = (
        round(sum(w["total_hours"] for w in complete) / len(complete), 2)
        if complete
        else None
    )

    ftp = ftp_on(store, athlete_id, reference)
    weight = _current_weight(store.conn, athlete_id, reference)
    w_per_kg = round(ftp / weight, 2) if ftp and weight else None
    ctl_series = _ctl_series(store.conn, athlete_id, first_monday, last_sunday)
    latest_ctl = next(
        (p["ctl"] for p in reversed(ctl_series) if p["ctl"] is not None), None
    )

    goals = store.get_goals(athlete_id)
    goal_progress = evaluate_goals(
        goals,
        {
            "weight_kg": weight,
            "weekly_hours": avg_hours,
            "ftp_w": ftp,
            "w_per_kg": w_per_kg,
            "ctl": latest_ctl,
        },
    )
    goal_weight = next(
        (g["target"] for g in goals if g["metric"] == "weight_kg"), None
    )

    cycling = [a for a in activities if a["sport_type"] in POWER_SPORTS]
    zone_seconds = (
        _aggregate_zones(store, athlete_id, cycling) if with_zones else {}
    )
    easy, threshold, hard = _split_intensity(zone_seconds)

    return {
        "window": {
            "start": first_monday.isoformat(),
            "end": last_sunday.isoformat(),
            "weeks": weeks,
            "complete_weeks": len(complete),
        },
        "athlete": {
            "ftp_w": ftp,
            "ftp_w_at_start": ftp_on(store, athlete_id, first_monday),
            "weight_kg": weight,
            "w_per_kg": w_per_kg,
            "goal_weight_kg": goal_weight,
            "w_per_kg_at_goal": (
                round(ftp / goal_weight, 2) if ftp and goal_weight else None
            ),
            "ctl": latest_ctl,
        },
        "goals": goal_progress,
        "volume": {
            "avg_weekly_hours": avg_hours,
            "modalities": [
                {"key": key, "label": MODALITY_LABELS[key]} for key in MODALITIES
            ],
            "weeks": weekly,
        },
        "biggest_effort": _biggest_effort(activities),
        "ctl_series": ctl_series,
        "zones": {
            "ftp_w": ftp,
            "definitions": [
                {
                    "zone": z.name,
                    "label": z.label,
                    "low": z.low,
                    # A última zona não tem teto, e JSON não tem infinito.
                    "high": z.high if math.isfinite(z.high) else None,
                }
                for z in build_power_zones(ftp)
            ]
            if ftp
            else [],
            "seconds": zone_seconds,
            "intensity": {
                "easy": _bucket_dict(easy),
                "threshold": _bucket_dict(threshold),
                "hard": _bucket_dict(hard),
            },
            "distribution": classify_distribution(easy, threshold, hard),
        },
        "recent_activities": [
            _activity_row(a) for a in reversed(activities[-RECENT_ACTIVITIES:])
        ],
        "milestones": _milestones(store, athlete_id),
    }


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _activities(conn, athlete_id: str, start: date, end: date) -> list[dict]:
    """Atividades da janela, com a modalidade já resolvida."""
    found = rows(
        conn,
        """
        SELECT id, name, CAST(started_at AS DATE) AS date, sport_type,
               strava_sport_type, trainer,
               COALESCE(moving_time_s, elapsed_time_s, 0) AS duration_s,
               distance_m, elevation_gain_m, tss, tss_source,
               normalized_power_w, intensity_factor, avg_cadence_rpm
        FROM activities
        WHERE athlete_id = ? AND CAST(started_at AS DATE) BETWEEN ? AND ?
        ORDER BY started_at
        """,
        [athlete_id, start, end],
    )
    for activity in found:
        activity["id"] = str(activity["id"])
        activity["modality"] = classify(
            activity["sport_type"], activity["strava_sport_type"], activity["trainer"]
        )
    return found


def _weekly_volume(activities: list[dict], first_monday: date, weeks: int) -> list[dict]:
    """Horas por modalidade, TSS e elevação de cada semana da janela."""
    result = []
    for offset in range(weeks):
        start = first_monday + timedelta(weeks=offset)
        end = start + timedelta(days=6)
        inside = [a for a in activities if start <= a["date"] <= end]
        hours = {key: 0.0 for key in MODALITIES}
        for activity in inside:
            hours[activity["modality"]] += activity["duration_s"] / 3600
        result.append(
            {
                "week_start": start.isoformat(),
                "week_end": end.isoformat(),
                "hours": {key: round(value, 2) for key, value in hours.items()},
                "total_hours": round(sum(hours.values()), 2),
                "tss": round(sum(a["tss"] or 0 for a in inside), 1),
                "sessions": len(inside),
                "elevation_m": round(sum(a["elevation_gain_m"] or 0 for a in inside)),
                "km": round(sum(a["distance_m"] or 0 for a in inside) / 1000, 1),
            }
        )
    return result


def _biggest_effort(activities: list[dict]) -> dict | None:
    """A sessão de maior TSS, comparada à mediana das sessões de ciclismo.

    A comparação é contra o treino típico, e não contra a semana: dizer que um
    pedal valeu "2× a semana mediana" mistura unidades — uma sessão contra sete
    dias de sessões.
    """
    scored = [a for a in activities if a["tss"]]
    if not scored:
        return None
    top = max(scored, key=lambda a: a["tss"])
    median = _median(
        [a["tss"] for a in scored if a["sport_type"] in POWER_SPORTS]
    )
    return {
        **_activity_row(top),
        "median_session_tss": median,
        "ratio_to_median": round(top["tss"] / median, 1) if median else None,
    }


def _activity_row(activity: dict) -> dict:
    """Linha da tabela de atividades — só o que a tela mostra."""
    return {
        "id": activity["id"],
        "name": activity["name"],
        "date": activity["date"].isoformat(),
        "sport_type": activity["sport_type"],
        "modality": activity["modality"],
        "duration_s": activity["duration_s"],
        "distance_m": activity["distance_m"],
        "elevation_gain_m": activity["elevation_gain_m"],
        "tss": activity["tss"],
        "tss_source": activity["tss_source"],
        "normalized_power_w": activity["normalized_power_w"],
        "intensity_factor": activity["intensity_factor"],
        "avg_cadence_rpm": activity["avg_cadence_rpm"],
    }


def _current_weight(conn, athlete_id: str, reference: date) -> float | None:
    """Peso atual: a pesagem recente do Garmin, senão o cadastro do atleta."""
    measured = row(
        conn,
        """
        SELECT weight_kg FROM health_metrics
        WHERE athlete_id = ? AND weight_kg IS NOT NULL
          AND date BETWEEN ? AND ?
        ORDER BY date DESC LIMIT 1
        """,
        [athlete_id, reference - timedelta(days=WEIGHT_FRESH_DAYS), reference],
    )
    if measured:
        return float(measured["weight_kg"])
    profile = row(conn, "SELECT weight_kg FROM athletes WHERE id = ?", [athlete_id])
    return float(profile["weight_kg"]) if profile and profile["weight_kg"] else None


def _ctl_series(conn, athlete_id: str, start: date, end: date) -> list[dict]:
    """CTL/ATL/TSB diários da janela."""
    return [
        {**point, "date": point["date"].isoformat()}
        for point in rows(
            conn,
            """
            SELECT date, ctl, atl, tsb, daily_tss FROM training_load
            WHERE athlete_id = ? AND date BETWEEN ? AND ?
            ORDER BY date
            """,
            [athlete_id, start, end],
        )
    ]


def _milestones(store, athlete_id: str) -> list[dict]:
    """Marcos cadastrados e testes de CP, do mais recente ao mais antigo.

    Os testes de potência crítica já estão no histórico de FTP; repeti-los como
    marco à mão seria cadastro duplicado. Entram aqui sintetizados.
    """
    found = [
        {**m, "date": m["date"].isoformat(), "origin": "milestone"}
        for m in store.get_milestones(athlete_id)
    ]
    tests = rows(
        store.conn,
        """
        SELECT effective_from AS date, ftp_w, cp_w, w_prime_j FROM ftp_history
        WHERE athlete_id = ? AND source = 'test'
        ORDER BY effective_from
        """,
        [athlete_id],
    )
    for test in tests:
        measurements = {"ftp_w": round(test["ftp_w"], 1)}
        if test["cp_w"]:
            measurements["cp_w"] = round(test["cp_w"], 1)
        if test["w_prime_j"]:
            measurements["w_prime_kj"] = round(test["w_prime_j"] / 1000, 2)
        found.append(
            {
                "id": f"cp-test-{test['date'].isoformat()}",
                "date": test["date"].isoformat(),
                "kind": "teste",
                "title": "Teste de potência crítica",
                "summary": None,
                "measurements": measurements,
                "source": "protocolo 1 min + 12 min",
                "origin": "ftp_history",
            }
        )
    return sorted(found, key=lambda m: m["date"], reverse=True)
