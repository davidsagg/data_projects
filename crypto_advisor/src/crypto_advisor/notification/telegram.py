"""Telegram Bot notification delivery."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import IO

try:
    from telegram import Bot
    from telegram.constants import ParseMode
    _HAS_TELEGRAM = True
except ImportError:
    _HAS_TELEGRAM = False
    Bot = None  # type: ignore[assignment,misc]
    ParseMode = None  # type: ignore[assignment]

ZONE_MESSAGES = {
    "warning": (
        "⚠️ <b>ALERTA FISCAL — WARNING</b>\n\n"
        "Vendas acumuladas: R${total:,.0f} / R$35.000 ({pct:.0f}%)\n"
        "Você ultrapassou R$28.000 de vendas este mês.\n"
        "Priorize loss harvesting e reduza novas vendas."
    ),
    "critical": (
        "🟠 <b>ALERTA FISCAL — CRÍTICO</b>\n\n"
        "Vendas acumuladas: R${total:,.0f} / R$35.000 ({pct:.0f}%)\n"
        "Apenas operações de <b>loss harvesting</b> permitidas.\n"
        "Não realize mais vendas com lucro este mês."
    ),
    "blocked": (
        "🚫 <b>BLOQUEIO FISCAL — LIMITE ATINGIDO</b>\n\n"
        "Vendas acumuladas: R${total:,.0f} / R$35.000 ({pct:.0f}%)\n"
        "Limite mensal de R$35.000 atingido.\n"
        "<b>Nenhuma venda permitida até o próximo mês.</b>"
    ),
}


class TelegramNotifier:
    def __init__(
        self,
        token: str,
        chat_id: str,
        fallback_dir: Path | None = None,
    ) -> None:
        self._token = token
        self._chat_id = chat_id
        self._fallback_dir = fallback_dir or Path("data/reports")

    async def send_weekly_report(self, summary: str) -> None:
        """Send the weekly report summary to the configured chat."""
        try:
            await self._send(summary)
        except Exception as exc:
            self._save_fallback(summary, label="weekly_report", error=str(exc))

    async def send_report_file(self, report_path: Path, week_date: str) -> None:
        """Send the HTML report as a downloadable document."""
        if not _HAS_TELEGRAM:
            return
        try:
            async with Bot(token=self._token) as bot:
                with open(report_path, "rb") as f:
                    await bot.send_document(
                        chat_id=self._chat_id,
                        document=f,
                        filename=f"relatorio_{week_date}.html",
                        caption=f"📄 Relatório completo — {week_date}",
                    )
        except Exception as exc:
            self._save_fallback(str(report_path), label="report_file_fallback", error=str(exc))

    def send_report_file_sync(self, report_path: Path, week_date: str) -> None:
        asyncio.run(self.send_report_file(report_path, week_date))

    async def send_tax_alert(self, zone: str, total_sold_brl: float) -> None:
        """Send a tax zone change alert. No-op for 'safe' zone."""
        if zone == "safe":
            return
        template = ZONE_MESSAGES.get(zone, "🧾 Tax zone changed: {zone}")
        pct = total_sold_brl / 35_000.0 * 100
        message = template.format(total=total_sold_brl, pct=pct, zone=zone)
        try:
            await self._send(message)
        except Exception as exc:
            self._save_fallback(message, label=f"tax_alert_{zone}", error=str(exc))

    async def _send(self, text: str) -> None:
        if not _HAS_TELEGRAM:
            raise ImportError(
                "python-telegram-bot not installed. "
                "Run: pip install python-telegram-bot>=21.0"
            )
        parse_mode = ParseMode.HTML if ParseMode else "HTML"
        async with Bot(token=self._token) as bot:
            await bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )

    def _save_fallback(self, text: str, label: str, error: str = "") -> None:
        self._fallback_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self._fallback_dir / f"{label}_{ts}.txt"
        header = f"[FALLBACK — Telegram unavailable: {error}]\n\n" if error else ""
        path.write_text(header + text, encoding="utf-8")

    def send_weekly_report_sync(self, summary: str) -> None:
        asyncio.run(self.send_weekly_report(summary))

    def send_tax_alert_sync(self, zone: str, total_sold_brl: float) -> None:
        asyncio.run(self.send_tax_alert(zone, total_sold_brl))
