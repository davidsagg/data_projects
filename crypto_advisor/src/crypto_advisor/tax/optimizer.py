"""Tax Optimizer Module — IN RFB 2.312/2026.

Tracks monthly BRL sales per exchange, enforces the R$35k exemption limit,
and generates TaxContext for injection into the Claude recommendation prompt.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from ..models import PortfolioPosition, TaxContext
from ..db.repository import TaxRepository, PortfolioRepository

# ─── Thresholds (configurable via env if needed) ──────────────────────────────

TAX_LIMIT_BRL = 35_000.0
TAX_WARNING_BRL = 28_000.0
TAX_CRITICAL_BRL = 33_000.0


# ─── Internal data classes ────────────────────────────────────────────────────

@dataclass
class TaxStatus:
    zone: str           # "safe" | "warning" | "critical" | "blocked"
    total_sold_brl: float
    limit_brl: float
    margin_available_brl: float


@dataclass
class IncomeSuggestion:
    symbol: str
    quantity_to_sell: float
    estimated_brl: float
    estimated_gain_brl: float
    gain_pct: float


@dataclass
class LossHarvestCandidate:
    symbol: str
    quantity: float
    avg_price_brl: float
    current_price_brl: float
    unrealized_loss_brl: float
    loss_pct: float


# ─── Zone helpers ─────────────────────────────────────────────────────────────

def _zone(total_sold: float) -> str:
    if total_sold >= TAX_LIMIT_BRL:
        return "blocked"
    if total_sold >= TAX_CRITICAL_BRL:
        return "critical"
    if total_sold >= TAX_WARNING_BRL:
        return "warning"
    return "safe"


def _zone_instruction(zone: str) -> str:
    return {
        "safe": (
            "Operar normalmente. Incluir impacto fiscal (tax_impact) em cada "
            "recomendação de venda."
        ),
        "warning": (
            "ATENÇÃO: vendas acumuladas acima de R$28.000. Priorizar loss harvesting. "
            "Reduzir tamanho de posições novas. Incluir tax_impact em todas as vendas."
        ),
        "critical": (
            "CRÍTICO: vendas acumuladas acima de R$33.000. Gerar APENAS recomendações "
            "de loss harvesting (posições em prejuízo). Não recomendar vendas com lucro."
        ),
        "blocked": (
            "BLOQUEADO: limite mensal de R$35.000 atingido. Não gerar NENHUMA "
            "recomendação de venda este mês. Apenas BUY e HOLD são permitidos."
        ),
    }[zone]


# ─── TaxOptimizer ─────────────────────────────────────────────────────────────

class TaxOptimizer:
    """Main tax optimisation engine backed by SQLite."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        exchange: str = "mercado_bitcoin",
    ) -> None:
        self._conn = conn
        self._exchange = exchange
        self._tax_repo = TaxRepository(conn)
        self._portfolio_repo = PortfolioRepository(conn)

    # ── Monthly status ────────────────────────────────────────────────────────

    def get_monthly_status(
        self, year: int, month: int, exchange: str | None = None
    ) -> TaxStatus:
        exch = exchange or self._exchange
        record = self._tax_repo.get_monthly(year, month, exch)
        total = record["total_sold_brl"] if record else 0.0
        zone = record["tax_status"] if record else "safe"
        return TaxStatus(
            zone=zone,
            total_sold_brl=total,
            limit_brl=TAX_LIMIT_BRL,
            margin_available_brl=max(0.0, TAX_LIMIT_BRL - total),
        )

    # ── Accumulate a sale ─────────────────────────────────────────────────────

    def add_sale(
        self,
        total_brl: float,
        gain_brl: float,
        year: int,
        month: int,
        exchange: str | None = None,
    ) -> TaxStatus:
        """Add a completed sale, update the accumulator, return new TaxStatus."""
        exch = exchange or self._exchange
        record = self._tax_repo.get_monthly(year, month, exch)
        current_total = record["total_sold_brl"] if record else 0.0
        current_gain = record["realized_gain_brl"] if record else 0.0
        current_loss = record["realized_loss_brl"] if record else 0.0

        new_total = current_total + total_brl
        new_gain = current_gain + max(0.0, gain_brl)
        new_loss = current_loss + abs(min(0.0, gain_brl))
        new_zone = _zone(new_total)

        self._tax_repo.upsert(
            year, month, exch, new_total, new_gain, new_loss, new_zone
        )

        return TaxStatus(
            zone=new_zone,
            total_sold_brl=new_total,
            limit_brl=TAX_LIMIT_BRL,
            margin_available_brl=max(0.0, TAX_LIMIT_BRL - new_total),
        )

    # ── Rebuild from trades table ─────────────────────────────────────────────

    def sync_from_trades(
        self, year: int, month: int, exchange: str | None = None
    ) -> TaxStatus:
        """Recompute tax_tracker from the raw trades table for a given month."""
        exch = exchange or self._exchange
        rows = self._conn.execute(
            """SELECT SUM(total_brl) as total_sold,
                      SUM(CASE WHEN total_brl > 0 THEN total_brl ELSE 0 END) as gain,
                      0 as loss
               FROM trades
               WHERE side='sell'
                 AND exchange=?
                 AND strftime('%Y', traded_at)=?
                 AND strftime('%m', traded_at)=?""",
            (exch, str(year), f"{month:02d}"),
        ).fetchone()

        total = rows["total_sold"] or 0.0
        gain = rows["gain"] or 0.0
        zone = _zone(total)

        self._tax_repo.upsert(year, month, exch, total, gain, 0.0, zone)

        return TaxStatus(
            zone=zone,
            total_sold_brl=total,
            limit_brl=TAX_LIMIT_BRL,
            margin_available_brl=max(0.0, TAX_LIMIT_BRL - total),
        )

    # ── Loss harvesting candidates ────────────────────────────────────────────

    def get_loss_harvest_candidates(
        self,
        current_prices_brl: dict[str, float],
        min_loss_pct: float = 0.05,
        exchange: str | None = None,
    ) -> list[LossHarvestCandidate]:
        exch = exchange or self._exchange
        positions = self._portfolio_repo.get_all(exch)
        candidates: list[LossHarvestCandidate] = []

        for pos in positions:
            current = current_prices_brl.get(pos.symbol)
            if current is None or pos.avg_price_brl <= 0:
                continue
            loss_pct = (pos.avg_price_brl - current) / pos.avg_price_brl
            if loss_pct < min_loss_pct:
                continue
            loss_brl = (pos.avg_price_brl - current) * pos.quantity
            candidates.append(LossHarvestCandidate(
                symbol=pos.symbol,
                quantity=pos.quantity,
                avg_price_brl=pos.avg_price_brl,
                current_price_brl=current,
                unrealized_loss_brl=round(loss_brl, 2),
                loss_pct=round(loss_pct * 100, 2),
            ))

        return sorted(candidates, key=lambda c: c.loss_pct, reverse=True)

    # ── Income strategy: max sell for this month ──────────────────────────────

    def calculate_max_sell_brl(
        self, year: int, month: int, exchange: str | None = None
    ) -> float:
        """Maximum BRL that can be sold this month without entering WARNING zone."""
        status = self.get_monthly_status(year, month, exchange)
        return max(0.0, TAX_WARNING_BRL - status.total_sold_brl)

    # ── Build TaxContext for Claude prompt ────────────────────────────────────

    def build_tax_context(
        self,
        year: int,
        month: int,
        current_prices_brl: dict[str, float],
        exchange: str | None = None,
    ) -> TaxContext:
        exch = exchange or self._exchange
        status = self.get_monthly_status(year, month, exch)
        candidates = self.get_loss_harvest_candidates(current_prices_brl, exchange=exch)

        return TaxContext(
            zone=status.zone,  # type: ignore[arg-type]
            total_sold_brl=status.total_sold_brl,
            limit_brl=status.limit_brl,
            margin_available_brl=status.margin_available_brl,
            instruction=_zone_instruction(status.zone),
            loss_harvest_candidates=[c.symbol for c in candidates],
        )

    # ── Income strategy: suggest partial profit-taking sells ──────────────────

    def suggest_income_sells(
        self,
        current_prices_brl: dict[str, float],
        year: int,
        month: int,
        exchange: str | None = None,
        min_gain_pct: float = 0.10,
        safety_margin_brl: float = 2_000.0,
    ) -> list[IncomeSuggestion]:
        """Suggest partial sells to realise gains within the tax-free limit.

        Only operates in SAFE zone. Prioritises highest gain % positions.
        Each suggestion caps at 50% of the position to preserve exposure.
        Total suggested sell BRL ≤ calculate_max_sell_brl() − safety_margin.
        """
        exch = exchange or self._exchange
        status = self.get_monthly_status(year, month, exch)
        if status.zone != "safe":
            return []

        budget_brl = self.calculate_max_sell_brl(year, month, exch) - safety_margin_brl
        if budget_brl <= 0:
            return []

        positions = self._portfolio_repo.get_all(exch)
        candidates: list[tuple[float, object, float]] = []

        for pos in positions:
            if pos.symbol == "BRL" or pos.avg_price_brl <= 0:
                continue
            current_brl = current_prices_brl.get(pos.symbol)
            if not current_brl:
                continue
            gain_pct = (current_brl - pos.avg_price_brl) / pos.avg_price_brl
            if gain_pct < min_gain_pct:
                continue
            candidates.append((gain_pct, pos, current_brl))

        candidates.sort(key=lambda x: x[0], reverse=True)

        suggestions: list[IncomeSuggestion] = []
        remaining = budget_brl

        for gain_pct, pos, current_brl in candidates:
            if remaining <= 0:
                break
            max_qty = pos.quantity * 0.5  # never sell more than 50% of position
            max_value = max_qty * current_brl

            if max_value <= remaining:
                qty = max_qty
                sell_brl = max_value
            else:
                qty = remaining / current_brl
                sell_brl = remaining

            gain_brl = (current_brl - pos.avg_price_brl) * qty
            suggestions.append(IncomeSuggestion(
                symbol=pos.symbol,
                quantity_to_sell=round(qty, 8),
                estimated_brl=round(sell_brl, 2),
                estimated_gain_brl=round(gain_brl, 2),
                gain_pct=round(gain_pct * 100, 2),
            ))
            remaining -= sell_brl

        return suggestions

    # ── Yearly fiscal summary ─────────────────────────────────────────────────

    def get_yearly_summary(
        self, year: int, exchange: str | None = None
    ) -> list[dict]:
        """Return one entry per month (1–12) with fiscal totals.

        Months without any sales are returned with zeros so the caller always
        gets a 12-entry list for a complete year view.
        """
        exch = exchange or self._exchange
        rows = self._conn.execute(
            """SELECT month, total_sold_brl, realized_gain_brl,
                      realized_loss_brl, tax_status
               FROM tax_tracker
               WHERE year=? AND exchange=?
               ORDER BY month""",
            (year, exch),
        ).fetchall()

        by_month = {r["month"]: dict(r) for r in rows}
        summary = []
        for m in range(1, 13):
            entry = by_month.get(m, {
                "month": m,
                "total_sold_brl": 0.0,
                "realized_gain_brl": 0.0,
                "realized_loss_brl": 0.0,
                "tax_status": "safe",
            })
            entry["month"] = m
            summary.append(entry)
        return summary
