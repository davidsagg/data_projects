"""
VeloDNA — Importação em lote de arquivos FIT históricos.

Uso:
    # Importar todos os .fit de /data/fit/  (padrão via .env)
    .venv/bin/python scripts/import_history.py

    # Importar um diretório específico
    .venv/bin/python scripts/import_history.py --dir /caminho/para/fits

    # Importar apenas um arquivo
    .venv/bin/python scripts/import_history.py --file tests/fixtures/sample.fit

    # Só recalcular PMC (sem reimportar arquivos)
    .venv/bin/python scripts/import_history.py --pmc-only
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

# Garante que src/ está no path quando rodado da raiz do projeto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
from dotenv import load_dotenv

load_dotenv()

from src.ingestion.catalog_store import CatalogStore
from src.ingestion.fit_parser import FITParser, FITParseError
from src.analytics.pmc_calculator import PMCCalculator

DB_PATH      = os.getenv("DB_PATH",      "/workspace/data/velodna.duckdb")
FIT_DATA_DIR = os.getenv("FIT_DATA_DIR", "/data/fit")


def _import_file(parser: FITParser, store: CatalogStore, path: Path) -> str | None:
    """Parseia um .fit e persiste. Retorna activity_id ou None em caso de erro."""
    import uuid
    try:
        activity = parser.parse(path)
        activity_id = str(uuid.uuid4())
        store.upsert_activity(activity, activity_id)
        return activity_id
    except FITParseError as e:
        print(f"  ⚠  Ignorado ({e})")
        return None
    except Exception as e:
        print(f"  ✗  Erro inesperado: {e}")
        return None


def _compute_tss(conn: duckdb.DuckDBPyConnection, ftp: float = 200.0) -> int:
    """
    Calcula TSS para atividades que ainda não têm TSS definido.
    Fórmula: TSS = (duration_s / 3600) × (avg_power / FTP)² × 100
    Fallback quando não há potência: TSS = duration_h × 45 (estimativa moderada).
    """
    updated = conn.execute("""
        UPDATE activities
        SET tss = CASE
            WHEN avg_power_w IS NOT NULL AND avg_power_w > 0
                THEN ROUND((duration_s / 3600.0) * POWER(avg_power_w / ?, 2) * 100, 1)
            ELSE
                ROUND(duration_s / 3600.0 * 45, 1)
        END
        WHERE tss IS NULL AND duration_s IS NOT NULL
    """, [ftp]).rowcount
    return updated


def run_import(fit_dir: Path | None, single_file: Path | None, pmc_only: bool) -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(DB_PATH)
    store = CatalogStore(conn)
    store.initialize_schema()

    if not pmc_only:
        parser = FITParser()
        imported = skipped = 0

        files: list[Path] = []
        if single_file:
            files = [single_file]
        elif fit_dir and fit_dir.exists():
            files = sorted(fit_dir.glob("**/*.fit"))
        else:
            print(f"Diretório não encontrado: {fit_dir}")

        if not files:
            print("Nenhum arquivo .fit encontrado.")
        else:
            print(f"Encontrado(s) {len(files)} arquivo(s) .fit — iniciando importação...\n")
            for f in files:
                print(f"  → {f.name}", end=" ")
                aid = _import_file(parser, store, f)
                if aid:
                    print(f"✓  ({aid[:8]}...)")
                    imported += 1
                else:
                    skipped += 1

            print(f"\n✅ Importados: {imported}  |  Ignorados/erros: {skipped}")

    # Calcular TSS para atividades sem potência registrada
    ftp = float(os.getenv("FTP_W", "200"))
    n = _compute_tss(conn, ftp)
    if n:
        print(f"\nTSS estimado para {n} atividade(s) sem TSS (FTP={ftp}W assumido)")
        print("  → Ajuste FTP_W no .env para valores mais precisos.")

    # Recalcular PMC (CTL/ATL/TSB) para todas as atividades com TSS
    print("\nCalculando CTL/ATL/TSB...")
    PMCCalculator().run_and_store(store, date.today())

    count = conn.execute(
        "SELECT COUNT(*) FROM athlete_metrics WHERE ctl IS NOT NULL"
    ).fetchone()[0]
    print(f"✅ athlete_metrics atualizado: {count} dia(s) com CTL calculado")

    # Resumo do banco
    acts   = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    stream = conn.execute("SELECT COUNT(*) FROM activity_streams").fetchone()[0]
    print(f"\n📊 Banco atual:")
    print(f"   activities       : {acts}")
    print(f"   activity_streams : {stream:,}")
    print(f"   athlete_metrics  : {count}")
    print(f"\n🚀 Abra http://localhost:5173 para ver os dados.")

    conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Importa arquivos FIT para o VeloDNA")
    ap.add_argument("--dir",      type=Path, default=None, help="Diretório com .fit")
    ap.add_argument("--file",     type=Path, default=None, help="Arquivo .fit único")
    ap.add_argument("--pmc-only", action="store_true",     help="Só recalcula PMC")
    args = ap.parse_args()

    fit_dir = args.dir or Path(FIT_DATA_DIR)
    run_import(fit_dir, args.file, args.pmc_only)


if __name__ == "__main__":
    main()
