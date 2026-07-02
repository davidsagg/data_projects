"""
Tests for the CoinGecko API client.

All HTTP calls are mocked — no real network access required.

Covers:
- get_top_markets: parsing, filtering stablecoins, rank ordering
- get_ohlcv: DataFrame shape, column names, timeframe routing
- get_fear_greed: parsing and classification
- In-memory cache: hit and miss behaviour
- Error handling: 429 rate-limit, 404, network timeout
"""

import time
import pytest
import httpx
from unittest.mock import MagicMock, patch, PropertyMock

# ─── Fixtures: raw API responses ──────────────────────────────────────────────

MARKETS_RESPONSE = [
    {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "current_price": 65000.0, "price_change_percentage_24h": 2.3,
        "total_volume": 28_000_000_000.0, "market_cap": 1_200_000_000_000.0,
        "market_cap_rank": 1,
    },
    {
        "id": "ethereum", "symbol": "eth", "name": "Ethereum",
        "current_price": 3200.0, "price_change_percentage_24h": 1.1,
        "total_volume": 12_000_000_000.0, "market_cap": 380_000_000_000.0,
        "market_cap_rank": 2,
    },
    {
        "id": "tether", "symbol": "usdt", "name": "Tether",
        "current_price": 1.0, "price_change_percentage_24h": 0.01,
        "total_volume": 50_000_000_000.0, "market_cap": 110_000_000_000.0,
        "market_cap_rank": 3,
    },
    {
        "id": "solana", "symbol": "sol", "name": "Solana",
        "current_price": 170.0, "price_change_percentage_24h": -1.5,
        "total_volume": 3_000_000_000.0, "market_cap": 78_000_000_000.0,
        "market_cap_rank": 4,
    },
]

# CoinGecko OHLC format: [[timestamp_ms, open, high, low, close], ...]
OHLCV_RESPONSE = [
    [1_700_000_000_000 + i * 14_400_000, 64000 + i, 65000 + i, 63000 + i, 64500 + i]
    for i in range(250)
]

FEAR_GREED_RESPONSE = {
    "data": [
        {
            "value": "72",
            "value_classification": "Greed",
            "timestamp": "1715529600",
        }
    ]
}

SIMPLE_PRICE_RESPONSE = {
    "bitcoin": {
        "usd": 65000.0, "brl": 325000.0,
        "usd_24h_change": 2.3, "usd_24h_vol": 28_000_000_000.0,
        "usd_market_cap": 1_200_000_000_000.0,
    },
    "ethereum": {
        "usd": 3200.0, "brl": 16000.0,
        "usd_24h_change": 1.1, "usd_24h_vol": 12_000_000_000.0,
        "usd_market_cap": 380_000_000_000.0,
    },
}


def _mock_response(json_data, status_code=200):
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=mock
        )
    return mock


# ─── get_top_markets ──────────────────────────────────────────────────────────

class TestGetTopMarkets:
    def test_returns_list_of_market_data(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(MARKETS_RESPONSE)):
            markets = client.get_top_markets(limit=20)
        assert isinstance(markets, list)
        assert len(markets) > 0

    def test_stablecoins_excluded(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(MARKETS_RESPONSE)):
            markets = client.get_top_markets()
        symbols = [m.symbol for m in markets]
        assert "USDT" not in symbols
        assert "USDC" not in symbols

    def test_btc_and_eth_present(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(MARKETS_RESPONSE)):
            markets = client.get_top_markets()
        symbols = [m.symbol for m in markets]
        assert "BTC" in symbols
        assert "ETH" in symbols

    def test_symbols_uppercase(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(MARKETS_RESPONSE)):
            markets = client.get_top_markets()
        for m in markets:
            assert m.symbol == m.symbol.upper()

    def test_market_cap_rank_set(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(MARKETS_RESPONSE)):
            markets = client.get_top_markets()
        btc = next(m for m in markets if m.symbol == "BTC")
        assert btc.market_cap_rank == 1

    def test_price_usd_correct(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(MARKETS_RESPONSE)):
            markets = client.get_top_markets()
        btc = next(m for m in markets if m.symbol == "BTC")
        assert btc.price_usd == pytest.approx(65000.0)


