"""CoinGecko API client with in-memory + disk TTL cache."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from ..models import FearGreedData, MarketData

# ─── Constants ────────────────────────────────────────────────────────────────

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"

STABLECOINS = {"usdt", "usdc", "dai", "busd", "tusd", "usdp", "gusd", "frax", "lusd", "usdd"}

# Ticker → CoinGecko coin ID
SYMBOL_TO_ID: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "BCH": "bitcoin-cash",
    "NEAR": "near",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "INJ": "injective-protocol",
    "SUI": "sui",
    "SEI": "sei-network",
    "TIA": "celestia",
    "PYTH": "pyth-network",
    "JTO": "jito-governance-token",
}

# Days param per timeframe → used in /coins/{id}/ohlc endpoint.
#
# CoinGecko free tier granularity (auto-selected by API):
#   days ≤ 30  → 4-hourly candles (180 candles max for 30 days)
#   days 31-90 → daily candles
#   days > 90  → wider intervals (free tier caps effective history at ~90 days)
#
# For MM200 on the daily chart we fetch the max range ("max") which gives
# ~365+ candles on most coins.  MM200 is skipped/None when insufficient data.
_TIMEFRAME_DAYS = {
    "4h": "30",   # 180 4h candles — free tier max (MM9/21/50/100 ✓)
    "1d": "365",  # ~92 daily candles on free tier (MM9/21/50/90 ✓ — MM200 = None)
}

# Per-timeframe minimum candle requirements (CoinGecko free tier limits)
_MIN_CANDLES: dict[str, int] = {
    "4h": 150,   # expect 180 on free tier — enough for RSI, MACD, Bollinger, MM100
    "1d":  90,   # expect ~92 on free tier — enough for RSI, MACD, Bollinger, MM90
}


# ─── Custom exceptions ────────────────────────────────────────────────────────

class InsufficientDataError(Exception):
    """Raised when the API returns fewer candles than required (< 200)."""


class RateLimitError(Exception):
    """Raised on HTTP 429 from CoinGecko."""


# ─── Client ───────────────────────────────────────────────────────────────────

class CoinGeckoClient:
    MIN_CANDLES = 200

    # Free tier (no key): ~30 req/min → space at 4s to survive burst history
    # Demo/Pro tier (with key): much higher limits, 0.5s is safe
    FREE_TIER_INTERVAL = 4.0
    KEYED_TIER_INTERVAL = 0.5

    def __init__(
        self,
        api_key: str | None = None,
        cache_ttl_seconds: int = 3600,
        retry_base_seconds: float = 5.0,      # set to 0 in tests
        request_interval_seconds: float | None = None,  # auto-detected from api_key
        disk_cache_dir: str | None = None,     # None = auto (data/cache/coingecko/)
    ) -> None:
        headers: dict[str, str] = {}
        if api_key:
            # Demo keys start with "CG-"; Pro keys use a different format
            if api_key.startswith("CG-"):
                headers["x-cg-demo-api-key"] = api_key
            else:
                headers["x-cg-pro-api-key"] = api_key
        self._http = httpx.Client(headers=headers, timeout=30.0)
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}
        self._retry_base = retry_base_seconds
        if request_interval_seconds is None:
            self._req_interval = self.KEYED_TIER_INTERVAL if api_key else self.FREE_TIER_INTERVAL
        else:
            self._req_interval = request_interval_seconds
        self._last_req_at: float = 0.0

        # Disk cache — survives process restarts within the TTL window.
        # Disabled when retry_base_seconds=0 (test mode) or disk_cache_dir="".
        _disk_enabled = retry_base_seconds > 0 and disk_cache_dir != ""
        if _disk_enabled and disk_cache_dir is None:
            _base = Path(os.getenv("DB_PATH", "data/crypto_advisor.db")).parent
            disk_cache_dir = str(_base / "cache" / "coingecko")
        self._disk_cache_dir = Path(disk_cache_dir) if _disk_enabled else None

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _disk_cache_path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "_")
        return self._disk_cache_dir / f"{safe}.json"

    def _get_cached(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry and (time.monotonic() - entry[0]) < self._cache_ttl:
            return entry[1]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        self._cache[key] = (time.monotonic(), value)

    def _get_raw_cached(self, url: str, params: dict | None) -> Any | None:
        """Disk cache for raw HTTP responses — survives process restarts."""
        if self._disk_cache_dir is None:
            return None
        import hashlib
        key = hashlib.md5((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
        path = self._disk_cache_dir / f"{key}.json"
        if path.exists():
            try:
                envelope = json.loads(path.read_text())
                if time.time() - envelope["ts"] < self._cache_ttl:
                    return envelope["data"]
            except Exception:
                path.unlink(missing_ok=True)
        return None

    def _set_raw_cached(self, url: str, params: dict | None, data: Any) -> None:
        if self._disk_cache_dir is None:
            return
        import hashlib
        key = hashlib.md5((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
        path = self._disk_cache_dir / f"{key}.json"
        try:
            self._disk_cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"ts": time.time(), "data": data}))
        except Exception:
            pass  # disk cache is best-effort

    # ── HTTP helper ───────────────────────────────────────────────────────────

    def _get(self, url: str, params: dict | None = None, _retries: int = 3) -> Any:
        """GET with disk + in-memory cache, rate limiting, and exponential backoff on 429."""
        # Disk cache: serves identical requests across process restarts within TTL
        cached_raw = self._get_raw_cached(url, params)
        if cached_raw is not None:
            return cached_raw

        # Enforce minimum interval between requests to stay under 30 req/min
        if self._req_interval > 0:
            elapsed = time.monotonic() - self._last_req_at
            if elapsed < self._req_interval:
                time.sleep(self._req_interval - elapsed)

        for attempt in range(_retries):
            response = self._http.get(url, params=params)

            self._last_req_at = time.monotonic()

            if response.status_code == 200:
                data = response.json()
                self._set_raw_cached(url, params, data)
                return data

            if response.status_code == 429:
                wait = 2 ** attempt * self._retry_base * 2  # 10s, 20s, 40s (default)
                if attempt < _retries - 1:
                    time.sleep(wait)
                    continue
                raise RateLimitError("CoinGecko rate limit exceeded (429). Wait and retry.")

            # 400 on free tier is often a transient rate-limit signal
            if response.status_code == 400 and attempt < _retries - 1:
                time.sleep(2 ** attempt * self._retry_base)  # 5s, 10s (default)
                continue

            response.raise_for_status()

        response.raise_for_status()  # final raise if loop exhausted

    # ── Public API ────────────────────────────────────────────────────────────

    def get_top_markets(self, limit: int = 20) -> list[MarketData]:
        """Top `limit` coins by market cap, stablecoins excluded. Prices in USD and BRL."""
        cache_key = f"top_markets_{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        url = f"{COINGECKO_BASE}/coins/markets"
        base_params = {
            "order": "market_cap_desc",
            "per_page": limit + 10,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "7d",
        }

        data_usd = self._get(url, params={**base_params, "vs_currency": "usd"})
        data_brl = self._get(url, params={**base_params, "vs_currency": "brl"})

        # Build BRL price lookup keyed by coin id
        brl_by_id: dict[str, float] = {
            item["id"]: item.get("current_price") or 0.0
            for item in data_brl
        }

        markets: list[MarketData] = []
        for item in data_usd:
            if item["symbol"].lower() in STABLECOINS:
                continue
            markets.append(MarketData(
                symbol=item["symbol"].upper(),
                price_usd=item.get("current_price") or 0.0,
                price_brl=brl_by_id.get(item["id"], 0.0),
                change_24h_pct=item.get("price_change_percentage_24h") or 0.0,
                change_7d_pct=item.get("price_change_percentage_7d_in_currency") or 0.0,
                volume_24h_usd=item.get("total_volume") or 0.0,
                market_cap_usd=item.get("market_cap") or 0.0,
                market_cap_rank=item.get("market_cap_rank"),
            ))
            if len(markets) >= limit:
                break

        self._set_cached(cache_key, markets)
        return markets

    def get_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """OHLCV DataFrame for `symbol` at `timeframe` ('4h' or '1d').

        Raises:
            KeyError: if symbol is not in the known SYMBOL_TO_ID mapping.
            InsufficientDataError: if the API returns fewer candles than the
                                   per-timeframe minimum (_MIN_CANDLES).
        """
        coin_id = SYMBOL_TO_ID[symbol]  # raises KeyError for unknown symbols
        days = _TIMEFRAME_DAYS.get(timeframe, "30")
        min_required = _MIN_CANDLES.get(timeframe, self.MIN_CANDLES)
        cache_key = f"ohlcv_{symbol}_{timeframe}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        url = f"{COINGECKO_BASE}/coins/{coin_id}/ohlc?vs_currency=usd&days={days}"
        raw = self._get(url)

        if len(raw) < min_required:
            raise InsufficientDataError(
                f"{symbol} {timeframe}: only {len(raw)} candles returned, "
                f"need >= {min_required}."
            )

        # CoinGecko OHLC format: [[timestamp_ms, open, high, low, close], ...]
        # Note: no volume field — CoinGecko OHLC omits volume, use 0 as placeholder
        df = pd.DataFrame(raw, columns=["timestamp_ms", "open", "high", "low", "close"])
        df.index = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp_ms"])
        df["volume"] = 0.0  # volume not available in CoinGecko OHLC endpoint
        df = df.sort_index()

        self._set_cached(cache_key, df)
        return df

    def get_fear_greed(self) -> FearGreedData:
        """Fetch the current Fear & Greed Index from alternative.me."""
        cache_key = "fear_greed"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        raw = self._get(FEAR_GREED_URL)
        entry = raw["data"][0]
        fg = FearGreedData(
            value=int(entry["value"]),
            classification=entry["value_classification"],
            timestamp=datetime.fromtimestamp(int(entry["timestamp"])),
        )
        self._set_cached(cache_key, fg)
        return fg

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "CoinGeckoClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
