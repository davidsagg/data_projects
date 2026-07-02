"""Binance public API client — OHLCV data, no authentication required.

Rate limit: 1200 req/min (weight-based). No API key needed for klines.
Used as the primary OHLCV source, replacing CoinGecko for indicator calculation.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pandas as pd

BINANCE_BASE = "https://api.binance.com/api/v3"

# Ticker → Binance trading pair (USDT-quoted; ≈ USD for analysis purposes)
SYMBOL_TO_PAIR: dict[str, str] = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "BNB":  "BNBUSDT",
    "SOL":  "SOLUSDT",
    "XRP":  "XRPUSDT",
    "ADA":  "ADAUSDT",
    "AVAX": "AVAXUSDT",
    "DOT":  "DOTUSDT",
    "MATIC":"MATICUSDT",
    "LINK": "LINKUSDT",
    "UNI":  "UNIUSDT",
    "ATOM": "ATOMUSDT",
    "LTC":  "LTCUSDT",
    "BCH":  "BCHUSDT",
    "NEAR": "NEARUSDT",
    "APT":  "APTUSDT",
    "ARB":  "ARBUSDT",
    "OP":   "OPUSDT",
    "INJ":  "INJUSDT",
    "SUI":  "SUIUSDT",
    "SEI":  "SEIUSDT",
    "TIA":  "TIAUSDT",
    "WLD":  "WLDUSDT",
    "LDO":  "LDOUSDT",
    "AAVE": "AAVEUSDT",
    "CRV":  "CRVUSDT",
    "DYDX": "DYDXUSDT",
    "SAND": "SANDUSDT",
    "MANA": "MANAUSDT",
    "AXS":  "AXSUSDT",
    "CHZ":  "CHZUSDT",
    "ENJ":  "ENJUSDT",
    "GALA": "GALAUSDT",
}

# Candles requested per timeframe — enough for MM200 on both
_LIMITS: dict[str, int] = {
    "4h": 250,   # ~41 days of 4h candles
    "1d": 400,   # ~13 months of daily candles
}


class BinanceClient:
    """Fetches OHLCV klines from Binance public API."""

    def __init__(
        self,
        cache_ttl_seconds: int = 3600,
        base_url: str = BINANCE_BASE,
        verify_ssl: bool = True,
    ) -> None:
        # verify_ssl=False needed in some DevContainer/proxy environments.
        # Always True in production (MacBook M2 / servers with proper cert store).
        self._http = httpx.Client(timeout=30.0, verify=verify_ssl)
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}
        self._base = base_url

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _get_cached(self, key: str) -> pd.DataFrame | None:
        entry = self._cache.get(key)
        if entry and (time.monotonic() - entry[0]) < self._cache_ttl:
            return entry[1]
        return None

    def _set_cached(self, key: str, value: pd.DataFrame) -> None:
        self._cache[key] = (time.monotonic(), value)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Return OHLCV DataFrame for `symbol` at `timeframe` ('4h' or '1d').

        Raises:
            KeyError: symbol not in SYMBOL_TO_PAIR mapping.
            httpx.HTTPStatusError: non-200 response.
            httpx.TimeoutException: request timed out.
        """
        sym_upper = symbol.upper()
        pair = SYMBOL_TO_PAIR[sym_upper]  # KeyError for unknown symbols
        limit = _LIMITS.get(timeframe, 250)
        interval = timeframe  # Binance uses same notation: "4h", "1d"

        cache_key = f"ohlcv_{sym_upper}_{timeframe}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        url = f"{self._base}/klines"
        response = self._http.get(url, params={
            "symbol":   pair,
            "interval": interval,
            "limit":    limit,
        })
        response.raise_for_status()
        raw = response.json()

        # Binance kline columns:
        # [0] open_time_ms, [1] open, [2] high, [3] low, [4] close, [5] volume, ...
        df = pd.DataFrame(raw, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore",
        ])
        df.index = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        df = df.sort_index()

        self._set_cached(cache_key, df)
        return df

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "BinanceClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
