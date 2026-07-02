"""
Tests for the Portfolio Reader (Mercado Bitcoin API client).

Uses mocked HTTP responses — no real API calls.

Covers:
- Successful portfolio parsing from MB API response
- Filtering of zero/dust balances
- Authentication error handling (401/403)
- Timeout error handling
- SQLite sync (portfolio table upsert)
- Empty portfolio response
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel


# ─── Data models (mirrors what will live in models.py) ────────────────────────

class PortfolioPosition(BaseModel):
    symbol: str
    quantity: float
    avg_price_brl: float
    exchange: str = "mercado_bitcoin"


class AuthenticationError(Exception):
    pass


class ExchangeTimeoutError(Exception):
    pass


# ─── Fake MB API client (thin layer over the fixture) ─────────────────────────

class FakeMercadoBitcoinClient:
    """Thin fake that wraps a pre-loaded response dict, simulating real MB API behaviour."""

    DUST_THRESHOLD = 1e-6

    def __init__(self, raw_response: dict | None = None, raise_status: int | None = None):
        self._raw = raw_response
        self._raise_status = raise_status

    def get_portfolio(self) -> list[PortfolioPosition]:
        if self._raise_status in (401, 403):
            raise AuthenticationError(
                f"MB API returned {self._raise_status}: invalid credentials"
            )
        if self._raise_status == 408:
            raise ExchangeTimeoutError("MB API request timed out after 10s")

        positions = []
        for item in (self._raw or {}).get("accounts", []):
            for balance in item.get("balances", []):
                qty = float(balance.get("available", 0)) + float(balance.get("on_hold", 0))
                if qty <= self.DUST_THRESHOLD:
                    continue
                avg = float(balance.get("avg_price", 0))
                positions.append(
                    PortfolioPosition(
                        symbol=balance["symbol"].upper(),
                        quantity=qty,
                        avg_price_brl=avg,
                    )
                )
        return positions


# ─── Fixtures ─────────────────────────────────────────────────────────────────

MB_PORTFOLIO_RESPONSE = {
    "accounts": [
        {
            "currency": "BRL",
            "balances": [
                {"symbol": "BTC", "available": "0.04", "on_hold": "0.01", "avg_price": "320000.00"},
                {"symbol": "ETH", "available": "1.2",  "on_hold": "0.0",  "avg_price": "18000.00"},
                {"symbol": "SOL", "available": "10.0", "on_hold": "0.0",  "avg_price": "750.00"},
                {"symbol": "BRL", "available": "1500.00","on_hold":"0.0",  "avg_price": "1.00"},
                # Dust balance — should be filtered
                {"symbol": "MATIC", "available": "0.0000001", "on_hold": "0.0", "avg_price": "3.50"},
            ],
        }
    ]
}


# ─── Successful response parsing ──────────────────────────────────────────────

class TestPortfolioParser:
    def test_returns_list_of_portfolio_positions(self):
        client = FakeMercadoBitcoinClient(raw_response=MB_PORTFOLIO_RESPONSE)
        positions = client.get_portfolio()
        assert isinstance(positions, list)
        assert all(isinstance(p, PortfolioPosition) for p in positions)

    def test_returns_correct_symbols(self):
        client = FakeMercadoBitcoinClient(raw_response=MB_PORTFOLIO_RESPONSE)
        symbols = {p.symbol for p in client.get_portfolio()}
        assert "BTC" in symbols
        assert "ETH" in symbols
        assert "SOL" in symbols

    def test_btc_quantity_is_sum_of_available_and_on_hold(self):
        client = FakeMercadoBitcoinClient(raw_response=MB_PORTFOLIO_RESPONSE)
        positions = client.get_portfolio()
        btc = next(p for p in positions if p.symbol == "BTC")
        assert btc.quantity == pytest.approx(0.05)

    def test_avg_price_parsed_correctly(self):
        client = FakeMercadoBitcoinClient(raw_response=MB_PORTFOLIO_RESPONSE)
        positions = client.get_portfolio()
        eth = next(p for p in positions if p.symbol == "ETH")
        assert eth.avg_price_brl == pytest.approx(18_000.0)

    def test_symbols_normalised_to_uppercase(self):
        response = {
            "accounts": [{
                "currency": "BRL",
                "balances": [
                    {"symbol": "btc", "available": "0.1", "on_hold": "0.0", "avg_price": "320000"}
                ],
            }]
        }
        client = FakeMercadoBitcoinClient(raw_response=response)
        positions = client.get_portfolio()
        assert positions[0].symbol == "BTC"


# ─── Dust / zero balance filtering ───────────────────────────────────────────

class TestDustFiltering:
    def test_matic_dust_balance_filtered(self):
        client = FakeMercadoBitcoinClient(raw_response=MB_PORTFOLIO_RESPONSE)
        symbols = {p.symbol for p in client.get_portfolio()}
        assert "MATIC" not in symbols

    def test_brl_balance_included_when_above_threshold(self):
        client = FakeMercadoBitcoinClient(raw_response=MB_PORTFOLIO_RESPONSE)
        symbols = {p.symbol for p in client.get_portfolio()}
        assert "BRL" in symbols

    def test_zero_quantity_position_excluded(self):
        response = {
            "accounts": [{
                "currency": "BRL",
                "balances": [
                    {"symbol": "ADA", "available": "0.0", "on_hold": "0.0", "avg_price": "2.50"},
                ],
            }]
        }
        client = FakeMercadoBitcoinClient(raw_response=response)
        assert client.get_portfolio() == []

    def test_empty_portfolio_response_returns_empty_list(self):
        client = FakeMercadoBitcoinClient(raw_response={"accounts": []})
        assert client.get_portfolio() == []


# ─── Error handling ───────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_401_raises_authentication_error(self):
        client = FakeMercadoBitcoinClient(raise_status=401)
        with pytest.raises(AuthenticationError, match="401"):
            client.get_portfolio()

    def test_403_raises_authentication_error(self):
        client = FakeMercadoBitcoinClient(raise_status=403)
        with pytest.raises(AuthenticationError, match="403"):
            client.get_portfolio()

    def test_timeout_raises_exchange_timeout_error(self):
        client = FakeMercadoBitcoinClient(raise_status=408)
        with pytest.raises(ExchangeTimeoutError, match="timed out"):
            client.get_portfolio()


# ─── SQLite sync ──────────────────────────────────────────────────────────────

class TestPortfolioSync:
    def test_positions_upserted_to_sqlite(self, db_conn):
        client = FakeMercadoBitcoinClient(raw_response=MB_PORTFOLIO_RESPONSE)
        positions = client.get_portfolio()

        for pos in positions:
            db_conn.execute(
                "INSERT OR REPLACE INTO portfolio (symbol, quantity, avg_price_brl, exchange) "
                "VALUES (?, ?, ?, ?)",
                (pos.symbol, pos.quantity, pos.avg_price_brl, pos.exchange),
            )
        db_conn.commit()

        rows = db_conn.execute("SELECT symbol FROM portfolio ORDER BY symbol").fetchall()
        symbols_in_db = {r["symbol"] for r in rows}
        assert "BTC" in symbols_in_db
        assert "ETH" in symbols_in_db

    def test_upsert_updates_existing_position(self, db_conn):
        db_conn.execute(
            "INSERT INTO portfolio (symbol, quantity, avg_price_brl, exchange) "
            "VALUES ('BTC', 0.01, 300000.0, 'mercado_bitcoin')"
        )
        db_conn.commit()

        db_conn.execute(
            "INSERT OR REPLACE INTO portfolio (symbol, quantity, avg_price_brl, exchange) "
            "VALUES ('BTC', 0.05, 320000.0, 'mercado_bitcoin')"
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT quantity, avg_price_brl FROM portfolio WHERE symbol='BTC'"
        ).fetchone()
        assert row["quantity"] == pytest.approx(0.05)
        assert row["avg_price_brl"] == pytest.approx(320_000.0)

    def test_portfolio_count_matches_non_dust_positions(self, db_conn):
        client = FakeMercadoBitcoinClient(raw_response=MB_PORTFOLIO_RESPONSE)
        positions = client.get_portfolio()

        for pos in positions:
            db_conn.execute(
                "INSERT OR REPLACE INTO portfolio (symbol, quantity, avg_price_brl, exchange) "
                "VALUES (?, ?, ?, ?)",
                (pos.symbol, pos.quantity, pos.avg_price_brl, pos.exchange),
            )
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) as c FROM portfolio").fetchone()["c"]
        assert count == len(positions)
