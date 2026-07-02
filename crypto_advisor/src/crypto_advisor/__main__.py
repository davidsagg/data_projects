"""Entry point: python -m crypto_advisor

Modes
-----
(no args)                       Start the APScheduler — blocks waiting for Sunday 18h
--run-now                       Execute the full weekly analysis immediately (ignores schedule)
--smoke-test                    Check connectivity against all configured APIs
--status                        Show portfolio, tax status and next scheduled run
--set-cost-basis SYMBOL PRICE   Set manually the avg purchase price in BRL for a position
--dashboard                     Start the FastAPI web dashboard (default: http://0.0.0.0:8080)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="crypto_advisor",
        description="CryptoAdvisor — AI swing trading advisor for Mercado Bitcoin",
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--run-now",
        action="store_true",
        help="Run the full weekly analysis immediately (bypasses schedule).",
    )
    group.add_argument(
        "--smoke-test",
        action="store_true",
        help="Validate connectivity against all configured APIs and exit.",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Print portfolio, current tax status and next scheduled run.",
    )
    group.add_argument(
        "--set-cost-basis",
        nargs=2,
        metavar=("SYMBOL", "PRICE_BRL"),
        help="Set the average purchase price in BRL for a portfolio position. "
             "Example: --set-cost-basis BTC 380000",
    )
    group.add_argument(
        "--dashboard",
        action="store_true",
        help="Start the FastAPI web dashboard.",
    )
    p.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Dashboard port (default: 8765). Only used with --dashboard.",
    )
    p.add_argument(
        "--host",
        default="0.0.0.0",
        help="Dashboard host (default: 0.0.0.0). Only used with --dashboard.",
    )
    p.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for the dashboard (dev mode). Only used with --dashboard.",
    )
    return p.parse_args()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _run_smoke_test() -> None:
    smoke = Path(__file__).parent.parent.parent / "scripts" / "smoke_test.py"
    if smoke.exists():
        import runpy
        runpy.run_path(str(smoke), run_name="__main__")
    else:
        print("scripts/smoke_test.py not found — run from the project root.")
        sys.exit(1)


def _print_status() -> None:
    import os
    import sqlite3
    from datetime import datetime, timezone

    from dotenv import load_dotenv
    load_dotenv()

    from rich.console import Console
    from rich.table import Table
    from rich import box

    from .db.schema import init_db
    from .db.repository import PortfolioRepository, PerformanceRepository
    from .tax.optimizer import TaxOptimizer

    console = Console()
    db_path = os.getenv("DB_PATH", "./data/crypto_advisor.db")

    try:
        conn = init_db(db_path)
        conn.row_factory = sqlite3.Row
    except Exception as exc:
        console.print(f"[red]DB error:[/red] {exc}")
        return

    now = datetime.now(timezone.utc)

    # ── Portfolio ─────────────────────────────────────────────────────────────
    portfolio = PortfolioRepository(conn).get_all()
    if portfolio:
        t = Table(title="💼 Portfólio", box=box.SIMPLE_HEAVY)
        t.add_column("Ativo", style="bold cyan")
        t.add_column("Qtd", justify="right")
        t.add_column("Preço médio BRL", justify="right")
        for pos in portfolio:
            if pos.symbol != "BRL":
                t.add_row(pos.symbol, f"{pos.quantity:.8f}",
                          f"R$ {pos.avg_price_brl:,.2f}")
        console.print(t)
    else:
        console.print("[dim]Portfólio vazio — sincronize com a exchange.[/dim]")

    # ── Tax status ────────────────────────────────────────────────────────────
    tax = TaxOptimizer(conn)
    status = tax.get_monthly_status(now.year, now.month)
    zone_color = {"safe": "green", "warning": "yellow",
                  "critical": "dark_orange", "blocked": "red"}.get(status.zone, "white")
    pct = status.total_sold_brl / status.limit_brl * 100
    console.print(
        f"\n🧾 [bold]Tax {now.strftime('%b/%Y')}:[/bold] "
        f"R$ {status.total_sold_brl:,.0f} / R$ {status.limit_brl:,.0f} "
        f"({pct:.0f}%)  [{zone_color}]{status.zone.upper()}[/{zone_color}]"
    )

    # ── Performance ───────────────────────────────────────────────────────────
    perf = PerformanceRepository(conn).get_summary()
    if perf.total_trades:
        console.print(
            f"📈 [bold]Performance:[/bold] "
            f"Win rate {perf.win_rate_pct:.1f}%  |  "
            f"R-múltiplo médio {perf.avg_r_multiple:.2f}x  |  "
            f"P&L total R$ {perf.total_pnl_brl:,.2f}  |  "
            f"{perf.open_trades} trade(s) aberto(s)"
        )

    # ── Next run ──────────────────────────────────────────────────────────────
    console.print(
        "\n⏰ [bold]Próximo relatório:[/bold] domingo às 18h00 (America/Sao_Paulo)"
    )
    conn.close()


def _set_cost_basis(symbol: str, price_brl: float) -> None:
    import os, sqlite3
    from dotenv import load_dotenv
    load_dotenv()
    from .db.schema import init_db
    from .db.repository import PortfolioRepository

    db_path = os.getenv("DB_PATH", "./data/crypto_advisor.db")
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    repo = PortfolioRepository(conn)

    symbol = symbol.upper()
    found = repo.set_avg_price(symbol, price_brl)
    conn.close()

    if found:
        print(f"✅  Preço médio de {symbol} atualizado para R$ {price_brl:,.2f}")
        print(f"    O P&L será calculado corretamente no próximo relatório.")
    else:
        print(f"⚠️  {symbol} não encontrado no portfólio.")
        print(f"    Rode --run-now ou --status primeiro para sincronizar as posições.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    _configure_logging()

    if args.smoke_test:
        _run_smoke_test()
        return

    if args.status:
        _print_status()
        return

    if args.set_cost_basis:
        symbol, price_str = args.set_cost_basis
        try:
            price_brl = float(price_str.replace(",", "."))
        except ValueError:
            print(f"❌  Preço inválido: '{price_str}'. Use apenas números. Ex: 380000 ou 380000.50")
            sys.exit(1)
        _set_cost_basis(symbol, price_brl)
        return

    if args.run_now:
        from .scheduler import run_weekly_analysis
        logging.getLogger().info("Executando análise semanal agora...")
        run_weekly_analysis()
        return

    if args.dashboard:
        from .dashboard.app import run as run_dashboard
        print(f"🪙  CryptoAdvisor Dashboard → http://{args.host}:{args.port}")
        run_dashboard(host=args.host, port=args.port, reload=args.reload)
        return

    # Default: start blocking scheduler
    from .scheduler import start
    start()


if __name__ == "__main__":
    main()
