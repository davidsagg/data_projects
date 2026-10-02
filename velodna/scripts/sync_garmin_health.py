"""
Sincroniza métricas diárias de saúde do Garmin Connect.

O Garmin limita por IP (HTTP 429), então o backfill é incremental e retomável:
por padrão só busca os dias que ainda não estão no banco. Um histórico longo
deve ser puxado em lotes, com `--days`.

Uso:
    # últimos 30 dias que faltam
    .venv/bin/python scripts/sync_garmin_health.py

    # janela específica
    .venv/bin/python scripts/sync_garmin_health.py --start 2026-01-01 --end 2026-07-25

    # refazer dias já gravados
    .venv/bin/python scripts/sync_garmin_health.py --days 60 --overwrite
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from ingestion.garmin_health_client import (  # noqa: E402
    GarminHealthClient,
    HealthDaily,
    resolve_credentials,
)
from storage.catalog_store import CatalogStore  # noqa: E402

DB_PATH = os.getenv("DB_PATH", "data/velodna.duckdb")


def persist(store: CatalogStore, athlete_id: str, daily: HealthDaily) -> None:
    """Grava um dia de métricas no catálogo.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        daily: métricas do dia.
    """
    store.insert_health_daily(
        athlete_id,
        daily.date,
        hrv_rmssd_ms=daily.hrv_rmssd_ms,
        hrv_status=daily.hrv_status,
        resting_hr_bpm=daily.resting_hr_bpm,
        sleep_hours=daily.sleep_duration_h,
        sleep_quality_score=daily.sleep_score,
        deep_sleep_min=daily.deep_sleep_min,
        rem_sleep_min=daily.rem_sleep_min,
        body_battery=daily.body_battery_max,
        body_battery_min=daily.body_battery_min,
        stress_level=daily.stress_avg,
        vo2max_estimated=daily.vo2max_estimated,
        steps=daily.steps,
        source=daily.source,
        # Peso só entra quando veio: o dia sem pesagem não pode apagar a que o
        # passo de pesagens gravou (um --overwrite faria exatamente isso).
        **({"weight_kg": daily.weight_kg} if daily.weight_kg else {}),
    )


def sync_weigh_ins(client, athlete_id: str, start: date, end: date) -> int:
    """Grava as pesagens do intervalo no dia correspondente.

    É um passo à parte do diário porque o peso vem de outro endpoint e cobre o
    intervalo numa requisição só — por isso roda sempre, mesmo quando não falta
    nenhum dia de HRV e sono.

    Args:
        client: GarminHealthClient autenticado.
        athlete_id: UUID do atleta.
        start: primeiro dia, inclusive.
        end: último dia, inclusive.

    Returns:
        Número de pesagens gravadas.
    """
    weigh_ins = client.get_weigh_ins(start, end)
    if not weigh_ins:
        return 0
    with duckdb.connect(DB_PATH) as conn:
        store = CatalogStore(conn)
        for day, kg in sorted(weigh_ins.items()):
            store.insert_health_daily(athlete_id, day, weight_kg=kg)
    last_day = max(weigh_ins)
    print(f"Pesagens: {len(weigh_ins)} · última {weigh_ins[last_day]:.1f} kg em {last_day}")
    return len(weigh_ins)


def missing_days(conn, athlete_id: str, start: date, end: date) -> list[date]:
    """Lista os dias do intervalo que ainda não estão no banco.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.
        start: primeiro dia, inclusive.
        end: último dia, inclusive.

    Returns:
        Datas faltantes em ordem cronológica.
    """
    existing = {
        row[0]
        for row in conn.execute(
            # Dia com só a pesagem ainda conta como faltante: HRV e sono dele
            # não foram buscados.
            "SELECT date FROM health_metrics WHERE athlete_id = ? "
            "AND date BETWEEN ? AND ? AND (hrv_rmssd_ms IS NOT NULL "
            "OR sleep_hours IS NOT NULL OR resting_hr_bpm IS NOT NULL "
            "OR body_battery IS NOT NULL OR steps IS NOT NULL)",
            [athlete_id, start, end],
        ).fetchall()
    }
    total_days = (end - start).days + 1
    return [
        day
        for offset in range(total_days)
        if (day := start + timedelta(days=offset)) not in existing
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30, help="Janela retroativa em dias")
    parser.add_argument(
        "--start", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    )
    parser.add_argument(
        "--end", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Refaz dias já gravados"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Pausa entre dias, em segundos"
    )
    parser.add_argument(
        "--weight-days",
        type=int,
        default=365,
        help="Janela de pesagens a buscar (uma requisição só)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=50,
        help="Dias por lote antes de liberar o banco (DuckDB é single-writer)",
    )
    args = parser.parse_args()

    credentials = resolve_credentials()
    if credentials is None:
        print("ERRO: GARMIN_EMAIL/GARMIN_PASSWORD não configurados no .env")
        return 1

    end = args.end or date.today()
    start = args.start or (end - timedelta(days=args.days - 1))

    # A conexão é aberta só para descobrir o que falta e liberada em seguida:
    # o DuckDB aceita um único escritor, e segurar o lock durante um backfill
    # de meia hora impede qualquer outro trabalho no banco.
    with duckdb.connect(DB_PATH) as conn:
        store = CatalogStore(conn)
        store.initialize_schema()
        athlete_id = store.resolve_athlete_id()
        days = (
            [start + timedelta(days=i) for i in range((end - start).days + 1)]
            if args.overwrite
            else missing_days(conn, athlete_id, start, end)
        )

    client = GarminHealthClient(*credentials)
    sync_weigh_ins(client, athlete_id, end - timedelta(days=args.weight_days - 1), end)

    if not days:
        print(f"Nada a sincronizar entre {start} e {end}.")
        return 0

    print(f"Sincronizando {len(days)} dia(s) entre {days[0]} e {days[-1]}...\n")

    saved = empty = 0

    for offset in range(0, len(days), args.batch):
        batch = days[offset : offset + args.batch]
        fetched: list[HealthDaily] = []

        for day in batch:
            daily = client.get_health_daily(day)
            if daily.is_empty:
                empty += 1
                print(f"  {day}  — sem dados")
            else:
                fetched.append(daily)
                print(
                    f"  {day}  HRV {daily.hrv_rmssd_ms or '—'} · "
                    f"FC rep {daily.resting_hr_bpm or '—'} · "
                    f"sono {daily.sleep_duration_h or '—'}h · "
                    f"bateria {daily.body_battery_max or '—'}"
                )
            if args.delay and day != batch[-1]:
                time.sleep(args.delay)

        if fetched:
            with duckdb.connect(DB_PATH) as conn:
                store = CatalogStore(conn)
                for daily in fetched:
                    persist(store, athlete_id, daily)
            saved += len(fetched)
            print(f"  → lote gravado ({saved}/{len(days)})\n")

    with duckdb.connect(DB_PATH) as conn:
        total = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM health_metrics "
            "WHERE athlete_id = ?",
            [athlete_id],
        ).fetchone()

    print(f"\nGravados: {saved} | sem dados: {empty}")
    print(f"health_metrics: {total[0]} dia(s), de {total[1]} a {total[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
