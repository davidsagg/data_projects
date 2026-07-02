"""Weekly pipeline orchestrator + APScheduler trigger.

Run directly:
    python -m crypto_advisor

Or import and start programmatically:
    from crypto_advisor.scheduler import start
    start()
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def run_weekly_analysis() -> None:
    """Full weekly pipeline: collect → analyse → report → notify."""
    from .advisor import CryptoAdvisor
    from .data.coingecko import CoinGeckoClient
    from .data.mercado_bitcoin import MercadoBitcoinClient
    from .db.schema import init_db
    from .db.repository import PortfolioRepository, TradeRepository, RecommendationRepository
    from .indicators.technical import TechnicalIndicators
    from .models import AdvisorContext
    from .notification.telegram import TelegramNotifier
    from .reporting.report import ReportBuilder, ReportData
    from .tax.optimizer import TaxOptimizer

    week_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc)

    logger.info("▶ Weekly analysis started — %s", week_date)

    # ── DB setup ──────────────────────────────────────────────────────────────
    db_path = os.getenv("DB_PATH", "./data/crypto_advisor.db")
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row

    portfolio_repo = PortfolioRepository(conn)
    trade_repo = TradeRepository(conn)
    rec_repo = RecommendationRepository(conn)

    # ── Exchange: portfolio + trades ──────────────────────────────────────────
    mb_client = MercadoBitcoinClient(
        api_id=os.environ["MB_API_ID"],
        api_secret=os.environ["MB_API_SECRET"],
        tapi_id=os.getenv("MB_TAPI_ID"),
        tapi_secret=os.getenv("MB_TAPI_SECRET"),
    )
    try:
        portfolio = mb_client.get_portfolio()
        portfolio_repo.upsert_bulk(portfolio)
        logger.info("  Portfolio synced: %d positions", len(portfolio))

        since = trade_repo.get_latest_traded_at()
        new_trades = mb_client.get_trade_history(since_date=since)
        for trade in new_trades:
            trade_repo.add(trade)
        logger.info("  Trades imported: %d new", len(new_trades))
    except Exception as exc:
        logger.warning("  MB API error: %s — using cached portfolio", exc)
        portfolio = portfolio_repo.get_all()

    # ── Tax optimizer ─────────────────────────────────────────────────────────
    tax = TaxOptimizer(conn)
    tax.sync_from_trades(now.year, now.month)

    # ── Market data + dynamic asset selection ─────────────────────────────────
    cg = CoinGeckoClient(api_key=os.getenv("COINGECKO_API_KEY") or None)
    from .data.asset_selector import AssetSelector, SelectedAsset
    selector = AssetSelector(cg)
    held_symbols = {p.symbol for p in portfolio if p.symbol != "BRL"}

    # top_n=20 → AssetSelector calls get_top_markets(limit=30) internally.
    # We reuse that same cache entry (limit=30) to avoid a second API call.
    TOP_N = 20
    _CG_LIMIT = TOP_N + 10  # must match AssetSelector's internal limit

    try:
        selected = selector.select_weekly_assets(
            portfolio_symbols=held_symbols, top_n=TOP_N, max_dynamic=7
        )
        # Reuse cache — same limit used inside select_weekly_assets
        top_markets = cg.get_top_markets(limit=_CG_LIMIT)
    except Exception as exc:
        logger.warning("  CoinGecko markets falhou: %s — usando âncoras como fallback", exc)
        selected = [
            SelectedAsset(sym, i + 1, 0.0, 0.0, 0.0, True, True, sym in held_symbols)
            for i, sym in enumerate(["BTC", "ETH", "SOL"])
        ]
        top_markets = []

    try:
        fear_greed = cg.get_fear_greed()
    except Exception as exc:
        logger.warning("  Fear & Greed indisponível: %s", exc)
        fear_greed = None

    # Prices in BRL for tax context
    current_prices_brl: dict[str, float] = {m.symbol: m.price_brl for m in top_markets}

    tax_ctx = tax.build_tax_context(now.year, now.month, current_prices_brl)

    symbols_to_analyse = [a.symbol for a in selected]

    market_data = {m.symbol: m for m in top_markets if m.symbol in symbols_to_analyse}

    # ── Technical indicators: Binance primary, CoinGecko fallback ────────────
    import time as _time
    from .data.binance import BinanceClient
    _ssl = os.getenv("BINANCE_VERIFY_SSL", "true").lower() != "false"
    binance = BinanceClient(verify_ssl=_ssl)

    # Probe Binance once — avoids N failed requests when geo-blocked
    _binance_available = True
    try:
        binance.get_ohlcv("BTC", "4h")
        logger.info("  Binance disponível — usando como fonte OHLCV primária")
    except Exception as exc:
        _binance_available = False
        logger.warning("  Binance indisponível (%s) — CoinGecko será fonte OHLCV primária", exc.__class__.__name__)

    def _get_ohlcv(sym: str, tf: str) -> "pd.DataFrame | None":
        if _binance_available:
            try:
                return binance.get_ohlcv(sym, tf)
            except Exception as exc:
                logger.warning("  Binance falhou para %s %s (%s) — usando CoinGecko", sym, tf, exc)
        try:
            return cg.get_ohlcv(sym, tf)
        except Exception as cg_exc:
            logger.warning("  CoinGecko falhou para %s %s: %s", sym, tf, cg_exc)
            return None

    tech_4h: dict = {}
    tech_1d: dict = {}
    for sym in symbols_to_analyse:
        try:
            df_4h = _get_ohlcv(sym, "4h")
            df_1d = _get_ohlcv(sym, "1d")
            if df_4h is None or df_1d is None:
                logger.warning("  %s sem OHLCV disponível — pulando indicadores", sym)
                continue
            tech_4h[sym] = TechnicalIndicators.calculate(df_4h, "4h", symbol=sym)
            tech_1d[sym] = TechnicalIndicators.calculate(df_1d, "1d", symbol=sym)
            logger.info("  Indicators OK: %s  MM9=%.0f  RSI=%.1f (%s)",
                        sym,
                        tech_4h[sym].sma_9 or 0,
                        tech_4h[sym].rsi_14 or 0,
                        tech_4h[sym].rsi_zone)
            if not _binance_available:
                _time.sleep(2)  # extra cooldown between symbols when using CoinGecko free tier
        except KeyError:
            logger.warning("  %s sem par conhecido — pulando indicadores", sym)
        except Exception as exc:
            logger.warning("  Indicators falhou para %s: %s", sym, exc)

    # ── Claude analysis ───────────────────────────────────────────────────────
    advisor = CryptoAdvisor()
    ctx = AdvisorContext(
        portfolio=portfolio,
        market_data=market_data,
        technical_4h=tech_4h,
        technical_1d=tech_1d,
        fear_greed=fear_greed,
        tax_context=tax_ctx,
        top_markets=top_markets,
        week_date=week_date,
    )
    weekly_report = advisor.generate_weekly_recommendations(ctx)
    logger.info("  Recommendations generated: %d", len(weekly_report.recommendations))

    # ── Persist recommendations ───────────────────────────────────────────────
    for rec in weekly_report.recommendations:
        rec_repo.save_from_output(week_date, rec)

    # ── Build & save HTML report ──────────────────────────────────────────────
    # USD/BRL rate derived from BTC (most liquid, most accurate ratio)
    btc_data = next((m for m in top_markets if m.symbol == "BTC"), None)
    usd_brl_rate = (btc_data.price_brl / btc_data.price_usd) if btc_data and btc_data.price_usd else 5.8

    # Prices in BRL for portfolio valuation (BRL fiat = 1:1)
    prices_brl = {m.symbol: m.price_brl for m in top_markets}
    prices_brl.setdefault("BRL", 1.0)

    portfolio_total = sum(
        p.quantity * prices_brl.get(p.symbol, 0.0)
        for p in portfolio
    )
    portfolio_cost = sum(
        p.quantity * p.avg_price_brl
        for p in portfolio
        if p.symbol != "BRL" and p.avg_price_brl > 0
    )
    portfolio_pnl = (portfolio_total - portfolio_cost) if portfolio_cost > 0 else 0.0

    report_data = ReportData(
        week_date=week_date,
        portfolio=portfolio,
        portfolio_total_brl=portfolio_total,
        portfolio_pnl_brl=portfolio_pnl,
        recommendations=weekly_report.recommendations,
        market_summary=weekly_report.market_summary,
        fear_greed=fear_greed,
        tax_context=tax_ctx,
        top_markets=top_markets,
        usd_brl_rate=usd_brl_rate,
        current_prices_brl=prices_brl,
    )

    builder = ReportBuilder()
    html = builder.build_html(report_data)
    report_path = builder.save(html, week_date)
    logger.info("  Report saved: %s", report_path)

    # ── Telegram delivery ─────────────────────────────────────────────────────
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        summary = builder.build_telegram_summary(report_data)
        notifier = TelegramNotifier(token=token, chat_id=chat_id)
        notifier.send_weekly_report_sync(summary)
        notifier.send_report_file_sync(report_path, week_date)
        logger.info("  Telegram report sent")
    else:
        logger.warning("  Telegram not configured — skipping delivery")

    conn.close()
    cg.close()
    logger.info("✓ Weekly analysis complete")


# ─── APScheduler ─────────────────────────────────────────────────────────────

def start() -> None:
    """Start the APScheduler for the weekly Sunday 18h run."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error(
            "APScheduler not installed. Run: pip install apscheduler>=3.10.0"
        )
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        run_weekly_analysis,
        trigger=CronTrigger(
            day_of_week=os.getenv("REPORT_SCHEDULE_DAY", "sun"),
            hour=int(os.getenv("REPORT_SCHEDULE_HOUR", "18")),
            minute=int(os.getenv("REPORT_SCHEDULE_MINUTE", "0")),
        ),
        id="weekly_analysis",
        name="Weekly crypto analysis",
        misfire_grace_time=3600,
        coalesce=True,
    )

    logger.info(
        "Scheduler started — weekly analysis every %s at %s:%s (America/Sao_Paulo)",
        os.getenv("REPORT_SCHEDULE_DAY", "sunday"),
        os.getenv("REPORT_SCHEDULE_HOUR", "18"),
        os.getenv("REPORT_SCHEDULE_MINUTE", "00"),
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
