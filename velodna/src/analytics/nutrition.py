"""
Alimentação no ciclo — ingestão contra gasto, semana a semana.

O dado vem do MacroFactor por export manual (`ingestion.macrofactor`), e tem
uma propriedade que manda em tudo aqui: **o registro é esparso**. Há meses com
comida anotada quase todo dia e meses com três dias. Por isso:

- as médias de ingestão são por **dia registrado**, nunca por dia do
  calendário — dividir por sete trataria dia sem registro como jejum;
- o balanço compara cada dia registrado com o gasto **daquele dia**;
- cada semana diz quantos dias tem, e só é `reliable` a partir de
  `MIN_DAYS_PER_WEEK`: média de um dia não descreve uma semana.

O export também não marca **dia parcial**: quem anota só o café da manhã deixa
um dia de 375 kcal, e ele puxaria a média do ciclo para um déficit que não
existiu. Dia abaixo de `MIN_FULL_DAY_KCAL` não entra em média nem em balanço —
no acervo real não há nada entre 400 e 1.000 kcal, então o corte não é
delicado.

O gasto e a tendência de peso existem todo dia (o MacroFactor os estima mesmo
sem registro), então essas duas séries são contínuas.
"""
from __future__ import annotations

from datetime import date, timedelta

from storage.query import rows

# Abaixo disso a média da semana é anedota. Quatro dias pegam ao menos um do
# fim de semana ou três úteis seguidos.
MIN_DAYS_PER_WEEK = 4

# Abaixo disso o dia é registro parcial, não um dia de pouca comida.
MIN_FULL_DAY_KCAL = 800


def is_full_day(calories_kcal: float | None) -> bool:
    """Dia com registro que dá para tomar como o dia inteiro."""
    return calories_kcal is not None and calories_kcal >= MIN_FULL_DAY_KCAL


def _mean(values: list[float | None], digits: int = 0) -> float | None:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), digits)


def _summarize(days: list[dict]) -> dict:
    """Médias de um conjunto de dias, com a ingestão só nos dias completos."""
    logged = [d for d in days if is_full_day(d["calories_kcal"])]
    partial = [
        d for d in days
        if d["calories_kcal"] is not None and not is_full_day(d["calories_kcal"])
    ]
    return {
        "days_logged": len(logged),
        "days_partial": len(partial),
        "avg_calories_kcal": _mean([d["calories_kcal"] for d in logged]),
        "avg_protein_g": _mean([d["protein_g"] for d in logged]),
        "avg_carbs_g": _mean([d["carbs_g"] for d in logged]),
        "avg_fat_g": _mean([d["fat_g"] for d in logged]),
        "avg_expenditure_kcal": _mean([d["expenditure_kcal"] for d in days]),
        "avg_balance_kcal": _mean(
            [
                d["calories_kcal"] - d["expenditure_kcal"]
                for d in logged
                if d["expenditure_kcal"] is not None
            ]
        ),
        "target_calories_kcal": _mean([d["target_calories_kcal"] for d in days]),
        "target_protein_g": _mean([d["target_protein_g"] for d in days]),
    }


def build_nutrition_cycle(
    conn, athlete_id: str, first_monday: date, weeks: int, reference: date
) -> dict:
    """Alimentação e peso das `weeks` semanas a partir de `first_monday`.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.
        first_monday: segunda-feira da primeira semana da janela.
        weeks: número de semanas (segunda a domingo).
        reference: último dia que conta — o que vem depois ainda não aconteceu.

    Returns:
        `weeks` (uma entrada por semana, sempre, mesmo sem dado), `summary` da
        janela inteira e `min_days_per_week`. `has_data` é falso quando não há
        nenhum dia importado na janela.
    """
    last_day = min(first_monday + timedelta(weeks=weeks) - timedelta(days=1), reference)
    days = rows(
        conn,
        """
        SELECT date, calories_kcal, protein_g, carbs_g, fat_g, expenditure_kcal,
               trend_weight_kg, target_calories_kcal, target_protein_g
        FROM nutrition_daily
        WHERE athlete_id = ? AND date BETWEEN ? AND ?
        ORDER BY date
        """,
        [athlete_id, first_monday, last_day],
    )

    weekly = []
    for index in range(weeks):
        start = first_monday + timedelta(weeks=index)
        end = start + timedelta(days=6)
        in_week = [d for d in days if start <= d["date"] <= end]
        summary = _summarize(in_week)
        trend = [d["trend_weight_kg"] for d in in_week if d["trend_weight_kg"]]
        weekly.append(
            {
                "week_start": start.isoformat(),
                "week_end": end.isoformat(),
                **summary,
                "reliable": summary["days_logged"] >= MIN_DAYS_PER_WEEK,
                # O peso da semana é o do último dia dela: a tendência já é
                # suavizada, tirar média de novo só a atrasaria.
                "trend_weight_kg": round(trend[-1], 2) if trend else None,
            }
        )

    trend = [d["trend_weight_kg"] for d in days if d["trend_weight_kg"]]
    total_days = (last_day - first_monday).days + 1 if last_day >= first_monday else 0
    return {
        "has_data": bool(days),
        "min_days_per_week": MIN_DAYS_PER_WEEK,
        "weeks": weekly,
        "summary": {
            **_summarize(days),
            "days_total": total_days,
            "trend_weight_start_kg": round(trend[0], 2) if trend else None,
            "trend_weight_end_kg": round(trend[-1], 2) if trend else None,
            "last_logged_on": next(
                (
                    d["date"].isoformat()
                    for d in reversed(days)
                    if is_full_day(d["calories_kcal"])
                ),
                None,
            ),
        },
    }
