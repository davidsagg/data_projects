"""
Tests for the prompt builder (US-015).

Covers:
- All required sections present in the assembled prompt
- Market section token count stays under 4000 tokens
- Graceful truncation when context is large (many assets)
- Tax context injected correctly for each zone
- Empty/None fields handled gracefully
"""

import pytest
from datetime import datetime, timezone


def _make_full_context():
    from crypto_advisor.models import (
        AdvisorContext, PortfolioPosition, MarketData, TechnicalSnapshot,
        FearGreedData, TaxContext,
    )
    portfolio = [
        PortfolioPosition(symbol="BTC", quantity=0.05, avg_price_brl=320_000),
        PortfolioPosition(symbol="ETH", quantity=1.2,  avg_price_brl=18_000),
    ]
    market_data = {
        "BTC": MarketData(symbol="BTC", price_usd=80_000, price_brl=400_000,
                          change_24h_pct=2.3, volume_24h_usd=28e9,
                          market_cap_usd=1.2e12, market_cap_rank=1),
        "ETH": MarketData(symbol="ETH", price_usd=3_200, price_brl=16_000,
                          change_24h_pct=1.1, volume_24h_usd=12e9,
                          market_cap_usd=380e9, market_cap_rank=2),
    }
    snap = TechnicalSnapshot(
        symbol="BTC", timeframe="4h",
        sma_9=79_000, sma_21=77_000, sma_200=None,
        rsi_14=58.6, macd=125.0, macd_signal=80.0, macd_hist=45.0,
        bb_upper=82_000, bb_middle=79_000, bb_lower=76_000,
        mm_alignment="bullish", rsi_zone="neutral",
        macd_crossover="none", bb_position="inside",
    )
    return AdvisorContext(
        portfolio=portfolio,
        market_data=market_data,
        technical_4h={"BTC": snap},
        technical_1d={"BTC": snap},
        fear_greed=FearGreedData(
            value=49, classification="Neutral",
            timestamp=datetime(2026, 5, 12, 18, 0, tzinfo=timezone.utc),
        ),
        tax_context=TaxContext(
            zone="safe", total_sold_brl=12_400, limit_brl=35_000,
            margin_available_brl=22_600, instruction="Operar normalmente.",
        ),
        top_markets=[
            MarketData(symbol="BTC", price_usd=80_000, price_brl=400_000,
                       change_24h_pct=2.3, volume_24h_usd=28e9,
                       market_cap_usd=1.2e12, market_cap_rank=1),
        ],
        week_date="2026-05-12",
    )


# ─── Required sections ────────────────────────────────────────────────────────

class TestRequiredSections:
    def test_portfolio_section_present(self):
        from crypto_advisor.advisor import build_user_prompt
        prompt = build_user_prompt(_make_full_context())
        assert "PORTF" in prompt.upper()  # matches PORTFOLIO or PORTFÓLIO

    def test_tax_section_present(self):
        from crypto_advisor.advisor import build_user_prompt
        prompt = build_user_prompt(_make_full_context())
        assert "TAX" in prompt.upper()

    def test_market_data_section_present(self):
        from crypto_advisor.advisor import build_user_prompt
        prompt = build_user_prompt(_make_full_context())
        assert "MARKET DATA" in prompt.upper() or "BTC" in prompt

    def test_technical_4h_section_present(self):
        from crypto_advisor.advisor import build_user_prompt
        prompt = build_user_prompt(_make_full_context())
        assert "4h" in prompt.lower() or "TÉCNICA" in prompt.upper()

    def test_fear_greed_section_present(self):
        from crypto_advisor.advisor import build_user_prompt
        prompt = build_user_prompt(_make_full_context())
        assert "FEAR" in prompt.upper() or "49" in prompt

    def test_instruction_section_present(self):
        from crypto_advisor.advisor import build_user_prompt
        prompt = build_user_prompt(_make_full_context())
        assert "INSTRUÇÃO" in prompt or "semana" in prompt.lower()

    def test_week_date_in_prompt(self):
        from crypto_advisor.advisor import build_user_prompt
        prompt = build_user_prompt(_make_full_context())
        assert "2026-05-12" in prompt


# ─── Token count ─────────────────────────────────────────────────────────────

