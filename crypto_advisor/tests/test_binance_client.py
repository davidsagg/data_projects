"""
Tests for the Binance public OHLCV client.

No auth required. All HTTP calls are mocked.

Covers:
- get_ohlcv: returns DataFrame with correct columns and DatetimeIndex
- Symbol mapping (BTC → BTCUSDT)
- Timeframe mapping (4h → 4h, 1d → 1d)
- Returns at least 200 rows for 4h and 365 for 1d
- Unknown symbol raises KeyError
- Cache hit on second call
- Network timeout propagates
"""

import pytest
import httpx
from unittest.mock import MagicMock, patch


# ─── Fixtures ─────────────────────────────────────────────────────────────────

# Binance klines format:
# [openTime, open, high, low, close, volume, closeTime, quoteVol, trades, ...]
def _make_klines(n: int = 250, base_price: float = 80_000.0) -> list:
    return [
        [
            1_700_000_000_000 + i * 14_400_000,  # open time ms
            str(base_price + i * 10),            # open
            str(base_price + i * 10 + 200),      # high
            str(base_price + i * 10 - 200),      # low
            str(base_price + i * 10 + 50),       # close
            str(1_000_000 + i * 100),             # volume
            1_700_000_000_000 + i * 14_400_000 + 14_399_999,  # close time
            "80000000",                           # quote volume
            1000,                                 # trades
            "500000",                             # taker buy base
            "40000000",                           # taker buy quote
            "0",                                  # unused
        ]
        for i in range(n)
    ]


def _mock_response(json_data, status_code: int = 200):
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=mock
        )
    return mock


def _make_client():
    from crypto_advisor.data.binance import BinanceClient
    return BinanceClient(cache_ttl_seconds=0)


# ─── DataFrame structure ──────────────────────────────────────────────────────

class TestDataFrameStructure:
    def test_returns_dataframe(self):
        import pandas as pd
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())):
            df = client.get_ohlcv("BTC", "4h")
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())):
            df = client.get_ohlcv("BTC", "4h")
        for col in ("open", "high", "low", "close", "volume"):
            assert col in df.columns, f"Missing column: {col}"

    def test_has_datetime_index(self):
        import pandas as pd
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())):
            df = client.get_ohlcv("BTC", "4h")
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_columns_are_float(self):
        import numpy as np
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())):
            df = client.get_ohlcv("BTC", "4h")
        for col in ("open", "high", "low", "close", "volume"):
            assert np.issubdtype(df[col].dtype, np.floating), f"{col} is not float"

    def test_sorted_ascending_by_time(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())):
            df = client.get_ohlcv("BTC", "4h")
        assert df.index.is_monotonic_increasing

    def test_high_always_gte_low(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())):
            df = client.get_ohlcv("BTC", "4h")
        assert (df["high"] >= df["low"]).all()


# ─── Symbol mapping ───────────────────────────────────────────────────────────

class TestSymbolMapping:
    def test_btc_maps_to_btcusdt(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())) as mock_get:
            client.get_ohlcv("BTC", "4h")
        params = mock_get.call_args[1].get("params", {})
        assert params.get("symbol") == "BTCUSDT"

    def test_eth_maps_to_ethusdt(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())) as mock_get:
            client.get_ohlcv("ETH", "1d")
        params = mock_get.call_args[1].get("params", {})
        assert params.get("symbol") == "ETHUSDT"

    def test_sol_maps_to_solusdt(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())) as mock_get:
            client.get_ohlcv("SOL", "4h")
        params = mock_get.call_args[1].get("params", {})
        assert params.get("symbol") == "SOLUSDT"

    def test_unknown_symbol_raises_key_error(self):
        client = _make_client()
        with pytest.raises(KeyError, match="UNKNOWNCOIN"):
            client.get_ohlcv("UNKNOWNCOIN", "4h")

    def test_symbol_case_insensitive(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())):
            df = client.get_ohlcv("btc", "4h")
        assert len(df) > 0


# ─── Timeframe and limit ──────────────────────────────────────────────────────

class TestTimeframeAndLimit:
    def test_4h_interval_sent_as_4h(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())) as mock_get:
            client.get_ohlcv("BTC", "4h")
        params = mock_get.call_args[1].get("params", {})
        assert params.get("interval") == "4h"

    def test_1d_interval_sent_as_1d(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())) as mock_get:
            client.get_ohlcv("BTC", "1d")
        params = mock_get.call_args[1].get("params", {})
        assert params.get("interval") == "1d"

    def test_4h_requests_at_least_200_candles(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines(250))) as mock_get:
            client.get_ohlcv("BTC", "4h")
        params = mock_get.call_args[1].get("params", {})
        assert int(params.get("limit", 0)) >= 200

    def test_1d_requests_at_least_365_candles(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines(400))) as mock_get:
            client.get_ohlcv("BTC", "1d")
        params = mock_get.call_args[1].get("params", {})
        assert int(params.get("limit", 0)) >= 365

    def test_returns_correct_row_count(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines(250))):
            df = client.get_ohlcv("BTC", "4h")
        assert len(df) == 250


# ─── Cache ────────────────────────────────────────────────────────────────────

class TestCache:
    def test_second_call_uses_cache(self):
        from crypto_advisor.data.binance import BinanceClient
        client = BinanceClient(cache_ttl_seconds=3600)
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())) as mock_get:
            client.get_ohlcv("BTC", "4h")
            client.get_ohlcv("BTC", "4h")
        assert mock_get.call_count == 1

    def test_cache_expired_refetches(self):
        from crypto_advisor.data.binance import BinanceClient
        client = BinanceClient(cache_ttl_seconds=0)  # instant expiry
        with patch.object(client._http, "get", return_value=_mock_response(_make_klines())) as mock_get:
            client.get_ohlcv("BTC", "4h")
            client.get_ohlcv("BTC", "4h")
        assert mock_get.call_count == 2


# ─── Error handling ───────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_timeout_raises(self):
        client = _make_client()
        with patch.object(client._http, "get", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(httpx.TimeoutException):
                client.get_ohlcv("BTC", "4h")

    def test_500_raises_http_error(self):
        client = _make_client()
        with patch.object(client._http, "get", return_value=_mock_response({}, 500)):
            with pytest.raises(httpx.HTTPStatusError):
                client.get_ohlcv("BTC", "4h")
