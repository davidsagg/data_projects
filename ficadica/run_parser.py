"""
Processa data/courses_raw.json e gera:
  data/courses.json   — catálogo normalizado
  data/courses.csv    — formato flat para análise
  data/catalog.md     — catálogo legível por humanos

Uso: python run_parser.py [--input PATH] [--output-dir DIR]
"""

import argparse
import json
from pathlib import Path
from rich.console import Console

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Parser do catálogo Fica a Dica Premium")
    parser.add_argument("--input", default="data/courses_raw.json", help="Arquivo JSON bruto")
    parser.add_argument("--output-dir", default="data", help="Diretório de saída")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        console.print(f"[red]Arquivo não encontrado: {input_path}[/red]")
        console.print("Execute primeiro: python run_scraper.py")
        raise SystemExit(1)

    console.print(f"[cyan]Carregando dados brutos de {input_path}...[/cyan]")
    with open(input_path, encoding="utf-8") as f:
        raw_data = json.load(f)
    console.print(f"  {len(raw_data)} cursos brutos carregados")

    # Parser
    from scraper.parser import CourseParser
    from scraper.exporter import DataExporter

    parser_obj = CourseParser()
    courses = parser_obj.parse_all_courses(raw_data)
    console.print(f"  {len(courses)} cursos normalizados\n")

    # Exportar
    exporter = DataExporter()
    exporter.to_json(courses, str(output_dir / "courses.json"))
    exporter.to_csv(courses, str(output_dir / "courses.csv"))
    exporter.to_markdown_catalog(courses, str(output_dir / "catalog.md"))

    console.print()
    exporter.summary_report(courses)


if __name__ == "__main__":
    main()
