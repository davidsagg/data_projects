"""
Tests for the AssetSelector module (US-007).

Covers:
- Anchors (BTC/ETH/SOL) always included regardless of ranking
- Stablecoins excluded
- Low-volume assets excluded (< $10M/day)
- max_dynamic cap respected
- MB availability flag set correctly
- Output sorted: anchors first, then by market_cap_rank
- Portfolio symbols annotated as already_held
"""

import pytest
from unittest.mock import MagicMock, patch


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_market(symbol, rank, price=100.0, volume=50_000_000.0, change=1.0):
    from crypto_advisor.models import MarketData
    return MarketData(
        symbol=symbol, price_usd=price, price_brl=price * 5,
        change_24h_pct=change, volume_24h_usd=volume,
        market_cap_usd=1e12 / rank, market_cap_rank=rank,
    )


TOP_20_MARKETS = [
    _make_market("BTC",   1, 80_000,  28_000_000_000),
    _make_market("ETH",   2,  3_200,  12_000_000_000),
    _make_market("USDT",  3,      1,  50_000_000_000),  # stablecoin
    _make_market("BNB",   4,    600,   1_200_000_000),
    _make_market("SOL",   5,    170,   3_000_000_000),
    _make_market("USDC",  6,      1,  40_000_000_000),  # stablecoin
    _make_market("XRP",   7,   0.60,   2_000_000_000),
    _make_market("ADA",   8,   0.45,     500_000_000),
    _make_market("AVAX",  9,  35.0,    800_000_000),
    _make_market("DOT",  10,   8.0,    300_000_000),
    _make_market("MATIC",11,   0.9,    250_000_000),
    _make_market("LINK", 12,  15.0,    400_000_000),
    _make_market("UNI",  13,   8.0,    200_000_000),
    _make_market("ATOM", 14,   9.0,    180_000_000),
    _make_market("LTC",  15,  75.0,    300_000_000),
    # Low volume — should be filtered
    _make_market("OBSCURE", 16, 0.01,    500_000),  # < $10M volume
]


def _make_selector(markets=None):
    from crypto_advisor.data.asset_selector import AssetSelector
    mock_cg = MagicMock()
    mock_cg.get_top_markets.return_value = markets or TOP_20_MARKETS
    return AssetSelector(mock_cg)


# ─── Anchors always included ──────────────────────────────────────────────────

class TestAnchors:
    def test_btc_always_included(self):
        selector = _make_selector()
        assets = selector.select_weekly_assets()
        assert any(a.symbol == "BTC" for a in assets)

    def test_eth_always_included(self):
        selector = _make_selector()
        assets = selector.select_weekly_assets()
        assert any(a.symbol == "ETH" for a in assets)

    def test_sol_always_included(self):
        selector = _make_selector()
        assets = selector.select_weekly_assets()
        assert any(a.symbol == "SOL" for a in assets)

    def test_anchor_flag_set(self):
        selector = _make_selector()
        assets = selector.select_weekly_assets()
        for a in assets:
            if a.symbol in ("BTC", "ETH", "SOL"):
                assert a.is_anchor is True

    def test_non_anchor_flag_not_set(self):
        selector = _make_selector()
        assets = selector.select_weekly_assets()
        for a in assets:
            if a.symbol not in ("BTC", "ETH", "SOL"):
                assert a.is_anchor is False


# ─── Stablecoins excluded ──────────────────────────────────────────────────────

class TestStablecoinsExcluded:
    def test_usdt_excluded(self):
        selector = _make_selector()
        symbols = {a.symbol for a in selector.select_weekly_assets()}
        assert "USDT" not in symbols

    def test_usdc_excluded(self):
        selector = _make_selector()
        symbols = {a.symbol for a in selector.select_weekly_assets()}
        assert "USDC" not in symbols

    @pytest.mark.parametrize("stable", ["DAI", "BUSD", "TUSD", "FRAX"])
    def test_known_stablecoins_excluded(self, stable):
        from crypto_advisor.data.asset_selector import STABLECOINS
        assert stable in STABLECOINS


# ─── Volume filter ────────────────────────────────────────────────────────────

class TestVolumeFilter:
    def test_low_volume_asset_excluded(self):
        selector = _make_selector()
        symbols = {a.symbol for a in selector.select_weekly_assets()}
        assert "OBSCURE" not in symbols

    def test_min_volume_threshold_is_10m(self):
        from crypto_advisor.data.asset_selector import MIN_VOLUME_USD
        assert MIN_VOLUME_USD == 10_000_000

    def test_asset_above_10m_volume_included(self):
        selector = _make_selector()
        symbols = {a.symbol for a in selector.select_weekly_assets()}
        assert "BNB" in symbols  # $1.2B volume


# ─── Dynamic cap ─────────────────────────────────────────────────────────────

class TestDynamicCap:
    def test_max_dynamic_respected(self):
        from crypto_advisor.data.asset_selector import AssetSelector
        mock_cg = MagicMock()
        mock_cg.get_top_markets.return_value = TOP_20_MARKETS
        selector = AssetSelector(mock_cg)
        assets = selector.select_weekly_assets(max_dynamic=3)
        non_anchors = [a for a in assets if not a.is_anchor]
        assert len(non_anchors) <= 3

    def test_total_assets_within_anchor_plus_max_dynamic(self):
        from crypto_advisor.data.asset_selector import AssetSelector
        mock_cg = MagicMock()
        mock_cg.get_top_markets.return_value = TOP_20_MARKETS
        selector = AssetSelector(mock_cg)
        max_d = 5
        assets = selector.select_weekly_assets(max_dynamic=max_d)
        assert len(assets) <= 3 + max_d  # 3 anchors + max_dynamic


# ─── MB availability ─────────────────────────────────────────────────────────

class TestMBAvailability:
    def test_btc_mb_available(self):
        selector = _make_selector()
        assets = selector.select_weekly_assets()
        btc = next(a for a in assets if a.symbol == "BTC")
        assert btc.mb_available is True

    def test_mb_available_flag_is_boolean(self):
        selector = _make_selector()
        for asset in selector.select_weekly_assets():
            assert isinstance(asset.mb_available, bool)


# ─── Sort order ──────────────────────────────────────────────────────────────

class TestSortOrder:
    def test_anchors_appear_before_dynamic(self):
        selector = _make_selector()
        assets = selector.select_weekly_assets()
        anchor_indices = [i for i, a in enumerate(assets) if a.is_anchor]
        dynamic_indices = [i for i, a in enumerate(assets) if not a.is_anchor]
        if anchor_indices and dynamic_indices:
            assert max(anchor_indices) < min(dynamic_indices)

    def test_dynamic_sorted_by_market_cap_rank(self):
        selector = _make_selector()
        dynamics = [a for a in selector.select_weekly_assets() if not a.is_anchor]
        ranks = [a.market_cap_rank for a in dynamics]
        assert ranks == sorted(ranks)


# ─── Portfolio annotation ─────────────────────────────────────────────────────

class TestPortfolioAnnotation:
    def test_already_held_flag_set_for_portfolio_symbols(self):
        selector = _make_selector()
        assets = selector.select_weekly_assets(portfolio_symbols={"BTC", "ETH"})
        btc = next(a for a in assets if a.symbol == "BTC")
        eth = next(a for a in assets if a.symbol == "ETH")
        assert btc.already_held is True
        assert eth.already_held is True

    def test_not_held_symbols_flagged_false(self):
        selector = _make_selector()
        assets = selector.select_weekly_assets(portfolio_symbols={"BTC"})
        bnb = next((a for a in assets if a.symbol == "BNB"), None)
        if bnb:
            assert bnb.already_held is False
