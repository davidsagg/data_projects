"""
Ponto de entrada principal do scraper.

Uso:
  python run_scraper.py                         # crawla todos os cursos
  python run_scraper.py --resume                # retoma de checkpoint
  python run_scraper.py --course nelsonfaria-escalas  # debug de um curso
  python run_scraper.py --no-headless           # abre janela (requer X server)
"""

import asyncio
import argparse
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def print_results(results: list[dict]):
    if not results:
        console.print("[yellow]Nenhum resultado.[/yellow]")
        return

    table = Table(title="Cursos Coletados", box=box.ROUNDED, show_lines=True)
    table.add_column("Slug", style="cyan", no_wrap=True)
    table.add_column("Título")
    table.add_column("Instrutor")
    table.add_column("Módulos", justify="right")
    table.add_column("Aulas", justify="right")
    table.add_column("Status")

    for c in results:
        if "error" in c:
            table.add_row(c["slug"], "", "", "", "", f"[red]ERRO: {c['error'][:40]}[/red]")
        else:
            table.add_row(
                c.get("slug", ""),
                c.get("title", ""),
                c.get("instructor", ""),
                str(len(c.get("modules", []))),
                str(c.get("total_lessons", 0)),
                "[green]OK[/green]",
            )

    console.print(table)


async def main():
    parser = argparse.ArgumentParser(description="Scraper do Fica a Dica Premium")
    parser.add_argument("--resume", action="store_true", help="Retoma de checkpoint existente")
    parser.add_argument("--course", metavar="SLUG", help="Scrapa apenas um curso (debug)")
    parser.add_argument("--no-headless", action="store_true", default=False, help="Abre janela visível do browser (requer X server)")
    args = parser.parse_args()

    from scraper.crawler import FicaAdicaCrawler

    crawler = FicaAdicaCrawler(headless=not args.no_headless)
    results = await crawler.scrape_all(resume=args.resume, single_course=args.course)

    print_results(results)

    # Salvar dados brutos — o parser normaliza depois para courses.json
    output_path = Path("data") / "courses_raw.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    console.print(f"\n[bold green]Dados brutos salvos em {output_path}[/bold green]")
    console.print("[cyan]Execute agora:[/cyan] python run_parser.py")


if __name__ == "__main__":
    asyncio.run(main())
