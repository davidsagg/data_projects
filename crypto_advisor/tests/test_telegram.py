"""
Tests for the Telegram Notifier.

python-telegram-bot is not available in this env — all Bot calls are mocked.

Covers:
- send_weekly_report: calls Bot.send_message with correct params
- send_tax_alert: sends zone-specific alert message
- Message HTML format validity
- Fallback to local save when Telegram fails
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


def _make_notifier():
    from crypto_advisor.notification.telegram import TelegramNotifier
    return TelegramNotifier(token="fake_token", chat_id="123456789")


def _make_report_data():
    from crypto_advisor.models import (
        PortfolioPosition, TaxContext, FearGreedData, RecommendationOutput,
    )
    from crypto_advisor.reporting.report import ReportData
    return ReportData(
        week_date="2026-05-12",
        portfolio=[PortfolioPosition(symbol="BTC", quantity=0.05, avg_price_brl=320_000.0)],
        portfolio_total_brl=16_500.0,
        portfolio_pnl_brl=500.0,
        recommendations=[
            RecommendationOutput(
                symbol="BTC", action="BUY", confidence="high",
                entry_price_usd=65_000.0, stop_loss_usd=62_000.0,
                target_price_usd=71_000.0, risk_reward_ratio=2.0,
                reasoning="Setup bullish.", tax_impact="",
            ),
        ],
        market_summary="Mercado em alta.",
        fear_greed=FearGreedData(
            value=72, classification="Greed",
            timestamp=datetime(2026, 5, 12, 18, 0, 0, tzinfo=timezone.utc),
        ),
        tax_context=TaxContext(
            zone="safe", total_sold_brl=12_400.0, limit_brl=35_000.0,
            margin_available_brl=22_600.0, instruction="Operar normalmente.",
        ),
        top_markets=[],
    )


# ─── send_weekly_report ───────────────────────────────────────────────────────

def _patch_telegram(mock_bot):
    """Patch both the Bot class and _HAS_TELEGRAM flag."""
    return [
        patch("crypto_advisor.notification.telegram.Bot", return_value=mock_bot),
        patch("crypto_advisor.notification.telegram._HAS_TELEGRAM", True),
    ]


class TestSendWeeklyReport:
    @pytest.mark.asyncio
    async def test_calls_send_message(self):
        from crypto_advisor.notification.telegram import TelegramNotifier
        notifier = TelegramNotifier(token="fake", chat_id="123")

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=MagicMock())
        mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
        mock_bot.__aexit__ = AsyncMock(return_value=False)

        for p in _patch_telegram(mock_bot):
            p.start()
        try:
            await notifier.send_weekly_report("test message")
        finally:
            for p in _patch_telegram(mock_bot):
                p.stop()

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == "123"
        assert "test message" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_uses_html_parse_mode(self):
        from crypto_advisor.notification.telegram import TelegramNotifier
        notifier = TelegramNotifier(token="fake", chat_id="123")
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=MagicMock())
        mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
        mock_bot.__aexit__ = AsyncMock(return_value=False)

        for p in _patch_telegram(mock_bot):
            p.start()
        try:
            await notifier.send_weekly_report("test")
        finally:
            for p in _patch_telegram(mock_bot):
                p.stop()

        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs.get("parse_mode") in ("HTML", "MarkdownV2", "Markdown")

    @pytest.mark.asyncio
    async def test_fallback_on_telegram_error(self, tmp_path):
        from crypto_advisor.notification.telegram import TelegramNotifier
        notifier = TelegramNotifier(token="fake", chat_id="123",
                                     fallback_dir=tmp_path)
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(side_effect=Exception("Network error"))
        mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
        mock_bot.__aexit__ = AsyncMock(return_value=False)

        for p in _patch_telegram(mock_bot):
            p.start()
        try:
            await notifier.send_weekly_report("report content")
        finally:
            for p in _patch_telegram(mock_bot):
                p.stop()

        files = list(tmp_path.glob("*.txt"))
        assert len(files) == 1


# ─── send_tax_alert ───────────────────────────────────────────────────────────

class TestSendTaxAlert:
    @pytest.mark.asyncio
    async def test_warning_alert_sent(self):
        from crypto_advisor.notification.telegram import TelegramNotifier
        notifier = TelegramNotifier(token="fake", chat_id="123")
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=MagicMock())
        mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
        mock_bot.__aexit__ = AsyncMock(return_value=False)

        for p in _patch_telegram(mock_bot):
            p.start()
        try:
            await notifier.send_tax_alert(zone="warning", total_sold_brl=29_000.0)
        finally:
            for p in _patch_telegram(mock_bot):
                p.stop()

        call_kwargs = mock_bot.send_message.call_args[1]
        assert "29" in call_kwargs["text"] or "warning" in call_kwargs["text"].lower()

    @pytest.mark.asyncio
    async def test_blocked_alert_has_urgency(self):
        from crypto_advisor.notification.telegram import TelegramNotifier
        notifier = TelegramNotifier(token="fake", chat_id="123")
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=MagicMock())
        mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
        mock_bot.__aexit__ = AsyncMock(return_value=False)

        for p in _patch_telegram(mock_bot):
            p.start()
        try:
            await notifier.send_tax_alert(zone="blocked", total_sold_brl=35_500.0)
        finally:
            for p in _patch_telegram(mock_bot):
                p.stop()

        call_kwargs = mock_bot.send_message.call_args[1]
        text = call_kwargs["text"].upper()
        assert "BLOQUEADO" in text or "BLOCKED" in text or "35" in text

    @pytest.mark.asyncio
    async def test_safe_zone_does_not_send_alert(self):
        from crypto_advisor.notification.telegram import TelegramNotifier
        notifier = TelegramNotifier(token="fake", chat_id="123")
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=MagicMock())

        with patch("crypto_advisor.notification.telegram.Bot", return_value=mock_bot):
            await notifier.send_tax_alert(zone="safe", total_sold_brl=5_000.0)

        mock_bot.send_message.assert_not_called()


# ─── Message format helpers ───────────────────────────────────────────────────

class TestMessageFormat:
    def test_format_report_message_is_string(self):
        from crypto_advisor.notification.telegram import TelegramNotifier
        from crypto_advisor.reporting.report import ReportBuilder
        notifier = TelegramNotifier(token="fake", chat_id="123")
        builder = ReportBuilder()
        data = _make_report_data()
        summary = builder.build_telegram_summary(data)
        assert isinstance(summary, str)

    def test_format_report_within_4096_chars(self):
        from crypto_advisor.reporting.report import ReportBuilder
        builder = ReportBuilder()
        summary = builder.build_telegram_summary(_make_report_data())
        assert len(summary) <= 4096
