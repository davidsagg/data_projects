"""
Recupera altitude e velocidade dos streams a partir dos arquivos `.fit`.

Dois defeitos se somaram e deixaram 192 atividades sem altitude:

1. O `fit_parser` lia os campos `altitude` e `speed`. Os dispositivos Garmin
   modernos gravam `enhanced_altitude` e `enhanced_speed` — campos de faixa
   maior — e **omitem** os clássicos. Corrigido em `_first_value`.
2. O erro foi invisível porque o resumo da atividade continuou mostrando a
   elevação certa: esse número vem da mensagem `session` do FIT, não dos
   records. Só apareceu quando a detecção de subidas devolveu zero subidas num
   pedal de 1.570 m.

Os `raw_file_path` gravados antes da migração para dev local apontam para
`/workspace/data/fit/...`, caminho do devcontainer que não existe mais. O script
remapeia pelo nome do arquivo em `data/fit/`.

Altitude não alimenta nenhuma métrica derivada (NP, TSS, curva de potência não
dependem dela), então **não é preciso recomputar** depois — só mapas, perfil de
elevação e análise de subidas passam a funcionar.

Uso:
    .venv/bin/python scripts/backfill_stream_channels.py --dry-run
    .venv/bin/python scripts/backfill_stream_channels.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from ingestion.fit_parser import FITParser  # noqa: E402

DB_PATH = os.getenv("DB_PATH", "data/velodna.duckdb")
FIT_DIR = Path(os.getenv("FIT_DATA_DIR", "data/fit"))

# Atividades por transação. O DuckDB aceita um escritor só; lotes curtos mantêm
# a janela de bloqueio pequena caso algo mais precise do banco.
BATCH_SIZE = 25


def resolve_fit_path(raw_path: str | None) -> Path | None:
    """Localiza o `.fit` da atividade, tolerando o caminho do devcontainer.

    Args:
        raw_path: caminho gravado em `activities.raw_file_path`.

    Returns:
        Caminho existente, ou None se o arquivo não for encontrado.
    """
    if not raw_path:
        return None

    candidate = Path(raw_path)
    if candidate.exists():
        return candidate

    local = FIT_DIR / candidate.name
    return local if local.exists() else None


def find_incomplete(conn) -> list[tuple[str, str]]:
    """Atividades que têm streams mas nenhum ponto com altitude."""
    return conn.execute(
        """
        SELECT a.id, a.raw_file_path
        FROM activities a
        WHERE a.source = 'fit'
          AND EXISTS (SELECT 1 FROM activity_streams s WHERE s.activity_id = a.id)
          AND NOT EXISTS (
                SELECT 1 FROM activity_streams s
                WHERE s.activity_id = a.id AND s.altitude_m IS NOT NULL
          )
        ORDER BY a.started_at
        """
    ).fetchall()


def backfill_one(conn, activity_id: str, fit_path: Path) -> int:
    """Reescreve altitude e velocidade dos streams de uma atividade.

    O casamento é por `time_s`, e não por posição na lista: streams e records
    podem divergir em contagem quando algum ponto foi descartado na ingestão, e
    parear por índice deslocaria a série inteira silenciosamente.

    Args:
        conn: conexão DuckDB aberta para escrita.
        activity_id: UUID da atividade.
        fit_path: arquivo `.fit` de origem.

    Returns:
        Número de pontos atualizados.
    """
    parsed = FITParser().parse(fit_path)
    start = parsed.start_time

    updates = []
    for point in parsed.streams:
        if point.altitude_m is None and point.speed_ms is None:
            continue
        time_s = int((point.timestamp - start).total_seconds())
        if time_s < 0:
            continue
        updates.append((point.altitude_m, point.speed_ms, activity_id, time_s))

    if not updates:
        return 0

    conn.executemany(
        """
        UPDATE activity_streams
        SET altitude_m = COALESCE(?, altitude_m),
            speed_ms   = COALESCE(?, speed_ms)
        WHERE activity_id = ? AND time_s = ?
        """,
        updates,
    )
    return len(updates)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="Só relata")
    args = parser.parse_args()

    with duckdb.connect(DB_PATH, read_only=True) as conn:
        pending = find_incomplete(conn)

    resolved = [(aid, resolve_fit_path(path)) for aid, path in pending]
    missing = [aid for aid, path in resolved if path is None]
    workable = [(aid, path) for aid, path in resolved if path is not None]

    print(f"{len(pending)} atividades sem altitude")
    print(f"  recuperáveis: {len(workable)}")
    if missing:
        print(f"  sem arquivo `.fit`: {len(missing)}")

    if args.dry_run or not workable:
        if args.dry_run:
            print("\n(dry-run — nada foi gravado)")
        return 0

    done = points = 0
    for start in range(0, len(workable), BATCH_SIZE):
        batch = workable[start : start + BATCH_SIZE]
        with duckdb.connect(DB_PATH) as conn:
            for activity_id, fit_path in batch:
                try:
                    points += backfill_one(conn, str(activity_id), fit_path)
                    done += 1
                except Exception as error:  # noqa: BLE001 — um arquivo ruim não derruba o lote
                    print(f"  ! {fit_path.name}: {error}", file=sys.stderr)
        print(f"  {min(start + BATCH_SIZE, len(workable))}/{len(workable)}", end="\r")

    print(" " * 30, end="\r")
    print(f"✓ {done} atividades · {points} pontos atualizados")
    print(
        "\nAltitude não alimenta métrica derivada — não é preciso recomputar.\n"
        "Mapas, perfil de elevação e análise de subidas passam a funcionar."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
