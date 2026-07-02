"""
Tests for the Mercado Bitcoin API client.

All HTTP calls are mocked — no real network access required.

Covers:
- OAuth2 token acquisition and auto-refresh
- get_portfolio: parsing, dust filter, upsert to SQLite
- get_trade_history: parsing filled orders, incremental import
- Authentication errors (401/403)
- Token expiry and refresh
- TAPI HMAC-SHA512 signature generation
"""

import time
import pytest
import httpx
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone


# ─── Fixtures: raw MB API responses ───────────────────────────────────────────

MB_AUTH_RESPONSE = {
    "access_token": "test_jwt_token_abc123",
    "expiration": int(time.time()) + 3600,
    "token_type": "Bearer",
}

MB_ACCOUNTS_RESPONSE = [
    {"id": "88776655", "name": "Conta Principal", "currency": "BRL", "type": "exchange"},
]

MB_BALANCES_RESPONSE = [
    {"symbol": "BTC", "available": "0.04000000", "on_hold": "0.01000000", "total": "0.05000000"},
    {"symbol": "ETH", "available": "1.20000000", "on_hold": "0.00000000", "total": "1.20000000"},
    {"symbol": "SOL", "available": "10.00000000","on_hold": "0.00000000", "total": "10.00000000"},
    {"symbol": "BRL", "available": "1500.00",    "on_hold": "0.00",       "total": "1500.00"},
    # Dust — must be filtered
    {"symbol": "MATIC","available": "0.00000010", "on_hold": "0.00000000","total": "0.00000010"},
]

