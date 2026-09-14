"""
Cadastra o perfil do atleta e, opcionalmente, corta o histórico anterior a uma data.

O corte remove atividades, streams e curvas de potência de forma consistente.
Os arquivos `.fit` de origem não são tocados: reimportar é sempre possível via
`scripts/import_history.py`.

Uso:
    .venv/bin/python scripts/set_athlete_profile.py \\
        --ftp 217 --max-hr 186 --resting-hr 58 --weight 71 \\
        --name "David Saggioro" --drop-before 2023-01-01
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from storage.catalog_store import CatalogStore  # noqa: E402

DB_PATH = os.getenv("DB_PATH", "data/velodna.duckdb")


def update_profile(conn, athlete_id: str, args) -> None:
    """Grava os dados informados no cadastro do atleta.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.
        args: argumentos da linha de comando.
    """
    updates = {
        "name": args.name,
        "ftp_w": args.ftp,
        "max_hr_bpm": args.max_hr,
        "resting_hr_bpm": args.resting_hr,
        "threshold_hr_bpm": args.threshold_hr,
        "weight_kg": args.weight,
    }
    fields = {k: v for k, v in updates.items() if v is not None}
    if not fields:
        return

    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE athletes SET {assignments} WHERE id = ?",
        [*fields.values(), athlete_id],
    )
    for key, value in fields.items():
        print(f"  {key:18s} {value}")


def anchor_ftp(conn, athlete_id: str, ftp_w: float, effective: date) -> None:
    """Registra o FTP informado pelo atleta como ponto manual do histórico.

    Pontos manuais não são apagados pelo recálculo automático — só as
    estimativas (`source = 'estimated'`) são reconstruídas.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.
        ftp_w: FTP em watts.
        effective: data a partir da qual o valor vale.
    """
    conn.execute(
        """
        INSERT INTO ftp_history (id, athlete_id, effective_from, ftp_w, method, source)
        VALUES (?, ?, ?, ?, 'informado', 'manual')
        ON CONFLICT (athlete_id, effective_from) DO UPDATE SET
            ftp_w = EXCLUDED.ftp_w, method = 'informado', source = 'manual'
        """,
        [str(uuid.uuid4()), athlete_id, effective, ftp_w],
    )
    print(f"  FTP manual de {ftp_w:.0f} W válido a partir de {effective}")


def register_cp_test(
    conn,
    athlete_id: str,
    test_date: date,
    short_s: int,
    long_s: int,
) -> None:
    """Registra uma sessão de teste de potência crítica no histórico de FTP.

    Lê os melhores esforços das duas durações do protocolo naquela data e ajusta
    CP e W' pelo modelo de dois pontos. O resultado entra como `source = 'test'`,
    que o recálculo automático nunca sobrescreve.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.
        test_date: data da sessão de teste.
        short_s: duração do esforço curto, em segundos.
        long_s: duração do esforço longo, em segundos.
    """
    from analytics.critical_power import fit_two_point

    row = conn.execute(
        """
        SELECT MAX(CASE WHEN pc.duration_s = ? THEN pc.power_w END),
               MAX(CASE WHEN pc.duration_s = ? THEN pc.power_w END)
        FROM activities a
        JOIN power_curves pc ON pc.activity_id = a.id
        WHERE a.athlete_id = ? AND CAST(a.started_at AS DATE) = ?
        """,
        [short_s, long_s, athlete_id, test_date],
    ).fetchone()

    if not row or row[0] is None or row[1] is None:
        print(f"  {test_date}: sem esforços de {short_s}s e {long_s}s — ignorado")
        return

    fit = fit_two_point((short_s, float(row[0])), (long_s, float(row[1])))
    if fit is None:
        print(f"  {test_date}: ajuste inválido — ignorado")
        return

    conn.execute(
        """
        INSERT INTO ftp_history (
            id, athlete_id, effective_from, ftp_w, cp_w, w_prime_j, method, source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'test')
        ON CONFLICT (athlete_id, effective_from) DO UPDATE SET
            ftp_w = EXCLUDED.ftp_w, cp_w = EXCLUDED.cp_w,
            w_prime_j = EXCLUDED.w_prime_j, method = EXCLUDED.method,
            source = 'test'
        """,
        [
            str(uuid.uuid4()), athlete_id, test_date, fit.ftp_w,
            fit.cp_w, fit.w_prime_j, f"cp_{short_s}s_{long_s}s",
        ],
    )
    print(
        f"  {test_date}: CP {fit.cp_w:.1f} W · W' {fit.w_prime_kj:.2f} kJ "
        f"· FTP {fit.ftp_w:.1f} W  ({row[0]:.0f} W @ {short_s}s, "
        f"{row[1]:.0f} W @ {long_s}s)"
    )


def drop_before(conn, cutoff: date) -> None:
    """Remove atividades anteriores ao corte, com seus dados dependentes.

    Args:
        conn: conexão DuckDB.
        cutoff: primeira data a manter.
    """
    doomed = conn.execute(
        "SELECT COUNT(*) FROM activities WHERE CAST(started_at AS DATE) < ?", [cutoff]
    ).fetchone()[0]
    if not doomed:
        print("  nada a remover")
        return

    conn.execute(
        """
        DELETE FROM activity_streams WHERE activity_id IN (
            SELECT id FROM activities WHERE CAST(started_at AS DATE) < ?
        )
        """,
        [cutoff],
    )
    conn.execute(
        """
        DELETE FROM power_curves WHERE activity_id IN (
            SELECT id FROM activities WHERE CAST(started_at AS DATE) < ?
        )
        """,
        [cutoff],
    )
    conn.execute(
        "DELETE FROM activities WHERE CAST(started_at AS DATE) < ?", [cutoff]
    )
    conn.execute("DELETE FROM training_load WHERE date < ?", [cutoff])
    conn.execute("DELETE FROM ftp_history WHERE effective_from < ?", [cutoff])

    print(f"  {doomed} atividade(s) removida(s) antes de {cutoff}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name")
    parser.add_argument("--ftp", type=float, help="FTP atual em watts")
    parser.add_argument("--max-hr", type=int, help="FC máxima em bpm")
    parser.add_argument("--resting-hr", type=int, help="FC de repouso em bpm")
    parser.add_argument("--threshold-hr", type=int, help="FC de limiar em bpm")
    parser.add_argument("--weight", type=float, help="Peso em kg")
    parser.add_argument(
        "--drop-before",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Remove atividades anteriores a esta data (AAAA-MM-DD)",
    )
    parser.add_argument(
        "--ftp-effective",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="Data de validade do FTP informado (padrão: hoje)",
    )
    parser.add_argument(
        "--cp-test",
        action="append",
        default=[],
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Data de uma sessão de teste de CP (repetível)",
    )
    parser.add_argument(
        "--cp-short", type=int, default=60, help="Esforço curto do protocolo, em s"
    )
    parser.add_argument(
        "--cp-long", type=int, default=720, help="Esforço longo do protocolo, em s"
    )
    args = parser.parse_args()

    conn = duckdb.connect(DB_PATH)
    store = CatalogStore(conn)
    store.initialize_schema()
    athlete_id = store.resolve_athlete_id()

    print(f"Atleta: {athlete_id}\n")

    print("[perfil]")
    update_profile(conn, athlete_id, args)

    if args.ftp:
        anchor_ftp(conn, athlete_id, args.ftp, args.ftp_effective)

    if args.cp_test:
        print("\n[testes de potência crítica]")
        for test_date in sorted(args.cp_test):
            register_cp_test(
                conn, athlete_id, test_date, args.cp_short, args.cp_long
            )

    if args.drop_before:
        print("\n[corte de histórico]")
        drop_before(conn, args.drop_before)

    remaining = conn.execute(
        "SELECT COUNT(*), MIN(CAST(started_at AS DATE)), MAX(CAST(started_at AS DATE)) "
        "FROM activities"
    ).fetchone()
    print(f"\nAtividades no catálogo: {remaining[0]} ({remaining[1]} a {remaining[2]})")
    print("\nRode scripts/recompute_metrics.py para reprocessar as métricas.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
