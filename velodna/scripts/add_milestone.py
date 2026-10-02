"""
Registra marcos que mudam a leitura do acervo: exames, planos, provas e achados.

Nada disso vem de sensor. Uma ergoespirometria que mostra o VO2max 10% abaixo
da linha de base, com o FTP estável, muda o que se espera das próximas semanas
— e não aparece em nenhum stream. O marco entra no Panorama e vira linha
vertical nos gráficos de carga e de FTP.

Os testes de potência crítica **não** precisam ser registrados aqui: eles já
estão no histórico de FTP (`set_athlete_profile.py --cp-test`) e o Panorama os
mostra como marco automaticamente.

Uso:
    # exame, com valores medidos (repetível)
    .venv/bin/python scripts/add_milestone.py --date 2026-02-12 --kind exame \\
        --title "Ergoespirometria" --measure vo2max_ml_kg_min=47.5 \\
        --measure fatmax_w=120 --source "Laboratório X" \\
        --summary "VO2max ~10% abaixo de 2023 com FTP estável."

    # início de um bloco
    .venv/bin/python scripts/add_milestone.py --date 2026-03-02 --kind plano \\
        --title "Reconstrução de VO2max — 12 semanas"

    .venv/bin/python scripts/add_milestone.py --list
    .venv/bin/python scripts/add_milestone.py --delete <id>

Tipos: exame, plano, prova, achado.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from storage.catalog_store import MILESTONE_KINDS, CatalogStore  # noqa: E402

DB_PATH = os.getenv("DB_PATH", "data/velodna.duckdb")


def parse_measure(raw: str) -> tuple[str, float]:
    """Lê `nome=valor`, aceitando vírgula decimal.

    Args:
        raw: texto passado em `--measure`.

    Returns:
        Par (nome, valor).
    """
    name, _, value = raw.partition("=")
    if not name or not value:
        raise argparse.ArgumentTypeError(f"Use nome=valor, recebi {raw!r}")
    return name.strip(), float(value.replace(",", "."))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    )
    parser.add_argument("--kind", choices=MILESTONE_KINDS)
    parser.add_argument("--title")
    parser.add_argument("--summary")
    parser.add_argument("--source")
    parser.add_argument(
        "--measure", action="append", default=[], type=parse_measure,
        help="Valor medido, nome=valor (repetível)",
    )
    parser.add_argument("--list", action="store_true", help="Lista os marcos")
    parser.add_argument("--delete", metavar="ID", help="Remove um marco")
    args = parser.parse_args()

    conn = duckdb.connect(DB_PATH)
    store = CatalogStore(conn)
    store.initialize_schema()
    athlete_id = store.resolve_athlete_id()

    try:
        if args.delete:
            store.delete_milestone(args.delete)
            print(f"Marco {args.delete} removido.")
            return 0

        if args.list:
            for m in store.get_milestones(athlete_id):
                values = " · ".join(f"{k}={v:g}" for k, v in m["measurements"].items())
                print(f"{m['date']}  {m['kind']:7s} {m['title']}  {values}")
                print(f"            id {m['id']}")
            return 0

        if not (args.date and args.kind and args.title):
            parser.error("--date, --kind e --title são obrigatórios para registrar")

        milestone_id = store.add_milestone(
            athlete_id,
            args.date,
            args.kind,
            args.title,
            args.summary,
            dict(args.measure) or None,
            args.source,
        )
        print(f"Marco registrado: {args.date} {args.kind} — {args.title} ({milestone_id})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
