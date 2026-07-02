import sys
import requests
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

def check_env():
    from scraper.config import EMAIL, PASSWORD, BASE_URL, APP_URL, OUTPUT_DIR, validate
    from pathlib import Path

    table = Table(title="Status do Ambiente", box=box.ROUNDED, show_header=True)
    table.add_column("Verificação", style="bold")
    table.add_column("Status")
    table.add_column("Detalhe")

    # Credenciais
    try:
        validate()
        table.add_row("Credenciais .env", "[green]OK[/green]", f"Email configurado: {EMAIL[:4]}***")
    except ValueError as e:
        table.add_row("Credenciais .env", "[red]ERRO[/red]", str(e))
        console.print(table)
        sys.exit(1)

    # Diretórios
    dirs_ok = Path(OUTPUT_DIR).exists() and Path(OUTPUT_DIR, "raw").exists()
    if dirs_ok:
        table.add_row("Diretórios data/", "[green]OK[/green]", f"{OUTPUT_DIR} e {OUTPUT_DIR}/raw criados")
    else:
        table.add_row("Diretórios data/", "[red]ERRO[/red]", "Diretórios não encontrados")

    # Conectividade BASE_URL
    try:
        r = requests.get(BASE_URL, timeout=10)
        table.add_row(
            "Conectividade site",
            "[green]OK[/green]",
            f"HTTP {r.status_code} — {BASE_URL}"
        )
    except requests.exceptions.ConnectionError:
        table.add_row("Conectividade site", "[red]ERRO[/red]", "Sem conexão com o site")
    except requests.exceptions.Timeout:
        table.add_row("Conectividade site", "[yellow]TIMEOUT[/yellow]", "Site demorou a responder")

    # Playwright disponível
    try:
        from playwright.sync_api import sync_playwright
        table.add_row("Playwright", "[green]OK[/green]", "Importado com sucesso")
    except ImportError:
        table.add_row("Playwright", "[red]ERRO[/red]", "Execute: pip install playwright && playwright install chromium")

    console.print(table)

if __name__ == "__main__":
    check_env()
