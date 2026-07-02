"""Mercado Bitcoin API client.

Implements two authentication layers:
- API v4 (REST/OAuth2): portfolio balances
- TAPI v3 (HMAC-SHA512): trade history
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from ..models import PortfolioPosition, TradeRecord

# ─── Constants ────────────────────────────────────────────────────────────────

MB_API_BASE = "https://api.mercadobitcoin.net/api/v4"
MB_TAPI_URL = "https://www.mercadobitcoin.com.br/tapi/v3/"
MB_TAPI_PATH = "/tapi/v3/"

DUST_THRESHOLD = 1e-6
FULLY_FILLED_STATUS = {"fully_filled", "filled", "3"}  # MB uses different formats


# ─── Custom exceptions ────────────────────────────────────────────────────────

class AuthenticationError(Exception):
    """Invalid API ID/Secret or TAPI credentials."""


class ExchangeTimeoutError(Exception):
    """MB API request timed out."""


# ─── TAPI signature (exported for unit testing) ───────────────────────────────

def _tapi_signature(
    tapi_secret: str,
    tapi_path: str,
    tapi_nonce: str,
    params: dict,
) -> str:
    """HMAC-SHA512 signature for TAPI requests."""
    param_str = urlencode({"tapi_nonce": tapi_nonce, **params})
    message = f"{tapi_path}?{param_str}"
    sig = hmac.new(
        tapi_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha512,
    )
    return sig.hexdigest()


# ─── Symbol helpers ───────────────────────────────────────────────────────────

def _symbol_from_pair(coin_pair: str) -> str:
    """Extract symbol from MB coin pair. 'BRLBTC' → 'BTC', 'BTC-BRL' → 'BTC'."""
    pair = coin_pair.replace("-", "").replace("_", "")
    if pair.startswith("BRL"):
        return pair[3:].upper()
    if pair.endswith("BRL"):
        return pair[:-3].upper()
    return pair.upper()


# ─── Client ───────────────────────────────────────────────────────────────────

class MercadoBitcoinClient:
    """Client for Mercado Bitcoin API v4 + TAPI v3."""

    def __init__(
        self,
        api_id: str,
        api_secret: str,
        tapi_id: str | None = None,
        tapi_secret: str | None = None,
    ) -> None:
        self._api_id = api_id
        self._api_secret = api_secret
        self._tapi_id = tapi_id
        self._tapi_secret = tapi_secret
        self._http = httpx.Client(timeout=30.0)
        self._token: str | None = None
        self._token_expires: float = 0.0

    # ── OAuth2 token (API v4) ─────────────────────────────────────────────────

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token

        try:
            resp = self._http.post(
                f"{MB_API_BASE}/authorize",
                json={"login": self._api_id, "password": self._api_secret},
            )
        except httpx.TimeoutException as exc:
            raise ExchangeTimeoutError("MB API authorize timed out") from exc

        if resp.status_code in (401, 403):
            raise AuthenticationError(
                f"MB API: invalid API ID or API Secret (HTTP {resp.status_code})"
            )
        resp.raise_for_status()

        data = resp.json()
        self._token = data["access_token"]
        self._token_expires = float(data.get("expiration", time.time() + 3600))
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_token()}"}

    # ── Portfolio (API v4) ────────────────────────────────────────────────────

    def get_portfolio(self) -> list[PortfolioPosition]:
        """Return current account balances, filtering dust (< 1e-6)."""
        headers = self._auth_headers()

        try:
            accounts_resp = self._http.get(f"{MB_API_BASE}/accounts", headers=headers)
        except httpx.TimeoutException as exc:
            raise ExchangeTimeoutError("MB API accounts request timed out") from exc
        accounts_resp.raise_for_status()
        accounts = accounts_resp.json()

        positions: list[PortfolioPosition] = []
        for account in accounts:
            account_id = account["id"]
            try:
                bal_resp = self._http.get(
                    f"{MB_API_BASE}/accounts/{account_id}/balances",
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                raise ExchangeTimeoutError(
                    f"MB API balances request timed out for account {account_id}"
                ) from exc
            bal_resp.raise_for_status()

            for balance in bal_resp.json():
                qty = (
                    float(balance.get("available", 0))
                    + float(balance.get("on_hold", 0))
                )
                if qty <= DUST_THRESHOLD:
                    continue
                positions.append(PortfolioPosition(
                    symbol=balance["symbol"].upper(),
                    quantity=qty,
                    avg_price_brl=float(balance.get("avg_price", 0.0)),
                    exchange="mercado_bitcoin",
                ))

        return positions

    # ── Account IDs (cached) ──────────────────────────────────────────────────

    def _get_account_ids(self) -> list[str]:
        headers = self._auth_headers()
        resp = self._http.get(f"{MB_API_BASE}/accounts", headers=headers)
        resp.raise_for_status()
        return [a["id"] for a in resp.json()]

    # ── Trade history (API v4 account-scoped orders) ──────────────────────────

    def get_trade_history(
        self,
        since_date: datetime | None = None,
        symbols: list[str] | None = None,
        page_size: int = 100,
    ) -> list[TradeRecord]:
        """Return fully-filled orders for all accounts.

        Tries the account-scoped endpoint first
        (GET /api/v4/accounts/{id}/orders); falls back to the TAPI if that
        also returns 404.
        """
        account_ids = self._get_account_ids()
        all_trades: list[TradeRecord] = []

        for account_id in account_ids:
            trades = self._fetch_orders_for_account(
                account_id, since_date, symbols, page_size
            )
            all_trades.extend(trades)

        return all_trades

    def _fetch_orders_for_account(
        self,
        account_id: str,
        since_date: datetime | None,
        symbols: list[str] | None,
        page_size: int,
    ) -> list[TradeRecord]:
        headers = self._auth_headers()
        params: dict[str, str | int] = {
            "status": "fully_filled",
            "page_size": page_size,
        }
        if since_date:
            params["from_timestamp"] = int(since_date.timestamp())

        trades: list[TradeRecord] = []
        page = 1

        while True:
            params["page"] = page
            try:
                resp = self._http.get(
                    f"{MB_API_BASE}/accounts/{account_id}/orders",
                    headers=headers,
                    params=params,
                )
            except httpx.TimeoutException as exc:
                raise ExchangeTimeoutError("MB API orders request timed out") from exc

            # 404 → endpoint not supported for this account type
            if resp.status_code == 404:
                return []

            resp.raise_for_status()
            data = resp.json()

            orders = data if isinstance(data, list) else data.get("orders", [])
            for order in orders:
                status_val = order.get("status", "")
                if str(status_val).lower() not in FULLY_FILLED_STATUS:
                    continue

                raw_symbol = order.get("symbol", order.get("coin_pair", ""))
                symbol = _symbol_from_pair(raw_symbol)
                if symbols and symbol not in symbols:
                    continue

                executed_qty = float(order.get("executedQty", order.get("qty", 0)))
                executed_price = float(order.get("executedPrice", order.get("price", 0)))
                total_brl = executed_qty * executed_price
                fee_brl = float(order.get("fee", 0))
                side_raw = order.get("side", "").lower()
                side = "buy" if "buy" in side_raw else "sell"

                created_at_str = order.get("created_at", order.get("updated_at", ""))
                if not created_at_str:
                    continue
                traded_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )

                trades.append(TradeRecord(
                    symbol=symbol,
                    side=side,  # type: ignore[arg-type]
                    quantity=executed_qty,
                    price_brl=executed_price,
                    total_brl=total_brl,
                    fee_brl=fee_brl,
                    exchange="mercado_bitcoin",
                    traded_at=traded_at,
                ))

            pagination = data.get("pagination", {}) if isinstance(data, dict) else {}
            total_pages = (pagination.get("total", 0) // page_size) + 1
            if page >= total_pages or len(orders) < page_size:
                break
            page += 1

        return trades

    # ── TAPI: trade history (fallback / older endpoint) ───────────────────────

    def get_trade_history_tapi(
        self,
        coin_pair: str = "BRLBTC",
        order_type: int = 1,
        since_timestamp: int | None = None,
    ) -> list[TradeRecord]:
        """Fetch filled orders via TAPI v3 (HMAC-SHA512 authenticated)."""
        if not self._tapi_id or not self._tapi_secret:
            raise AuthenticationError("TAPI credentials not configured (MB_TAPI_ID/MB_TAPI_SECRET)")

        nonce = str(int(time.time() * 1000))
        params: dict[str, str | int] = {
            "tapi_method": "list_orders",
            "coin_pair": coin_pair,
            "status_list": "[3]",   # 3 = fully filled
        }
        if since_timestamp:
            params["from_timestamp"] = since_timestamp

        signature = _tapi_signature(
            tapi_secret=self._tapi_secret,
            tapi_path=MB_TAPI_PATH,
            tapi_nonce=nonce,
            params=params,  # type: ignore[arg-type]
        )

        headers = {
            "TAPI-ID": self._tapi_id,
            "TAPI-MAC": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        body = urlencode({"tapi_nonce": nonce, **params})

        try:
            resp = self._http.post(MB_TAPI_URL, content=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ExchangeTimeoutError("MB TAPI request timed out") from exc

        if resp.status_code in (401, 403):
            raise AuthenticationError("MB TAPI: invalid TAPI-ID or TAPI-MAC signature")
        resp.raise_for_status()

        data = resp.json()
        symbol = _symbol_from_pair(coin_pair)
        trades: list[TradeRecord] = []

        for order in data.get("response_data", {}).get("orders", []):
            if str(order.get("status")) != "3":
                continue
            qty = float(order.get("executed_quantity", 0))
            price = float(order.get("executed_price_avg", order.get("limit_price", 0)))
            total = qty * price
            side = "buy" if order.get("order_type") == 1 else "sell"
            traded_at = datetime.fromtimestamp(
                int(order["updated_timestamp"]), tz=timezone.utc
            )
            trades.append(TradeRecord(
                symbol=symbol, side=side,  # type: ignore[arg-type]
                quantity=qty, price_brl=price, total_brl=total,
                fee_brl=float(order.get("fee", 0)),
                exchange="mercado_bitcoin", traded_at=traded_at,
            ))

        return trades

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "MercadoBitcoinClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
