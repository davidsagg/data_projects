"""
Sincroniza atividades do Strava para o catálogo VeloDNA.

Por padrão o script é **incremental**: descobre a atividade mais recente do
catálogo e pede ao Strava só o que veio depois dela. Rodar de novo logo em
seguida não faz nada — atividades já vinculadas são puladas.

O acervo já contém as mesmas pedaladas importadas dos arquivos `.fit`. Quando o
Strava devolve uma atividade que casa com uma existente (mesmo horário de
início, dentro de 5 minutos), o script apenas anota o `strava_id` no registro
local em vez de inserir uma cópia — os streams originais do Garmin são mais
ricos que os do Strava e ficam preservados.

Depois de sincronizar, rode `scripts/recompute_metrics.py` para calcular NP, IF,
TSS e o PMC das atividades novas.

Uso:
    # o que faltar desde a atividade mais recente do catálogo
    .venv/bin/python scripts/sync_strava.py

    # janela explícita
    .venv/bin/python scripts/sync_strava.py --start 2026-07-25 --end 2026-09-13

    # últimos 60 dias, sem buscar séries temporais (muito mais rápido)
    .venv/bin/python scripts/sync_strava.py --days 60 --no-streams

    # só conferir a credencial
    .venv/bin/python scripts/sync_strava.py --check
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from ingestion.strava_auth import StravaAuth, StravaAuthError  # noqa: E402
from ingestion.strava_client import StravaAPIError, StravaClient  # noqa: E402
from ingestion.strava_sync import StravaSync, SyncReport  # noqa: E402
from storage.catalog_store import CatalogStore  # noqa: E402

DB_PATH = os.getenv("DB_PATH", "data/velodna.duckdb")

# Atividades gravadas por transação. Cada lote abre e fecha a conexão: o DuckDB
# aceita um único escritor, e segurar o banco durante todo o backfill deixaria a
# API local fora do ar. Dez é o suficiente para amortizar o custo de abrir.
BATCH_SIZE = 10


class DatabaseBusyError(RuntimeError):
    """O banco está travado por outro processo — tipicamente a API local."""


def connect_or_explain(path: str):
    """Abre o catálogo, traduzindo o erro de lock em instrução acionável.

    Args:
        path: caminho do arquivo DuckDB.

    Returns:
        Conexão aberta.

    Raises:
        DatabaseBusyError: se outro processo detém o lock de escrita.
    """
    try:
        return duckdb.connect(path)
    except duckdb.IOException as error:
        if "lock" not in str(error).lower():
            raise
        raise DatabaseBusyError(
            f"O banco {path} está em uso por outro processo.\n"
            "  O DuckDB aceita um único escritor, e normalmente quem segura é a\n"
            "  API local. Pare-a, rode a sincronização e suba de novo:\n\n"
            "    lsof -ti:8006 | xargs kill\n"
            "    .venv/bin/python scripts/sync_strava.py\n"
            "    DB_PATH=data/velodna.duckdb .venv/bin/uvicorn api.main:app \\\n"
            "        --port 8006 --app-dir src --reload"
        ) from error


# Piso de escopo do catálogo. Por decisão do Dave, o VeloDNA guarda apenas de
# 2023 em diante — as 879 atividades de 2013–2021 foram removidas de propósito e
# seguem no banco legado. A conta do Strava, porém, tem histórico desde 2012, e um
# `--all` desavisado reinjeta tudo o que foi descartado. O piso é aplicado a
# qualquer janela resolvida; `--ignore-scope` existe para quem quiser mesmo o
# histórico completo.
CATALOG_START = datetime(2023, 1, 1, tzinfo=timezone.utc)


# Recuo aplicado à última atividade conhecida ao calcular o início incremental.
# Cobre o treino que estava sendo gravado quando a sincronização anterior rodou.
OVERLAP_DAYS = 2


def latest_activity_start(conn) -> datetime | None:
    """Descobre o início da atividade mais recente do catálogo.

    Returns:
        Instante de início, ou None se o catálogo estiver vazio.
    """
    found = conn.execute("SELECT max(started_at) FROM activities").fetchone()
    return found[0] if found and found[0] else None


def resolve_window(conn, args) -> tuple[datetime | None, datetime | None]:
    """Determina o intervalo a sincronizar a partir dos argumentos.

    Args:
        conn: conexão DuckDB.
        args: namespace do argparse.

    Returns:
        Par (after, before); `None` em qualquer ponta significa sem limite.
    """
    before = (
        datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        if args.end
        else None
    )

    if args.start:
        return datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc), before

    if args.days:
        return datetime.now(timezone.utc) - timedelta(days=args.days), before

    if args.all:
        return None, before

    latest = latest_activity_start(conn)
    if latest is None:
        return None, before

    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    return latest - timedelta(days=OVERLAP_DAYS), before


def apply_scope_floor(after: datetime | None, ignore: bool) -> datetime | None:
    """Impõe o piso de 2023 à janela, salvo pedido explícito do contrário.

    Args:
        after: início da janela resolvida, possivelmente None.
        ignore: True para dispensar o piso.

    Returns:
        O início efetivo da busca.
    """
    if ignore:
        return after
    if after is None:
        return CATALOG_START
    return max(after, CATALOG_START)


def check_credentials() -> int:
    """Valida a credencial do Strava sem tocar no banco."""
    try:
        athlete = StravaClient(auth=StravaAuth()).get_athlete()
    except (StravaAuthError, StravaAPIError) as error:
        print(f"✗ {error}", file=sys.stderr)
        return 1

    name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
    print(f"✓ Autenticado como {name or athlete.get('id')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--start", help="Data inicial (AAAA-MM-DD)")
    parser.add_argument("--end", help="Data final (AAAA-MM-DD)")
    parser.add_argument("--days", type=int, help="Janela retroativa em dias")
    parser.add_argument(
        "--all", action="store_true", help="Todo o histórico disponível no Strava"
    )
    parser.add_argument(
        "--limit", type=int, help="Máximo de atividades a processar nesta execução"
    )
    parser.add_argument(
        "--no-streams",
        action="store_true",
        help="Não buscar séries temporais (1 requisição por atividade a menos)",
    )
    parser.add_argument(
        "--ignore-scope",
        action="store_true",
        help=f"Buscar antes de {CATALOG_START:%Y-%m-%d} (o catálogo exclui esse período)",
    )
    parser.add_argument(
        "--check", action="store_true", help="Só validar a credencial e sair"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Listar o que seria importado, sem gravar nada",
    )
    args = parser.parse_args()

    if args.check:
        return check_credentials()

    try:
        client = StravaClient(auth=StravaAuth())
    except StravaAuthError as error:
        print(f"✗ {error}", file=sys.stderr)
        return 1

    # A janela e o atleta saem de uma conexão curta, fechada antes da rede.
    try:
        with connect_or_explain(DB_PATH) as conn:
            CatalogStore(conn).initialize_schema()
            after, before = resolve_window(conn, args)
            athlete_id = CatalogStore(conn).resolve_athlete_id()
    except DatabaseBusyError as error:
        print(f"✗ {error}", file=sys.stderr)
        return 1

    after = apply_scope_floor(after, args.ignore_scope)

    window = f"de {after:%Y-%m-%d}" if after else "todo o histórico"
    window += f" até {before:%Y-%m-%d}" if before else ""
    if not args.ignore_scope and after == CATALOG_START:
        window += f"  (piso do catálogo; use --ignore-scope para ir antes)"
    print(f"Sincronizando {window}…")

    if args.dry_run:
        return _dry_run(client, after, before, args.limit)

    # Busca primeiro, com o banco livre: a listagem é só rede.
    try:
        summaries = list(
            islice(client.iter_activities(after=after, before=before), args.limit)
            if args.limit
            else client.iter_activities(after=after, before=before)
        )
    except (StravaAuthError, StravaAPIError) as error:
        print(f"✗ {error}", file=sys.stderr)
        return 1

    if not summaries:
        print("Nada novo no Strava para este período.")
        return 0

    print(f"{len(summaries)} atividades no período. Gravando em lotes de {BATCH_SIZE}…")

    report = SyncReport()
    for start in range(0, len(summaries), BATCH_SIZE):
        batch = summaries[start : start + BATCH_SIZE]
        try:
            with connect_or_explain(DB_PATH) as conn:
                store = CatalogStore(conn)
                store.initialize_schema()
                StravaSync(client, store).sync_summaries(
                    batch,
                    with_streams=not args.no_streams,
                    athlete_id=athlete_id,
                    report=report,
                )
        except DatabaseBusyError as error:
            print(f"✗ {error}", file=sys.stderr)
            print(f"\n{report.summary()} (parcial — rode de novo para continuar)")
            return 1
        except (StravaAuthError, StravaAPIError) as error:
            print(f"✗ {error}", file=sys.stderr)
            print(f"\n{report.summary()} (parcial)")
            return 1

        print(f"  {min(start + BATCH_SIZE, len(summaries))}/{len(summaries)}", end="\r")

    print(" " * 30, end="\r")
    print(report.summary())
    for error in report.errors:
        print(f"  ! {error}", file=sys.stderr)

    if report.inserted or report.streams_added:
        print(
            "\nAtividades novas ainda estão sem NP/IF/TSS. Rode:\n"
            "  .venv/bin/python scripts/recompute_metrics.py"
        )
    return 0


def _dry_run(client, after, before, limit) -> int:
    """Lista as atividades do período sem gravar nada."""
    count = 0
    for summary in client.iter_activities(after=after, before=before):
        if limit is not None and count >= limit:
            break
        count += 1
        print(
            f"  {summary['start_date'][:10]}  {summary.get('sport_type', '?'):<16}"
            f"  {(summary.get('distance') or 0) / 1000:6.1f} km"
            f"  {summary.get('name', '')[:40]}"
        )
    print(f"\n{count} atividades no período (nada foi gravado).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
