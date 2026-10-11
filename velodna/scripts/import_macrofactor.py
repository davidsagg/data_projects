"""
Importa o export do MacroFactor: alimentação, gasto, tendência e pesagens.

O MacroFactor não tem API. No app: More → Data Management → Data Export →
"All time" (ou só o período novo) → salvar o `.xlsx` em `docs/dados-saude/`,
que fica fora do git. Depois:

    .venv/bin/python scripts/import_macrofactor.py            # o export mais novo
    .venv/bin/python scripts/import_macrofactor.py caminho/para/export.xlsx
    .venv/bin/python scripts/import_macrofactor.py --dry-run  # lê e resume

Idempotente: reimportar o mesmo arquivo, ou um mais novo que cubra o mesmo
período, atualiza os dias em vez de duplicar. As pesagens entram em
`health_metrics` só onde o Garmin não registrou peso.

Como os outros scripts de escrita, exige o banco livre — pare a API antes
(`make stop`).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb
from dotenv import load_dotenv

load_dotenv()

from ingestion.macrofactor import (
    MacroFactorExport,
    import_export,
    parse_export,
)
from storage.catalog_store import CatalogStore

DB_PATH = os.getenv("DB_PATH", "data/velodna.duckdb")
EXPORT_DIR = Path("docs/dados-saude")


def latest_export(folder: Path = EXPORT_DIR) -> Path | None:
    """O export mais recente da pasta — o nome traz a data e a hora."""
    exports = sorted(folder.glob("MacroFactor-*.xlsx"))
    return exports[-1] if exports else None


def summarize(export: MacroFactorExport) -> str:
    """Resumo de uma linha por assunto, para conferir antes de gravar."""
    logged = [d for d in export.days if d.calories_kcal is not None]
    lines = []
    if export.days:
        lines.append(
            f"Dias: {len(export.days)}, de {export.days[0].date} a "
            f"{export.days[-1].date} · com comida registrada: {len(logged)}"
        )
    if logged:
        lines.append(f"Último dia registrado: {logged[-1].date}")
    if export.weigh_ins:
        last = export.weigh_ins[-1]
        lines.append(
            f"Pesagens: {len(export.weigh_ins)} · última {last.weight_kg:.1f} kg "
            f"em {last.date}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("path", nargs="?", type=Path, help="export .xlsx")
    parser.add_argument("--dry-run", action="store_true", help="lê sem gravar")
    args = parser.parse_args()

    path = args.path or latest_export()
    if not path or not path.exists():
        sys.exit(f"Nenhum export encontrado em {EXPORT_DIR}/MacroFactor-*.xlsx")

    print(f"Lendo {path.name}…")
    export = parse_export(path)
    print(summarize(export))
    if args.dry_run:
        return

    conn = duckdb.connect(DB_PATH)
    try:
        store = CatalogStore(conn)
        store.initialize_schema()
        result = import_export(store, store.resolve_athlete_id(), export)
    finally:
        conn.close()
    print(
        f"Gravados: {result['days']} dia(s) · "
        f"{result['weigh_ins']} pesagem(ns) nova(s) em health_metrics"
    )


if __name__ == "__main__":
    main()
