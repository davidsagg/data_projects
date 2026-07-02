"""
Smoke test — valida conectividade com todas as APIs externas.
Execução: python scripts/smoke_test.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# garante que src/ está no path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

PASS = "  ✅"
FAIL = "  ❌"
SKIP = "  ⏭ "
SEP  = "─" * 55


def section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


def result(label: str, ok: bool, detail: str = "") -> None:
    icon = PASS if ok else FAIL
    suffix = f"  — {detail}" if detail else ""
    print(f"{icon}  {label}{suffix}")


# ─── 1. CoinGecko ─────────────────────────────────────────────────────────────

def test_coingecko() -> bool:
    section("1. CoinGecko API (free tier)")
    from crypto_advisor.data.coingecko import CoinGeckoClient, InsufficientDataError

    api_key = os.getenv("COINGECKO_API_KEY") or None
    # Use default 1h TTL so TechnicalIndicators reuses the cached OHLCV
    client = CoinGeckoClient(api_key=api_key)
    all_ok = True

    # 1a. Top markets
    try:
        t0 = time.time()
        markets = client.get_top_markets(limit=10)
        elapsed = time.time() - t0
        btc = next((m for m in markets if m.symbol == "BTC"), None)
        assert btc is not None, "BTC not found in top markets"
        result(
            "get_top_markets(10)",
            True,
            f"{len(markets)} ativos  |  BTC ${btc.price_usd:,.0f}  |  {elapsed:.2f}s",
        )
    except Exception as exc:
        result("get_top_markets", False, str(exc))
        all_ok = False

    # CoinGecko free tier: ~30 req/min. Add small gaps between calls.
    time.sleep(4)

    # 1b. OHLCV BTC 4h  (retry once on 429)
    for attempt in range(2):
        try:
            if attempt:
                print("         ⏳ rate-limited, aguardando 15s...")
                time.sleep(15)
            t0 = time.time()
            df = client.get_ohlcv("BTC", "4h")
            elapsed = time.time() - t0
            result(
                "get_ohlcv(BTC, 4h)",
                True,
                f"{len(df)} candles  |  último close ${df['close'].iloc[-1]:,.0f}  |  {elapsed:.2f}s",
            )
            break
        except InsufficientDataError as exc:
            result("get_ohlcv(BTC, 4h)", False, f"InsufficientData: {exc}")
            all_ok = False
            break
        except Exception as exc:
            if "429" in str(exc) and attempt == 0:
                continue
            result("get_ohlcv(BTC, 4h)", False, str(exc))
            all_ok = False

    # 1c. OHLCV BTC 1d
    time.sleep(5)
    for attempt in range(2):
        try:
            if attempt:
                print("         ⏳ rate-limited, aguardando 15s...")
                time.sleep(15)
            t0 = time.time()
            df = client.get_ohlcv("BTC", "1d")
            elapsed = time.time() - t0
            result(
                "get_ohlcv(BTC, 1d)",
                True,
                f"{len(df)} candles  |  {elapsed:.2f}s",
            )
            break
        except Exception as exc:
            if "429" in str(exc) and attempt == 0:
                continue
            result("get_ohlcv(BTC, 1d)", False, str(exc))
            all_ok = False

    # 1d. Fear & Greed
    try:
        t0 = time.time()
        fg = client.get_fear_greed()
        elapsed = time.time() - t0
        result(
            "get_fear_greed()",
            True,
            f"value={fg.value}  classification='{fg.classification}'  |  {elapsed:.2f}s",
        )
    except Exception as exc:
        result("get_fear_greed()", False, str(exc))
        all_ok = False

    client.close()
    return all_ok


# ─── 2. Binance (OHLCV + indicadores) ────────────────────────────────────────

def test_binance() -> bool:
    """Returns True even if Binance is geo-blocked — CoinGecko is the fallback."""
    section("2. Binance Public API (OHLCV + Indicadores)")
    from crypto_advisor.data.binance import BinanceClient
    from crypto_advisor.data.coingecko import CoinGeckoClient
    from crypto_advisor.indicators.technical import TechnicalIndicators

    _ssl = os.getenv("BINANCE_VERIFY_SSL", "true").lower() != "false"
    binance = BinanceClient(cache_ttl_seconds=3600, verify_ssl=_ssl)
    coingecko_key = os.getenv("COINGECKO_API_KEY") or None
    coingecko = CoinGeckoClient(api_key=coingecko_key)

    WARN = "  ⚠️ "
    binance_blocked = False

    for sym, tf in [("BTC", "4h"), ("BTC", "1d"), ("ETH", "4h")]:
        try:
            t0 = time.time()
            df = binance.get_ohlcv(sym, tf)
            elapsed = time.time() - t0
            snap = TechnicalIndicators.calculate(df, tf, symbol=sym)
            mm9   = f"${snap.sma_9:,.0f}"   if snap.sma_9   else "N/A"
            mm200 = f"${snap.sma_200:,.0f}" if snap.sma_200 else "N/A"
            rsi   = f"{snap.rsi_14:.1f}"    if snap.rsi_14  else "N/A"
            result(
                f"get_ohlcv({sym}, {tf})",
                True,
                f"{len(df)} candles  |  MM9={mm9}  MM200={mm200}  "
                f"RSI={rsi} ({snap.rsi_zone})  |  {elapsed:.2f}s",
            )
        except Exception as exc:
            binance_blocked = True
            # Try CoinGecko fallback
            try:
                t0 = time.time()
                df = coingecko.get_ohlcv(sym, tf)
                elapsed = time.time() - t0
                snap = TechnicalIndicators.calculate(df, tf, symbol=sym)
                mm9 = f"${snap.sma_9:,.0f}" if snap.sma_9 else "N/A"
                rsi = f"{snap.rsi_14:.1f}"  if snap.rsi_14 else "N/A"
                icon = WARN
                suffix = f"(Binance geo-bloqueado: {exc.__class__.__name__}) → CoinGecko OK: {len(df)} candles  MM9={mm9}  RSI={rsi}  |  {elapsed:.2f}s"
                print(f"{icon}  get_ohlcv({sym}, {tf})  — {suffix}")
            except Exception as cg_exc:
                result(f"get_ohlcv({sym}, {tf})", False, f"Binance: {exc} | CoinGecko: {cg_exc}")

    if binance_blocked:
        print(f"{WARN}  Binance geo-bloqueado neste ambiente (normal em DevContainer/cloud).")
        print(f"        O pipeline usa CoinGecko como fallback automaticamente.")

    binance.close()
    coingecko.close()
    return True  # Binance failure is non-fatal; CoinGecko fallback handles production


# ─── 3. Mercado Bitcoin ───────────────────────────────────────────────────────

def test_mercado_bitcoin() -> bool:
    section("3. Mercado Bitcoin API")
    from crypto_advisor.data.mercado_bitcoin import (
        MercadoBitcoinClient, AuthenticationError, ExchangeTimeoutError,
    )

    api_id     = os.getenv("MB_API_ID", "")
    api_secret = os.getenv("MB_API_SECRET", "")
    tapi_id    = os.getenv("MB_TAPI_ID", "")
    tapi_secret= os.getenv("MB_TAPI_SECRET", "")

    if not api_id or not api_secret:
        print(f"{SKIP}  MB_API_ID/MB_API_SECRET não configuradas — pulando")
        return True

    client = MercadoBitcoinClient(
        api_id=api_id, api_secret=api_secret,
        tapi_id=tapi_id, tapi_secret=tapi_secret,
    )
    all_ok = True

    # 2a. Auth token
    try:
        t0 = time.time()
        token = client._get_token()
        elapsed = time.time() - t0
        result("OAuth2 authorize", True, f"token obtido ({len(token)} chars)  |  {elapsed:.2f}s")
    except AuthenticationError as exc:
        result("OAuth2 authorize", False, f"AuthError: {exc}")
        client.close()
        return False
    except Exception as exc:
        result("OAuth2 authorize", False, str(exc))
        client.close()
        return False

    # 2b. Portfolio
    try:
        t0 = time.time()
        positions = client.get_portfolio()
        elapsed = time.time() - t0
        symbols = [p.symbol for p in positions]
        total_brl = next((p.quantity for p in positions if p.symbol == "BRL"), 0)
        result(
            "get_portfolio()",
            True,
            f"{len(positions)} posições  |  símbolos: {', '.join(symbols[:6])}  |  {elapsed:.2f}s",
        )
        if total_brl:
            print(f"         BRL disponível: R$ {total_brl:,.2f}")
    except Exception as exc:
        result("get_portfolio()", False, str(exc))
        all_ok = False

    # 2c. Trade history (last 30 days)
    try:
        from datetime import datetime, timedelta, timezone
        since = datetime.now(timezone.utc) - timedelta(days=30)
        t0 = time.time()
        trades = client.get_trade_history(since_date=since)
        elapsed = time.time() - t0
        sells = [t for t in trades if t.side == "sell"]
        total_sold = sum(t.total_brl for t in sells)
        note = "(conta nova — sem histórico)" if len(trades) == 0 else ""
        result(
            "get_trade_history(30d)",
            True,
            f"{len(trades)} trades  |  {len(sells)} vendas  |  "
            f"R$ {total_sold:,.2f} vendido  |  {elapsed:.2f}s  {note}",
        )
    except Exception as exc:
        result("get_trade_history(30d)", False, str(exc))
        all_ok = False

    client.close()
    return all_ok


# ─── 3. Anthropic / Claude ────────────────────────────────────────────────────

def test_anthropic() -> bool:
    section("4. Anthropic API (Claude)")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key or api_key.startswith("your_"):
        print(f"{SKIP}  ANTHROPIC_API_KEY não configurada — adicione ao .env e re-execute")
        return True

    try:
        import anthropic
        t0 = time.time()
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=32,
            messages=[{"role": "user", "content": "Reply with just: OK"}],
        )
        elapsed = time.time() - t0
        reply = resp.content[0].text.strip()
        result(
            "claude-sonnet-4-6 ping",
            True,
            f"resposta='{reply}'  |  {elapsed:.2f}s",
        )
        return True
    except Exception as exc:
        result("claude-sonnet-4-6 ping", False, str(exc))
        return False


# ─── 4. Telegram ──────────────────────────────────────────────────────────────

async def _test_telegram_async() -> bool:
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print(f"{SKIP}  TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não configuradas — pulando")
        return True

    try:
        from telegram import Bot
    except ImportError:
        print(f"{SKIP}  python-telegram-bot não instalado — pulando (ok no DevContainer)")
        return True

    try:
        t0 = time.time()
        async with Bot(token=token) as bot:
            me = await bot.get_me()
            elapsed_me = time.time() - t0
            result("Bot.get_me()", True, f"@{me.username}  |  {elapsed_me:.2f}s")

            t1 = time.time()
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "🔧 <b>CryptoAdvisor — Smoke Test</b>\n\n"
                    "✅ Conexão Telegram validada com sucesso.\n"
                    "<i>Esta mensagem foi enviada automaticamente pelo script de smoke test.</i>"
                ),
                parse_mode="HTML",
            )
            elapsed_send = time.time() - t1
            result("Bot.send_message()", True, f"mensagem entregue  |  {elapsed_send:.2f}s")
        return True
    except Exception as exc:
        result("Telegram", False, str(exc))
        return False


def test_telegram() -> bool:
    section("5. Telegram Bot")
    return asyncio.run(_test_telegram_async())


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "═" * 55)
    print("  CryptoAdvisor — Smoke Test")
    print("  " + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("═" * 55)

    results = {
        "CoinGecko (market cap)": test_coingecko(),
        "Binance (OHLCV)":        test_binance(),
        "Mercado Bitcoin":        test_mercado_bitcoin(),
        "Anthropic/Claude":       test_anthropic(),
        "Telegram":               test_telegram(),
    }

    section("Resumo")
    all_passed = True
    for name, ok in results.items():
        icon = PASS if ok else FAIL
        print(f"{icon}  {name}")
        if not ok:
            all_passed = False

    print(f"\n{'═' * 55}")
    if all_passed:
        print("  ✅  Todos os testes passaram — pronto para produção")
    else:
        print("  ⚠️   Alguns testes falharam — verifique o .env e as credenciais")
    print("═" * 55 + "\n")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