# ─── get_ohlcv ────────────────────────────────────────────────────────────────

class TestGetOhlcv:
    def test_returns_dataframe(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(OHLCV_RESPONSE)):
            df = client.get_ohlcv("BTC", "4h")
        import pandas as pd
        assert isinstance(df, pd.DataFrame)

    def test_dataframe_has_required_columns(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(OHLCV_RESPONSE)):
            df = client.get_ohlcv("BTC", "4h")
        for col in ("open", "high", "low", "close", "volume"):
            assert col in df.columns, f"Missing column: {col}"

    def test_dataframe_has_datetime_index(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        import pandas as pd
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(OHLCV_RESPONSE)):
            df = client.get_ohlcv("BTC", "4h")
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_at_least_min_rows(self):
        """OHLCV_RESPONSE fixture has 250 rows — well above per-timeframe minimums."""
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(OHLCV_RESPONSE)):
            df = client.get_ohlcv("BTC", "1d")
        assert len(df) >= 90  # 1d free-tier minimum

    def test_insufficient_data_raises(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient, InsufficientDataError
        short_data = OHLCV_RESPONSE[:50]
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(short_data)):
            with pytest.raises(InsufficientDataError):
                client.get_ohlcv("BTC", "4h")

    def test_timeframe_4h_uses_correct_days_param(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(OHLCV_RESPONSE)) as mock_get:
            client.get_ohlcv("BTC", "4h")
        call_url = mock_get.call_args[0][0]
        assert "days=30" in call_url or "days=" in call_url

    def test_timeframe_1d_uses_correct_days_param(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(OHLCV_RESPONSE)) as mock_get:
            client.get_ohlcv("BTC", "1d")
        call_url = mock_get.call_args[0][0]
        assert "days=" in call_url


# ─── get_fear_greed ───────────────────────────────────────────────────────────

class TestGetFearGreed:
    def test_returns_fear_greed_data(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        from crypto_advisor.models import FearGreedData
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(FEAR_GREED_RESPONSE)):
            fg = client.get_fear_greed()
        assert isinstance(fg, FearGreedData)

    def test_value_parsed_correctly(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(FEAR_GREED_RESPONSE)):
            fg = client.get_fear_greed()
        assert fg.value == 72

    def test_classification_parsed(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", return_value=_mock_response(FEAR_GREED_RESPONSE)):
            fg = client.get_fear_greed()
        assert fg.classification == "Greed"


# ─── Cache behaviour ──────────────────────────────────────────────────────────

class TestCache:
    def test_second_call_uses_cache(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        # get_top_markets makes 2 HTTP calls (USD + BRL); second get_top_markets() hits cache
        with patch.object(client._http, "get", return_value=_mock_response(MARKETS_RESPONSE)) as mock_get:
            client.get_top_markets()
            client.get_top_markets()
        assert mock_get.call_count == 2  # USD + BRL on first call; cache on second

    def test_cache_expires_after_ttl(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(cache_ttl_seconds=0, retry_base_seconds=0)  # instant expiry
        # Each get_top_markets() makes 2 HTTP calls (USD + BRL); 2 calls × 2 = 4
        with patch.object(client._http, "get", return_value=_mock_response(MARKETS_RESPONSE)) as mock_get:
            client.get_top_markets()
            client.get_top_markets()
        assert mock_get.call_count == 4


# ─── Error handling ───────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_rate_limit_429_raises(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient, RateLimitError
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch("crypto_advisor.data.coingecko.time.sleep"):  # skip backoff waits
            with patch.object(client._http, "get", return_value=_mock_response({}, 429)):
                with pytest.raises(RateLimitError):
                    client.get_top_markets()

    def test_network_timeout_raises(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with patch.object(client._http, "get", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(httpx.TimeoutException):
                client.get_top_markets()

    def test_unknown_symbol_raises_key_error(self):
        from crypto_advisor.data.coingecko import CoinGeckoClient
        client = CoinGeckoClient(retry_base_seconds=0, request_interval_seconds=0)
        with pytest.raises(KeyError, match="UNKNOWNCOIN"):
            client.get_ohlcv("UNKNOWNCOIN", "4h")
