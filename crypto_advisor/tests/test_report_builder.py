"""
Tests for the Report Builder (Jinja2 HTML + Telegram summary).

Jinja2 is available in this environment; all tests run without mocks.

Covers:
- Template renders without exception with full data
- Template renders with minimal data (no portfolio, no tax context)
- Key HTML sections present in output
- Telegram summary format and 4096-char truncation
- Report saved to correct path with correct filename
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_report_data():
    from crypto_advisor.models import (
        PortfolioPosition, MarketData, TechnicalSnapshot,
        TaxContext, FearGreedData, RecommendationOutput,
    )
    from crypto_advisor.reporting.report import ReportData

    return ReportData(
        week_date="2026-05-12",
        portfolio=[
            PortfolioPosition(symbol="BTC", quantity=0.05, avg_price_brl=320_000.0),
            PortfolioPosition(symbol="ETH", quantity=1.2, avg_price_brl=18_000.0),
        ],
        portfolio_total_brl=35_200.0,
        portfolio_pnl_brl=500.0,
        recommendations=[
            RecommendationOutput(
                symbol="BTC", action="BUY",
                entry_price_usd=65_000.0, stop_loss_usd=62_000.0,
                target_price_usd=71_000.0, risk_reward_ratio=2.0,
                confidence="high",
                reasoning="Rompimento de MM200 com volume acima da média.",
                tax_impact="",
            ),
            RecommendationOutput(
                symbol="ETH", action="HOLD",
                confidence="medium",
                reasoning="Setup ainda válido; aguardar rompimento de $3.500.",
                tax_impact="",
            ),
            RecommendationOutput(
                symbol="SOL", action="SELL",
                entry_price_usd=170.0, stop_loss_usd=185.0,
                target_price_usd=145.0, risk_reward_ratio=1.7,
                confidence="low",
                reasoning="Perda de suporte; candidato a loss harvest.",
                tax_impact="Venda de R$1.700 dentro da margem mensal (R$12.400/R$35.000).",
            ),
        ],
        market_summary="Mercado em tendência de alta com Fear & Greed em 72.",
        fear_greed=FearGreedData(
            value=72, classification="Greed",
            timestamp=datetime(2026, 5, 12, 18, 0, 0, tzinfo=timezone.utc),
        ),
        tax_context=TaxContext(
            zone="safe", total_sold_brl=12_400.0, limit_brl=35_000.0,
            margin_available_brl=22_600.0,
            instruction="Operar normalmente.",
            loss_harvest_candidates=["SOL"],
        ),
        top_markets=[
            MarketData(symbol="BTC", price_usd=65_000.0, change_24h_pct=2.3,
                       volume_24h_usd=28e9, market_cap_usd=1.2e12, market_cap_rank=1),
        ],
    )


# ─── Template rendering ───────────────────────────────────────────────────────

class TestTemplateRendering:
    def test_renders_without_exception(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        data = _make_report_data()
        html = builder.build_html(data)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_output_is_valid_html(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        html = builder.build_html(_make_report_data())
        assert "<html" in html.lower() or "<!doctype" in html.lower()

    def test_week_date_present_in_output(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        html = builder.build_html(_make_report_data())
        assert "2026-05-12" in html

    def test_all_symbols_present(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        html = builder.build_html(_make_report_data())
        assert "BTC" in html
        assert "ETH" in html
        assert "SOL" in html

    def test_all_actions_present(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        html = builder.build_html(_make_report_data())
        assert "COMPRA" in html
        assert "MANTER" in html
        assert "VENDA" in html

    def test_tax_status_present(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        html = builder.build_html(_make_report_data())
        assert "35.000" in html or "35000" in html or "SAFE" in html.upper()

    def test_fear_greed_present(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        html = builder.build_html(_make_report_data())
        assert "72" in html
        assert "Greed" in html

    def test_renders_with_empty_portfolio(self):
        from crypto_advisor.reporting.report import ReportBuilder, ReportData
        builder = ReportBuilder()
        data = _make_report_data()
        data.portfolio = []
        data.portfolio_total_brl = 0.0
        data.portfolio_pnl_brl = 0.0
        html = builder.build_html(data)
        assert isinstance(html, str)

    def test_renders_with_no_tax_context(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        data = _make_report_data()
        data.tax_context = None
        html = builder.build_html(data)
        assert isinstance(html, str)

    def test_renders_with_empty_recommendations(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        data = _make_report_data()
        data.recommendations = []
        html = builder.build_html(data)
        assert isinstance(html, str)


# ─── File save ────────────────────────────────────────────────────────────────

class TestReportSave:
    def test_save_creates_file(self, tmp_path):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        data = _make_report_data()
        html = builder.build_html(data)
        saved_path = builder.save(html, data.week_date, output_dir=tmp_path)
        assert saved_path.exists()

    def test_saved_filename_contains_week_date(self, tmp_path):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        data = _make_report_data()
        html = builder.build_html(data)
        saved_path = builder.save(html, data.week_date, output_dir=tmp_path)
        assert "2026-05-12" in saved_path.name

    def test_saved_file_has_html_extension(self, tmp_path):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        data = _make_report_data()
        html = builder.build_html(data)
        saved_path = builder.save(html, data.week_date, output_dir=tmp_path)
        assert saved_path.suffix == ".html"

    def test_saved_content_matches_rendered(self, tmp_path):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        data = _make_report_data()
        html = builder.build_html(data)
        saved_path = builder.save(html, data.week_date, output_dir=tmp_path)
        assert saved_path.read_text(encoding="utf-8") == html


# ─── Telegram summary ─────────────────────────────────────────────────────────

class TestTelegramSummary:
    def test_returns_string(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        summary = builder.build_telegram_summary(_make_report_data())
        assert isinstance(summary, str)

    def test_summary_within_telegram_limit(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        summary = builder.build_telegram_summary(_make_report_data())
        assert len(summary) <= 4096

    def test_summary_contains_week_date(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        summary = builder.build_telegram_summary(_make_report_data())
        assert "2026-05-12" in summary or "12/05/2026" in summary

    def test_summary_contains_recommendations(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        summary = builder.build_telegram_summary(_make_report_data())
        assert "BTC" in summary
        assert "BUY" in summary or "COMPRAR" in summary

    def test_summary_contains_tax_status(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        summary = builder.build_telegram_summary(_make_report_data())
        assert "35" in summary  # R$35.000 or 35%

    def test_long_summary_truncated_to_4096(self):
        from crypto_advisor.reporting.report import ReportBuilder, ReportData
        from crypto_advisor.models import RecommendationOutput
        builder = ReportBuilder()
        data = _make_report_data()
        # Add many recommendations to force truncation
        data.recommendations = [
            RecommendationOutput(
                symbol=f"TOKEN{i:03d}", action="SKIP",
                confidence="low",
                reasoning="x" * 500,
                tax_impact="",
            )
            for i in range(30)
        ]
        summary = builder.build_telegram_summary(data)
        assert len(summary) <= 4096
