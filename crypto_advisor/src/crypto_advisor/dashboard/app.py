"""FastAPI + HTMX dashboard for CryptoAdvisor."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape

load_dotenv()

# ─── App & templates ─────────────────────────────────────────────────────────

app = FastAPI(title="CryptoAdvisor Dashboard", docs_url=None, redoc_url=None)

_HERE = Path(__file__).parent
# cache_size=0 avoids TypeError: unhashable type: 'dict' in Jinja2 3.1.3+ LRU cache
_jinja_env = Environment(
    loader=FileSystemLoader(str(_HERE / "templates")),
    autoescape=select_autoescape(["html"]),
    cache_size=0,
)
templates = Jinja2Templates(env=_jinja_env)


# ─── Jinja2 filters ──────────────────────────────────────────────────────────

def _fmt_brl(value: float | None) -> str:
    if value is None:
        return "—"
    try:
        formatted = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        sign = "-" if value < 0 else ""
        return f"{sign}R$ {formatted}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    try:
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_qty(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) < 0.001:
        return f"{value:.8f}"
    if abs(value) < 1:
        return f"{value:.6f}"
    return f"{value:,.4f}"


_jinja_env.filters["brl"] = _fmt_brl
_jinja_env.filters["pct"] = _fmt_pct
_jinja_env.filters["qty"] = _fmt_qty


# ─── Price cache (120s TTL) ───────────────────────────────────────────────────

_price_cache: dict[str, Any] = {
    "prices_brl": {},
    "fear_greed": None,
    "usd_brl_rate": 5.8,
    "fetched_at": 0.0,
}
_CACHE_TTL = 120

_btc_history_cache: dict[str, Any] = {
    "dates": [],       # ["YYYY-MM-DD", ...]
    "prices_usd": [],  # [float USD closes from Binance, ...]
    "fetched_at": 0.0,
}
_BTC_HISTORY_TTL = 1800  # 30 min — daily candles don't change fast


def _refresh_prices() -> None:
    try:
        from crypto_advisor.data.coingecko import CoinGeckoClient
        cg = CoinGeckoClient(api_key=os.getenv("COINGECKO_API_KEY") or None)
        markets = cg.get_top_markets(limit=30)
        fg = cg.get_fear_greed()
        cg._http.close()
        _price_cache["prices_brl"] = {m.symbol: m.price_brl for m in markets}
        _price_cache["fear_greed"] = fg
        _price_cache["fetched_at"] = time.time()
        btc = next((m for m in markets if m.symbol == "BTC"), None)
        if btc and btc.price_usd:
            _price_cache["usd_brl_rate"] = btc.price_brl / btc.price_usd
    except Exception:
        pass


def _refresh_btc_history() -> None:
    """Fetch 30 daily BTC closes from Binance (reliable, no rate-limit issues)."""
    try:
        from crypto_advisor.data.binance import BinanceClient
        b = BinanceClient()
        df = b.get_ohlcv("BTC", "1d")
        b._http.close()
        df_30 = df.tail(30)
        _btc_history_cache["dates"] = [ts.strftime("%Y-%m-%d") for ts in df_30.index]
        _btc_history_cache["prices_usd"] = [float(p) for p in df_30["close"]]
        _btc_history_cache["fetched_at"] = time.time()
    except Exception:
        pass


def _ensure_fresh_prices() -> None:
    if time.time() - _price_cache["fetched_at"] > _CACHE_TTL:
        if _price_cache["fetched_at"] == 0.0:
            _refresh_prices()  # synchronous on first load so page has live data
        else:
            threading.Thread(target=_refresh_prices, daemon=True).start()


def _ensure_fresh_btc_history() -> None:
    if time.time() - _btc_history_cache["fetched_at"] > _BTC_HISTORY_TTL:
        if _btc_history_cache["fetched_at"] == 0.0:
            _refresh_btc_history()  # synchronous on first load
        else:
            threading.Thread(target=_refresh_btc_history, daemon=True).start()


# ─── DB ──────────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    from crypto_advisor.db.schema import init_db
    db_path = os.getenv("DB_PATH", "./data/crypto_advisor.db")
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _save_snapshot(conn: sqlite3.Connection, total_value: float, total_cost: float) -> None:
    """Save portfolio value snapshot at most once per hour."""
    row = conn.execute(
        "SELECT captured_at FROM portfolio_snapshots ORDER BY captured_at DESC LIMIT 1"
    ).fetchone()
    if row:
        try:
            last = datetime.fromisoformat(row["captured_at"].replace(" ", "T"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - last).total_seconds() < 3600:
                return
        except Exception:
            pass
    conn.execute(
        "INSERT INTO portfolio_snapshots (total_value_brl, total_cost_brl) VALUES (?, ?)",
        (round(total_value, 2), round(total_cost, 2)),
    )
    conn.commit()


# ─── Analysis background runner ───────────────────────────────────────────────

_analysis_lock = threading.Lock()
_analysis_state: dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "error": None,
}


def _run_analysis_thread() -> None:
    from crypto_advisor.scheduler import run_weekly_analysis
    with _analysis_lock:
        _analysis_state.update({
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "error": None,
        })
    try:
        run_weekly_analysis()
        _price_cache["fetched_at"] = 0.0  # force price refresh after analysis
        with _analysis_lock:
            _analysis_state.update({
                "status": "done",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as exc:
        with _analysis_lock:
            _analysis_state.update({
                "status": "error",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            })


def _analysis_widget() -> str:
    with _analysis_lock:
        state = dict(_analysis_state)
    status = state["status"]

    btn_classes = (
        "px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium "
        "rounded-lg transition-colors flex items-center gap-2 cursor-pointer"
    )
    hx_attrs = 'hx-post="/api/run-analysis" hx-target="#analysis-widget" hx-swap="outerHTML"'

    if status == "running":
        return (
            '<div id="analysis-widget" class="flex items-center gap-2 px-4 py-2 rounded-lg '
            'bg-blue-500/10 border border-blue-500/30 text-blue-300 text-sm" '
            'hx-get="/api/analysis-widget" hx-trigger="every 5s" hx-swap="outerHTML">'
            '<svg class="animate-spin h-4 w-4 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" '
            'fill="none" viewBox="0 0 24 24">'
            '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>'
            '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>'
            '</svg>'
            'Analisando com Claude Sonnet...'
            '</div>'
        )

    if status == "done":
        finished = (state.get("finished_at") or "")[:16].replace("T", " ")
        return (
            f'<div id="analysis-widget" class="flex flex-col gap-2">'
            f'<span class="text-green-400 text-xs">✓ Concluída às {finished}</span>'
            f'<button {hx_attrs} class="{btn_classes}">'
            f'<span>▶</span><span>Executar Novamente</span></button>'
            f'</div>'
        )

    if status == "error":
        err = (state.get("error") or "Erro")[:80]
        return (
            f'<div id="analysis-widget" class="flex flex-col gap-2">'
            f'<span class="text-red-400 text-xs">✗ {err}</span>'
            f'<button {hx_attrs} class="{btn_classes}">'
            f'<span>↺</span><span>Tentar Novamente</span></button>'
            f'</div>'
        )

    # idle
    return (
        f'<div id="analysis-widget">'
        f'<button {hx_attrs} class="{btn_classes}">'
        f'<span>▶</span><span>Executar Análise IA</span>'
        f'</button></div>'
    )


def _common_ctx(conn: sqlite3.Connection) -> dict[str, Any]:
    pending_count = conn.execute(
        "SELECT COUNT(*) as c FROM recommendations WHERE status='pending'"
    ).fetchone()["c"]
    return {
        "pending_count": pending_count,
        "analysis_widget": _analysis_widget(),
    }


# ─── Pages ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> Any:
    conn = _get_conn()
    _ensure_fresh_prices()
    _ensure_fresh_btc_history()

    from crypto_advisor.db.repository import PortfolioRepository
    from crypto_advisor.tax.optimizer import TaxOptimizer

    positions = PortfolioRepository(conn).get_all()
    prices_brl = _price_cache["prices_brl"]
    fear_greed = _price_cache["fear_greed"]

    enriched: list[dict[str, Any]] = []
    total_value = 0.0
    total_cost = 0.0

    for pos in positions:
        if pos.symbol == "BRL":
            price = 1.0
        else:
            price = prices_brl.get(pos.symbol, pos.avg_price_brl)
        value = pos.quantity * price
        cost = pos.quantity * pos.avg_price_brl if pos.symbol != "BRL" else pos.quantity
        pnl = value - cost if pos.symbol != "BRL" else 0.0
        pnl_pct = (pnl / cost * 100) if (cost > 0 and pos.symbol != "BRL") else 0.0
        enriched.append({
            "symbol": pos.symbol,
            "quantity": pos.quantity,
            "avg_price_brl": pos.avg_price_brl,
            "current_price_brl": price,
            "value_brl": value,
            "pnl_brl": pnl,
            "pnl_pct": pnl_pct,
            "has_live_price": pos.symbol in prices_brl or pos.symbol == "BRL",
        })
        total_value += value
        if pos.symbol != "BRL":
            total_cost += cost

    if total_value > 0:
        _save_snapshot(conn, total_value, total_cost)

    # Portfolio evolution: 30-day BTC daily closes from Binance × current holdings.
    # Much more reliable than portfolio_snapshots (which only record when dashboard is open
    # and were saved with zero BTC price in early runs).
    btc_qty = next((p.quantity for p in positions if p.symbol == "BTC"), 0.0)
    brl_balance = next((p.quantity for p in positions if p.symbol == "BRL"), 0.0)
    btc_cost_brl = next((p.avg_price_brl for p in positions if p.symbol == "BTC"), 0.0)
    usd_brl = float(_price_cache.get("usd_brl_rate", 5.8))  # type: ignore[arg-type]

    if _btc_history_cache["prices_usd"] and btc_qty > 0:
        chart_dates = _btc_history_cache["dates"]
        chart_values = [btc_qty * p * usd_brl + brl_balance for p in _btc_history_cache["prices_usd"]]
        # Cost line only when avg_price_brl is set (not the zero default)
        chart_costs = (
            [btc_qty * btc_cost_brl + brl_balance for _ in _btc_history_cache["prices_usd"]]
            if btc_cost_brl > 0 else []
        )
        chart_label = "Patrimônio — 30 dias"
    else:
        chart_dates = []
        chart_values = []
        chart_costs = []
        chart_label = "Patrimônio — 30 dias"

    now = datetime.now(timezone.utc)
    tax_status = TaxOptimizer(conn).get_monthly_status(now.year, now.month)

    ctx = _common_ctx(conn)
    conn.close()

    prices_updated_at = (
        datetime.fromtimestamp(_price_cache["fetched_at"]).strftime("%H:%M")
        if _price_cache["fetched_at"] > 0 else None
    )

    ctx.update({
        "positions": enriched,
        "total_value_brl": total_value,
        "total_cost_brl": total_cost,
        "total_pnl_brl": total_value - total_cost,
        "total_pnl_pct": ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0.0,
        "fear_greed": fear_greed,
        "tax_status": tax_status,
        "chart_dates": chart_dates,
        "chart_values": chart_values,
        "chart_costs": chart_costs,
        "chart_label": chart_label,
        "prices_updated_at": prices_updated_at,
    })
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/recommendations", response_class=HTMLResponse)
async def recommendations_page(request: Request) -> Any:
    conn = _get_conn()
    _ensure_fresh_prices()

    rate: float = _price_cache.get("usd_brl_rate", 5.8)  # type: ignore[assignment]

    # Only show the latest week — history is not displayed per user preference
    latest_week_row = conn.execute(
        "SELECT MAX(week_date) as wd FROM recommendations"
    ).fetchone()
    latest_week = latest_week_row["wd"] if latest_week_row else None

    latest_recs = []
    if latest_week:
        latest_recs = [dict(r) for r in conn.execute(
            "SELECT * FROM recommendations WHERE week_date=? "
            "AND status != 'dismissed' "
            "ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, id DESC",
            (latest_week,),
        ).fetchall()]

    ctx = _common_ctx(conn)
    conn.close()
    ctx.update({
        "latest_week": latest_week,
        "latest_recs": latest_recs,
        "rate": rate,
    })
    return templates.TemplateResponse(request, "recommendations.html", ctx)


@app.get("/tax", response_class=HTMLResponse)
async def tax_page(request: Request) -> Any:
    conn = _get_conn()

    now = datetime.now(timezone.utc)
    from crypto_advisor.tax.optimizer import TaxOptimizer
    tax_status = TaxOptimizer(conn).get_monthly_status(now.year, now.month)

    history = [dict(r) for r in conn.execute(
        "SELECT year, month, total_sold_brl, realized_gain_brl, "
        "realized_loss_brl, tax_status FROM tax_tracker "
        "ORDER BY year DESC, month DESC LIMIT 12"
    ).fetchall()]

    ctx = _common_ctx(conn)
    conn.close()
    ctx.update({"tax_status": tax_status, "history": history})
    return templates.TemplateResponse(request, "tax.html", ctx)


# ─── API fragments (HTMX targets) ────────────────────────────────────────────

@app.post("/api/run-analysis")
async def api_run_analysis() -> HTMLResponse:
    with _analysis_lock:
        already_running = _analysis_state["status"] == "running"
    if not already_running:
        threading.Thread(target=_run_analysis_thread, daemon=True).start()
        time.sleep(0.1)  # let thread update state before rendering widget
    return HTMLResponse(_analysis_widget())


@app.get("/api/analysis-widget")
async def api_analysis_widget() -> HTMLResponse:
    return HTMLResponse(_analysis_widget())


def _render_rec_card(rec_id: int, status: str) -> HTMLResponse:
    """Render the full recommendation card after approve/reject via HTMX."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM recommendations WHERE id=?", (rec_id,)).fetchone()
    conn.close()
    if row is None:
        return HTMLResponse(f'<div id="rec-{rec_id}"></div>')
    rate: float = _price_cache.get("usd_brl_rate", 5.8)  # type: ignore[assignment]
    html = _jinja_env.get_template("_rec_card.html").render(rec=dict(row), rate=rate)
    return HTMLResponse(html)


