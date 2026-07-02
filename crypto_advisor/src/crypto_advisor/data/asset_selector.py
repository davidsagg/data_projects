"""Dynamic asset selection for weekly analysis (US-007).

Anchors (BTC, ETH, SOL) are always included.
Dynamic slots are filled with top-N CoinGecko coins filtered by:
  - Not a stablecoin
  - 24h volume >= $10M (MIN_VOLUME_USD)
  - Up to max_dynamic coins beyond the anchors
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .coingecko import CoinGeckoClient

ANCHOR_SYMBOLS: frozenset[str] = frozenset({"BTC", "ETH", "SOL"})

STABLECOINS: frozenset[str] = frozenset({
    "USDT", "USDC", "DAI", "BUSD", "TUSD", "USDP", "GUSD",
    "FRAX", "LUSD", "USDD", "PYUSD", "CRVUSD", "USDE", "FDUSD",
})

# Symbols with confirmed BRL pairs on Mercado Bitcoin (as of 2026-05)
MB_PAIRS: frozenset[str] = frozenset({
    "BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "AVAX", "DOT",
    "MATIC", "LINK", "UNI", "LTC", "BCH", "NEAR", "ATOM",
    "ARB", "OP", "APT", "INJ", "SUI", "AAVE", "COMP", "MKR",
    "SNX", "CRV", "SAND", "MANA", "AXS", "CHZ", "ENJ", "GALA",
    "1INCH", "DYDX", "LDO", "BLUR", "ARB", "WLD",
})

MIN_VOLUME_USD: float = 10_000_000.0


@dataclass
class SelectedAsset:
    symbol: str
    market_cap_rank: int
    price_usd: float
    volume_24h_usd: float
    change_24h_pct: float
    is_anchor: bool
    mb_available: bool
    already_held: bool = False


class AssetSelector:
    """Selects the weekly asset universe from CoinGecko top markets."""

    def __init__(self, coingecko_client: CoinGeckoClient) -> None:
        self._cg = coingecko_client

    def select_weekly_assets(
        self,
        portfolio_symbols: set[str] | None = None,
        top_n: int = 20,
        max_dynamic: int = 7,
    ) -> list[SelectedAsset]:
        """Return ordered list of assets to analyse this week.

        Order: anchors first (sorted by rank), then dynamic by rank.
        """
        held = portfolio_symbols or set()
        markets = self._cg.get_top_markets(limit=top_n + 10)

        anchors: list[SelectedAsset] = []
        dynamics: list[SelectedAsset] = []
        anchor_found: set[str] = set()

        for market in markets:
            sym = market.symbol
            if sym.upper() in STABLECOINS:
                continue

            is_anchor = sym in ANCHOR_SYMBOLS
            has_volume = market.volume_24h_usd >= MIN_VOLUME_USD

            if not is_anchor and not has_volume:
                continue
            if not is_anchor and len(dynamics) >= max_dynamic:
                continue

            asset = SelectedAsset(
                symbol=sym,
                market_cap_rank=market.market_cap_rank or 999,
                price_usd=market.price_usd,
                volume_24h_usd=market.volume_24h_usd,
                change_24h_pct=market.change_24h_pct,
                is_anchor=is_anchor,
                mb_available=sym in MB_PAIRS,
                already_held=sym in held,
            )

            if is_anchor:
                anchors.append(asset)
                anchor_found.add(sym)
            else:
                dynamics.append(asset)

        # Guarantee missing anchors are included even if outside top_n
        for sym in ANCHOR_SYMBOLS - anchor_found:
            market = next((m for m in markets if m.symbol == sym), None)
            if market:
                anchors.append(SelectedAsset(
                    symbol=sym,
                    market_cap_rank=market.market_cap_rank or 0,
                    price_usd=market.price_usd,
                    volume_24h_usd=market.volume_24h_usd,
                    change_24h_pct=market.change_24h_pct,
                    is_anchor=True,
                    mb_available=sym in MB_PAIRS,
                    already_held=sym in held,
                ))

        anchors.sort(key=lambda a: a.market_cap_rank)
        dynamics.sort(key=lambda a: a.market_cap_rank)

        return anchors + dynamics