class TestTokenCount:
    def test_market_section_under_4000_tokens(self):
        from crypto_advisor.advisor import build_user_prompt, estimate_tokens
        prompt = build_user_prompt(_make_full_context())
        assert estimate_tokens(prompt) < 4000

    def test_large_context_still_under_limit(self):
        from crypto_advisor.advisor import build_user_prompt, estimate_tokens
        from crypto_advisor.models import (
            AdvisorContext, MarketData, TechnicalSnapshot,
        )
        ctx = _make_full_context()
        # Add 20 assets with snapshots to simulate a full weekly run
        for i in range(20):
            sym = f"TOKEN{i:02d}"
            ctx.market_data[sym] = MarketData(
                symbol=sym, price_usd=1.0, price_brl=5.0,
                change_24h_pct=0.5, volume_24h_usd=50e6,
                market_cap_usd=1e9, market_cap_rank=20 + i,
            )
            ctx.technical_4h[sym] = TechnicalSnapshot(
                symbol=sym, timeframe="4h",
                sma_9=1.0, sma_21=0.95, sma_200=None,
                rsi_14=50.0, macd=0.01, macd_signal=0.008, macd_hist=0.002,
                bb_upper=1.05, bb_middle=1.0, bb_lower=0.95,
                mm_alignment="mixed", rsi_zone="neutral",
                macd_crossover="none", bb_position="inside",
            )
        prompt = build_user_prompt(ctx)
        assert estimate_tokens(prompt) < 4000

    def test_estimate_tokens_returns_int(self):
        from crypto_advisor.advisor import estimate_tokens
        assert isinstance(estimate_tokens("hello world"), int)

    def test_estimate_tokens_scales_with_length(self):
        from crypto_advisor.advisor import estimate_tokens
        short = estimate_tokens("hello")
        long  = estimate_tokens("hello " * 100)
        assert long > short


# ─── Tax zone injection ───────────────────────────────────────────────────────

class TestTaxZoneInjection:
    @pytest.mark.parametrize("zone,keyword", [
        ("safe",     "SAFE"),
        ("warning",  "WARNING"),
        ("critical", "CRITICAL"),
        ("blocked",  "BLOCKED"),
    ])
    def test_zone_label_in_prompt(self, zone, keyword):
        from crypto_advisor.advisor import build_user_prompt
        from crypto_advisor.models import TaxContext
        ctx = _make_full_context()
        ctx.tax_context = TaxContext(
            zone=zone, total_sold_brl=10_000, limit_brl=35_000,
            margin_available_brl=25_000,
            instruction=f"Instrução para {zone}.",
        )
        prompt = build_user_prompt(ctx)
        assert keyword in prompt.upper()

    def test_loss_harvest_candidates_in_prompt(self):
        from crypto_advisor.advisor import build_user_prompt
        from crypto_advisor.models import TaxContext
        ctx = _make_full_context()
        ctx.tax_context = TaxContext(
            zone="warning", total_sold_brl=29_000, limit_brl=35_000,
            margin_available_brl=6_000, instruction="Priorize loss harvesting.",
            loss_harvest_candidates=["SOL", "MATIC"],
        )
        prompt = build_user_prompt(ctx)
        assert "SOL" in prompt or "harvest" in prompt.lower()


# ─── Empty/None handling ──────────────────────────────────────────────────────

class TestEdgeCases:
    def test_renders_without_portfolio(self):
        from crypto_advisor.advisor import build_user_prompt
        ctx = _make_full_context()
        ctx.portfolio = []
        prompt = build_user_prompt(ctx)
        assert isinstance(prompt, str)

    def test_renders_without_tax_context(self):
        from crypto_advisor.advisor import build_user_prompt
        ctx = _make_full_context()
        ctx.tax_context = None
        prompt = build_user_prompt(ctx)
        assert isinstance(prompt, str)

    def test_renders_without_fear_greed(self):
        from crypto_advisor.advisor import build_user_prompt
        ctx = _make_full_context()
        ctx.fear_greed = None
        prompt = build_user_prompt(ctx)
        assert isinstance(prompt, str)

    def test_renders_without_indicators(self):
        from crypto_advisor.advisor import build_user_prompt
        ctx = _make_full_context()
        ctx.technical_4h = {}
        ctx.technical_1d = {}
        prompt = build_user_prompt(ctx)
        assert isinstance(prompt, str)
