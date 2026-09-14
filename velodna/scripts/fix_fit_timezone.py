"""
Corrige o fuso das atividades importadas de arquivos `.fit`.

O protocolo FIT grava timestamps em UTC, mas o `fitparse` os devolve **naive**.
Ao gravar um datetime sem fuso numa coluna `TIMESTAMPTZ`, o DuckDB presume o
fuso local da máquina — e em São Paulo isso deslocou todo o acervo três horas
para a frente. A data continuava certa, só o horário ficava errado, então o erro
passou despercebido até o Strava trazer a mesma pedalada com o horário
verdadeiro: `2026-07-25T10:24:31Z` contra `2026-07-25 10:24:31-03:00` no banco.

A correção **não muda o horário de parede gravado** — muda o rótulo de fuso.
`10:24:31-03:00` vira `10:24:31+00:00`, ou seja, o instante volta 3 h e passa a
ser o real. Como o Brasil não tem horário de verão desde 2019 e o acervo começa
em 2023, o deslocamento é uniforme e não há casos de fronteira de DST.

O parser já foi corrigido (`ingestion.fit_parser._as_utc`), então importações
novas nascem certas. Este script existe só para o que já está gravado, e é
idempotente: só toca em linhas cujo offset ainda não é zero.

Uso:
    .venv/bin/python scripts/fix_fit_timezone.py --dry-run   # mostra o efeito
    .venv/bin/python scripts/fix_fit_timezone.py             # aplica
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/velodna.duckdb")

# Só as atividades vindas de arquivo. As do Strava já chegam em UTC correto.
AFFECTED_SOURCE = "fit"


def inspect(conn) -> dict:
    """Levanta o que seria alterado, sem tocar em nada."""
    total = conn.execute(
        "SELECT count(*) FROM activities WHERE source = ?", [AFFECTED_SOURCE]
    ).fetchone()[0]

    offsets = conn.execute(
        """
        SELECT DISTINCT CAST(date_part('timezone', started_at) AS INT) / 3600
        FROM activities WHERE source = ?
        """,
        [AFFECTED_SOURCE],
    ).fetchall()

    # O offset de -03:00 é NEGATIVO (-10800 s), então o instante corrigido é
    # `started_at + offset` — somar um número negativo volta 3 h. Subtrair
    # avançaria 3 h e listaria as atividades da noite em vez das da madrugada.
    date_changes = conn.execute(
        """
        SELECT id, started_at, sport_type, round(distance_m / 1000, 1)
        FROM activities
        WHERE source = ?
          AND CAST(started_at AS DATE) <> CAST(
              started_at + date_part('timezone', started_at) * INTERVAL 1 SECOND AS DATE
          )
        ORDER BY started_at
        """,
        [AFFECTED_SOURCE],
    ).fetchall()

    return {
        "total": total,
        "offsets": [o[0] for o in offsets],
        "date_changes": date_changes,
    }


def apply_fix(conn) -> int:
    """Reinterpreta o horário gravado como UTC, em vez de local.

    `strftime` extrai o horário de parede como texto e o `CAST ... AS TIMESTAMPTZ`
    com sufixo `+00` o reinterpreta em UTC. É uma reinterpretação do rótulo, não
    uma subtração cega — o que mantém a operação correta mesmo se algum dia o
    acervo incluir datas com horário de verão.

    Returns:
        Número de linhas atualizadas.
    """
    before = conn.execute(
        """
        SELECT count(*) FROM activities
        WHERE source = ? AND date_part('timezone', started_at) <> 0
        """,
        [AFFECTED_SOURCE],
    ).fetchone()[0]

    conn.execute(
        """
        UPDATE activities
        SET started_at = CAST(
            strftime(started_at, '%Y-%m-%d %H:%M:%S') || '+00' AS TIMESTAMPTZ
        )
        WHERE source = ? AND date_part('timezone', started_at) <> 0
        """,
        [AFFECTED_SOURCE],
    )
    return before


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Mostra o efeito sem gravar"
    )
    parser.add_argument(
        "--no-backup", action="store_true", help="Não copiar o banco antes"
    )
    args = parser.parse_args()

    with duckdb.connect(DB_PATH, read_only=True) as conn:
        report = inspect(conn)

    print(f"Atividades de origem '{AFFECTED_SOURCE}': {report['total']}")
    print(f"Offsets encontrados: {report['offsets']} h")

    if report["offsets"] == [0]:
        print("✓ Nada a fazer — o acervo já está em UTC.")
        return 0

    print(f"\nMudam de data: {len(report['date_changes'])}")
    for row in report["date_changes"]:
        print(f"  {row[1]}  {row[2]}  {row[3]} km")

    if args.dry_run:
        print("\n(dry-run — nada foi gravado)")
        return 0

    if not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{DB_PATH}.bak-{stamp}"
        shutil.copy2(DB_PATH, backup)
        print(f"\n✓ Backup: {backup}")

    with duckdb.connect(DB_PATH) as conn:
        updated = apply_fix(conn)

    print(f"✓ {updated} atividades reinterpretadas como UTC")
    print(
        "\nO PMC agrupa por data, e uma atividade pode ter mudado de dia. Rode:\n"
        "  .venv/bin/python scripts/recompute_metrics.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
