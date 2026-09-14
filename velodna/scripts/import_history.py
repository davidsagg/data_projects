"""
VeloDNA — Importação em lote de arquivos FIT históricos.

O cálculo de TSS/NP não acontece aqui: é responsabilidade de
`scripts/recompute_metrics.py`, que roda sobre os streams já persistidos e usa
o FTP vigente na data de cada atividade.

Uso:
    # Importar todos os .fit de data/fit/ (padrão via .env)
    .venv/bin/python scripts/import_history.py

    # Importar um diretório específico
    .venv/bin/python scripts/import_history.py --dir /caminho/para/fits

    # Importar apenas um arquivo
    .venv/bin/python scripts/import_history.py --file tests/fixtures/sample.fit

    # Só recalcular o PMC (sem reimportar arquivos)
    .venv/bin/python scripts/import_history.py --pmc-only
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from analytics.pmc_calculator import PMCCalculator  # noqa: E402
from ingestion.fit_parser import FITParseError  # noqa: E402
from ingestion.pipeline import IngestionPipeline  # noqa: E402
from storage.catalog_store import CatalogStore  # noqa: E402

DB_PATH = os.getenv("DB_PATH", "data/velodna.duckdb")
FIT_DATA_DIR = os.getenv("FIT_DATA_DIR", "data/fit")


def _import_file(pipeline: IngestionPipeline, path: Path) -> str | None:
    """Importa um arquivo `.fit`, tolerando arquivos corrompidos.

    Args:
        pipeline: pipeline de ingestão já ligado ao catálogo.
        path: caminho do arquivo.

    Returns:
        UUID da atividade, ou None se o arquivo foi ignorado.
    """
    try:
        return pipeline.ingest_fit(path)
    except FITParseError as e:
        print(f"  ⚠  Ignorado ({e})")
        return None
    except Exception as e:  # arquivo corrompido não deve abortar o lote
        print(f"  ✗  Erro inesperado: {e}")
        return None


def _discover_fit_files(root: Path) -> list[Path]:
    """Encontra arquivos FIT sob um diretório, comprimidos ou não.

    A busca ignora maiúsculas: exports do TrainingPeaks vêm como `.FIT.gz`
    enquanto Wahoo e Zwift usam `.fit.gz`, e um glob sensível a caixa deixaria
    metade dos arquivos para trás sem avisar.

    Args:
        root: diretório varrido recursivamente.

    Returns:
        Caminhos ordenados dos arquivos encontrados.
    """
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.name.lower().endswith((".fit", ".fit.gz"))
    )


def run_import(fit_dir: Path | None, single_file: Path | None, pmc_only: bool) -> None:
    """Importa arquivos FIT e recalcula a série de carga de treino.

    Args:
        fit_dir: diretório varrido recursivamente por `.fit`.
        single_file: importa apenas este arquivo, quando informado.
        pmc_only: pula a importação e só recalcula o PMC.
    """
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(DB_PATH)
    store = CatalogStore(conn)
    store.initialize_schema()

    if not pmc_only:
        pipeline = IngestionPipeline(conn)
        imported = skipped = 0

        if single_file:
            files = [single_file]
        elif fit_dir and fit_dir.exists():
            files = _discover_fit_files(fit_dir)
        else:
            files = []
            print(f"Diretório não encontrado: {fit_dir}")

        if not files:
            print("Nenhum arquivo .fit encontrado.")
        else:
            print(f"Encontrado(s) {len(files)} arquivo(s) .fit — importando...\n")
            for f in files:
                print(f"  → {f.name}", end=" ")
                activity_id = _import_file(pipeline, f)
                if activity_id:
                    print(f"✓  ({activity_id[:8]}...)")
                    imported += 1
                else:
                    skipped += 1
            print(f"\nImportados: {imported}  |  Ignorados/erros: {skipped}")

    print("\nCalculando CTL/ATL/TSB...")
    PMCCalculator().run_and_store(store, date.today())

    activities = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    streams = conn.execute("SELECT COUNT(*) FROM activity_streams").fetchone()[0]
    load_days = conn.execute(
        "SELECT COUNT(*) FROM training_load WHERE ctl IS NOT NULL"
    ).fetchone()[0]
    no_tss = conn.execute(
        "SELECT COUNT(*) FROM activities WHERE tss IS NULL"
    ).fetchone()[0]

    print("\nBanco atual:")
    print(f"   activities       : {activities:,}")
    print(f"   activity_streams : {streams:,}")
    print(f"   training_load    : {load_days:,} dia(s) com CTL")

    if no_tss:
        print(
            f"\n{no_tss:,} atividade(s) sem TSS — "
            "rode scripts/recompute_metrics.py para calcular NP/IF/TSS."
        )

    conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Importa arquivos FIT para o VeloDNA")
    ap.add_argument("--dir", type=Path, default=None, help="Diretório com .fit")
    ap.add_argument("--file", type=Path, default=None, help="Arquivo .fit único")
    ap.add_argument("--pmc-only", action="store_true", help="Só recalcula o PMC")
    args = ap.parse_args()

    run_import(args.dir or Path(FIT_DATA_DIR), args.file, args.pmc_only)


if __name__ == "__main__":
    main()
