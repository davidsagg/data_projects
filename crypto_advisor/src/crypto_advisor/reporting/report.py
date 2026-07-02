"""Report builder: Jinja2 HTML + Telegram summary formatter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import (
    FearGreedData, MarketData, PerformanceSummary, PortfolioPosition,
    RecommendationOutput, TaxContext,
)

try:
    from ..tax.optimizer import IncomeSuggestion
except ImportError:
    IncomeSuggestion = None  # type: ignore[assignment,misc]

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TELEGRAM_MAX = 4096

ACTION_EMOJI = {
    "BUY": "🟢", "SELL": "🔴", "HOLD": "🔵", "SKIP": "⚪",
}
ZONE_EMOJI = {
    "safe": "✅", "warning": "⚠️", "critical": "🟠", "blocked": "🚫",
}


# ─── Report data container ────────────────────────────────────────────────────

@dataclass
class ReportData:
    week_date: str
    portfolio: list[PortfolioPosition]
    portfolio_total_brl: float
    portfolio_pnl_brl: float
    recommendations: list[RecommendationOutput]
    market_summary: str
    fear_greed: FearGreedData | None
    tax_context: TaxContext | None
    top_markets: list[MarketData] = field(default_factory=list)
    performance: PerformanceSummary | None = None
    income_suggestions: list = field(default_factory=list)  # list[IncomeSuggestion]
    usd_brl_rate: float = 5.8  # fallback; overridden by scheduler from live MarketData
    current_prices_brl: dict = field(default_factory=dict)  # symbol → current price in BRL


# ─── ReportBuilder ────────────────────────────────────────────────────────────

class ReportBuilder:
    def __init__(self, template_dir: Path | None = None) -> None:
        tdir = template_dir or _TEMPLATE_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(tdir)),
            autoescape=select_autoescape(["html"]),
        )

    # ── HTML report ───────────────────────────────────────────────────────────

    def build_html(self, data: ReportData) -> str:
        template = self._env.get_template("weekly_report.html.j2")
        return template.render(
            week_date=data.week_date,
            portfolio=data.portfolio,
            portfolio_total_brl=data.portfolio_total_brl,
            portfolio_pnl_brl=data.portfolio_pnl_brl,
            recommendations=data.recommendations,
            market_summary=data.market_summary,
            fear_greed=data.fear_greed,
            tax_context=data.tax_context,
            top_markets=data.top_markets,
            performance=data.performance,
            usd_brl_rate=data.usd_brl_rate,
            current_prices_brl=data.current_prices_brl,
        )

    def save(
        self,
        html: str,
        week_date: str,
        output_dir: Path | None = None,
    ) -> Path:
        out = output_dir or Path("data/reports")
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{week_date}.html"
        path.write_text(html, encoding="utf-8")
        return path

    # ── Telegram summary ──────────────────────────────────────────────────────

    def build_telegram_summary(self, data: ReportData) -> str:
        lines: list[str] = []

        # Header
        lines.append(f"📊 <b>CryptoAdvisor — {data.week_date}</b>")
        if data.fear_greed:
            lines.append(
                f"<i>Fear &amp; Greed: {data.fear_greed.value} "
                f"({data.fear_greed.classification})</i>"
            )
        lines.append("")

        # Portfolio
        pnl_sign = "+" if data.portfolio_pnl_brl >= 0 else ""
        lines.append(
            f"💼 <b>Portfólio:</b> R${data.portfolio_total_brl:,.2f} "
            f"| {pnl_sign}R${data.portfolio_pnl_brl:,.2f}"
        )
        lines.append("")

        # Recommendations
        recs = data.recommendations
        rate = data.usd_brl_rate

        def _brl(usd: float | None) -> str:
            if usd is None or usd <= 0:
                return "—"
            return f"R${usd * rate:,.2f}"

        lines.append(f"🎯 <b>Recomendações ({len(recs)}):</b>")
        for rec in recs:
            emoji = ACTION_EMOJI.get(rec.action, "•")
            confidence_tag = f"[{rec.confidence[:1].upper()}]"
            has_prices = (
                rec.entry_price_usd is not None
                and rec.entry_price_usd > 0
                and rec.target_price_usd is not None
                and rec.target_price_usd > 0
            )
            if has_prices and rec.risk_reward_ratio:
                price_info = (
                    f" | {_brl(rec.entry_price_usd)}→{_brl(rec.target_price_usd)} "
                    f"| stop {_brl(rec.stop_loss_usd)} "
                    f"| RR {rec.risk_reward_ratio:.1f}x"
                )
            elif has_prices:
                price_info = f" | {_brl(rec.entry_price_usd)}→{_brl(rec.target_price_usd)}"
            else:
                price_info = ""
            lines.append(
                f"{emoji} <b>{rec.symbol} — {rec.action}</b>{price_info} {confidence_tag}"
            )

        lines.append("")

        # Tax status
        if data.tax_context:
            tc = data.tax_context
            zone_emoji = ZONE_EMOJI.get(tc.zone, "•")
            pct = tc.total_sold_brl / tc.limit_brl * 100
            lines.append(
                f"🧾 <b>Tax:</b> R${tc.total_sold_brl:,.0f}/R${tc.limit_brl:,.0f} "
                f"({pct:.0f}%) {zone_emoji} {tc.zone.upper()}"
            )
            lines.append("")

        # Income suggestions (only in SAFE zone, when present)
        if data.income_suggestions:
            lines.append("\n💡 <b>Income Strategy:</b>")
            for s in data.income_suggestions[:3]:
                lines.append(
                    f"  ▸ {s.symbol}: vender {s.quantity_to_sell:.8f} un "
                    f"≈ R${s.estimated_brl:,.2f} "
                    f"(+{s.gain_pct:.1f}% / +R${s.estimated_gain_brl:,.2f})"
                )
            lines.append("")

        # Legenda
        lines.append(
            "<i>RR = risco/retorno (ex: RR 2.0x → ganho potencial 2× o risco) "
            "| [H]=alta [M]=média [L]=baixa confiança</i>"
        )
        lines.append("")

        # UI link
        lines.append("👉 <a href='http://localhost:8501'>Validar recomendações →</a>")

        text = "\n".join(lines)

        # Enforce Telegram's 4096-char hard limit
        if len(text) > _TELEGRAM_MAX:
            text = text[: _TELEGRAM_MAX - 4] + "\n..."

        return text