@app.post("/api/recommendations/{rec_id}/approve")
async def api_approve(rec_id: int) -> HTMLResponse:
    conn = _get_conn()
    from crypto_advisor.db.repository import RecommendationRepository
    RecommendationRepository(conn).update_status(rec_id, "approved")
    conn.close()
    return _render_rec_card(rec_id, "approved")


@app.post("/api/recommendations/{rec_id}/reject")
async def api_reject(rec_id: int) -> HTMLResponse:
    conn = _get_conn()
    from crypto_advisor.db.repository import RecommendationRepository
    RecommendationRepository(conn).update_status(rec_id, "rejected")
    conn.close()
    return _render_rec_card(rec_id, "rejected")


@app.post("/api/recommendations/{rec_id}/dismiss")
async def api_dismiss(rec_id: int) -> HTMLResponse:
    conn = _get_conn()
    from crypto_advisor.db.repository import RecommendationRepository
    RecommendationRepository(conn).update_status(rec_id, "dismissed")
    conn.close()
    return HTMLResponse("")  # outerHTML swap with empty removes the element


@app.post("/api/sync-portfolio")
async def api_sync_portfolio() -> HTMLResponse:
    try:
        from crypto_advisor.data.mercado_bitcoin import MercadoBitcoinClient
        from crypto_advisor.db.repository import PortfolioRepository

        mb = MercadoBitcoinClient(
            api_id=os.environ["MB_API_ID"],
            api_secret=os.environ["MB_API_SECRET"],
            tapi_id=os.getenv("MB_TAPI_ID"),
            tapi_secret=os.getenv("MB_TAPI_SECRET"),
        )
        positions = mb.get_portfolio()
        mb.close()

        conn = _get_conn()
        PortfolioRepository(conn).upsert_bulk(positions)
        conn.close()

        _price_cache["fetched_at"] = 0.0  # force price refresh
        threading.Thread(target=_refresh_prices, daemon=True).start()

        return HTMLResponse(
            '<span id="sync-status" class="text-green-400 text-xs">✓ Sincronizado</span>'
        )
    except KeyError:
        return HTMLResponse(
            '<span id="sync-status" class="text-yellow-400 text-xs">⚠ MB_API_ID não configurado</span>',
            status_code=500,
        )
    except Exception as exc:
        short = str(exc)[:80]
        return HTMLResponse(
            f'<span id="sync-status" class="text-red-400 text-xs">✗ {short}</span>',
            status_code=500,
        )


# ─── Dev server ───────────────────────────────────────────────────────────────

def run(host: str = "0.0.0.0", port: int = 8080, reload: bool = False) -> None:
    import uvicorn
    uvicorn.run(
        "crypto_advisor.dashboard.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