MB_ORDERS_RESPONSE = {
    "orders": [
        {
            "orderId": "1001",
            "symbol": "BTC-BRL",
            "side": "sell",
            "qty": "0.01000000",
            "price": "320000.00",
            "executedQty": "0.01000000",
            "executedPrice": "321000.00",
            "fee": "9.63",
            "created_at": "2026-05-03T14:00:00Z",
            "updated_at": "2026-05-03T14:00:01Z",
            "status": "fully_filled",
        },
        {
            "orderId": "1002",
            "symbol": "ETH-BRL",
            "side": "buy",
            "qty": "0.50000000",
            "price": "17800.00",
            "executedQty": "0.50000000",
            "executedPrice": "17800.00",
            "fee": "4.45",
            "created_at": "2026-05-05T10:30:00Z",
            "updated_at": "2026-05-05T10:30:02Z",
            "status": "fully_filled",
        },
    ],
    "pagination": {"page": 1, "page_size": 100, "total": 2},
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


def _make_client():
    from crypto_advisor.data.mercado_bitcoin import MercadoBitcoinClient
    return MercadoBitcoinClient(
        api_id="test_api_id",
        api_secret="test_api_secret",
        tapi_id="test_tapi_id",
        tapi_secret="test_tapi_secret",
    )


# ─── Authentication ───────────────────────────────────────────────────────────

class TestAuthentication:
    def test_get_token_calls_authorize_endpoint(self):
        client = _make_client()
        with patch.object(client._http, "post", return_value=_mock_response(MB_AUTH_RESPONSE)) as mock_post:
            token = client._get_token()
        assert token == "test_jwt_token_abc123"
        assert "authorize" in mock_post.call_args[0][0]

    def test_token_cached_on_second_call(self):
        client = _make_client()
        with patch.object(client._http, "post", return_value=_mock_response(MB_AUTH_RESPONSE)) as mock_post:
            client._get_token()
            client._get_token()
        assert mock_post.call_count == 1

    def test_expired_token_triggers_refresh(self):
        client = _make_client()
        client._token = "old_token"
        client._token_expires = time.time() - 10  # already expired

        with patch.object(client._http, "post", return_value=_mock_response(MB_AUTH_RESPONSE)) as mock_post:
            token = client._get_token()
        assert mock_post.call_count == 1
        assert token == "test_jwt_token_abc123"

    def test_401_raises_authentication_error(self):
        from crypto_advisor.data.mercado_bitcoin import AuthenticationError
        client = _make_client()
        with patch.object(client._http, "post", return_value=_mock_response({}, 401)):
            with pytest.raises(AuthenticationError, match="API ID"):
                client._get_token()

    def test_auth_header_contains_bearer_token(self):
        client = _make_client()
        client._token = "my_token"
        client._token_expires = time.time() + 3600
        headers = client._auth_headers()
        assert headers["Authorization"] == "Bearer my_token"


# ─── get_portfolio ─────────────────────────────────────────────────────────────

class TestGetPortfolio:
    def _setup(self, client):
        """Patch the three sequential API calls: authorize → accounts → balances."""
        client._token = "test_jwt_token_abc123"
        client._token_expires = time.time() + 3600

        def _get_side_effect(url, **kwargs):
            if "/accounts" in url and "balances" not in url:
                return _mock_response(MB_ACCOUNTS_RESPONSE)
            if "balances" in url:
                return _mock_response(MB_BALANCES_RESPONSE)
            return _mock_response({}, 404)

        return patch.object(client._http, "get", side_effect=_get_side_effect)

    def test_returns_list_of_portfolio_positions(self):
        from crypto_advisor.models import PortfolioPosition
        client = _make_client()
        with self._setup(client):
            positions = client.get_portfolio()
        assert isinstance(positions, list)
        assert all(isinstance(p, PortfolioPosition) for p in positions)

    def test_btc_quantity_aggregated(self):
        client = _make_client()
        with self._setup(client):
            positions = client.get_portfolio()
        btc = next(p for p in positions if p.symbol == "BTC")
        assert btc.quantity == pytest.approx(0.05)

    def test_dust_balance_filtered(self):
        client = _make_client()
        with self._setup(client):
            positions = client.get_portfolio()
        symbols = {p.symbol for p in positions}
        assert "MATIC" not in symbols

    def test_brl_cash_included(self):
        client = _make_client()
        with self._setup(client):
            positions = client.get_portfolio()
        symbols = {p.symbol for p in positions}
        assert "BRL" in symbols

    def test_symbols_uppercase(self):
        client = _make_client()
        with self._setup(client):
            positions = client.get_portfolio()
        for p in positions:
            assert p.symbol == p.symbol.upper()

    def test_exchange_set_to_mercado_bitcoin(self):
        client = _make_client()
        with self._setup(client):
            positions = client.get_portfolio()
        for p in positions:
            assert p.exchange == "mercado_bitcoin"


# ─── get_trade_history ────────────────────────────────────────────────────────

class TestGetTradeHistory:
    def _setup(self, client):
        client._token = "test_jwt_token_abc123"
        client._token_expires = time.time() + 3600

        def _get_side_effect(url, **kwargs):
            # accounts list (no trailing /orders)
            if url.endswith("/accounts"):
                return _mock_response(MB_ACCOUNTS_RESPONSE)
            # account-scoped orders
            if "/orders" in url:
                return _mock_response(MB_ORDERS_RESPONSE)
            return _mock_response({}, 404)

        return patch.object(client._http, "get", side_effect=_get_side_effect)

    def test_returns_list_of_trade_records(self):
        from crypto_advisor.models import TradeRecord
        client = _make_client()
        with self._setup(client):
            trades = client.get_trade_history()
        assert isinstance(trades, list)
        assert all(isinstance(t, TradeRecord) for t in trades)

    def test_returns_both_buy_and_sell(self):
        client = _make_client()
        with self._setup(client):
            trades = client.get_trade_history()
        sides = {t.side for t in trades}
        assert "buy" in sides
        assert "sell" in sides

    def test_sell_total_calculated_correctly(self):
        client = _make_client()
        with self._setup(client):
            trades = client.get_trade_history()
        btc_sell = next(t for t in trades if t.symbol == "BTC" and t.side == "sell")
        # executedQty * executedPrice = 0.01 * 321000 = 3210.00
        assert btc_sell.total_brl == pytest.approx(3210.0)

    def test_fee_parsed(self):
        client = _make_client()
        with self._setup(client):
            trades = client.get_trade_history()
        btc_sell = next(t for t in trades if t.symbol == "BTC" and t.side == "sell")
        assert btc_sell.fee_brl == pytest.approx(9.63)

    def test_traded_at_is_datetime(self):
        client = _make_client()
        with self._setup(client):
            trades = client.get_trade_history()
        for t in trades:
            assert isinstance(t.traded_at, datetime)

    def test_only_fully_filled_orders_included(self):
        """Partial fills and cancelled orders must be excluded."""
        response_with_partial = {
            "orders": [
                *MB_ORDERS_RESPONSE["orders"],
                {
                    "orderId": "1003", "symbol": "SOL-BRL", "side": "buy",
                    "qty": "5.0", "price": "750.00", "executedQty": "2.0",
                    "executedPrice": "750.00", "fee": "0.75",
                    "created_at": "2026-05-06T08:00:00Z",
                    "updated_at": "2026-05-06T08:00:01Z",
                    "status": "partially_filled",
                },
            ],
            "pagination": {"page": 1, "page_size": 100, "total": 3},
        }
        client = _make_client()
        client._token = "test_jwt_token_abc123"
        client._token_expires = time.time() + 3600

        def _side(url, **kwargs):
            if url.endswith("/accounts"):
                return _mock_response(MB_ACCOUNTS_RESPONSE)
            return _mock_response(response_with_partial)

        with patch.object(client._http, "get", side_effect=_side):
            trades = client.get_trade_history()
        statuses_included = {t.symbol for t in trades}
        assert "SOL" not in statuses_included

    def test_since_date_passed_as_query_param(self):
        client = _make_client()
        client._token = "test_jwt_token_abc123"
        client._token_expires = time.time() + 3600
        since = datetime(2026, 5, 1, tzinfo=timezone.utc)

        calls = []
        def _side_effect(url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/accounts"):
                return _mock_response(MB_ACCOUNTS_RESPONSE)
            return _mock_response(MB_ORDERS_RESPONSE)

        with patch.object(client._http, "get", side_effect=_side_effect):
            client.get_trade_history(since_date=since)

        # find the orders call (not the accounts call)
        orders_calls = [(u, kw) for u, kw in calls if "/orders" in u]
        assert orders_calls, "No orders request was made"
        _, call_kw = orders_calls[0]
        params = call_kw.get("params", {})
        assert any("from" in str(k).lower() or "timestamp" in str(k).lower()
                   for k in params.keys()), \
            f"since_date not passed as param. Got params: {params}"


# ─── TAPI signature ───────────────────────────────────────────────────────────

class TestTAPISignature:
    def test_signature_is_hex_string(self):
        from crypto_advisor.data.mercado_bitcoin import _tapi_signature
        sig = _tapi_signature(
            tapi_secret="mysecret",
            tapi_path="/tapi/v3/",
            tapi_nonce="1234567890",
            params={"tapi_method": "list_orders", "coin_pair": "BRLBTC"},
        )
        assert isinstance(sig, str)
        assert len(sig) == 128  # SHA-512 hex = 128 chars

    def test_same_inputs_produce_same_signature(self):
        from crypto_advisor.data.mercado_bitcoin import _tapi_signature
        kwargs = dict(
            tapi_secret="mysecret", tapi_path="/tapi/v3/",
            tapi_nonce="111", params={"tapi_method": "list_orders"},
        )
        assert _tapi_signature(**kwargs) == _tapi_signature(**kwargs)

    def test_different_secrets_produce_different_signatures(self):
        from crypto_advisor.data.mercado_bitcoin import _tapi_signature
        base = dict(tapi_path="/tapi/v3/", tapi_nonce="111", params={})
        sig1 = _tapi_signature(tapi_secret="secret_a", **base)
        sig2 = _tapi_signature(tapi_secret="secret_b", **base)
        assert sig1 != sig2
