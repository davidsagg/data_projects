"""Typed repository layer — SQLite CRUD for all tables. No ORM."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ..models import PerformanceSummary, PortfolioPosition, TradeRecord


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── PortfolioRepository ──────────────────────────────────────────────────────

class PortfolioRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, position: PortfolioPosition) -> None:
        self._conn.execute(
            """INSERT INTO portfolio (symbol, quantity, avg_price_brl, exchange, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(symbol, exchange) DO UPDATE SET
                 quantity      = excluded.quantity,
                 avg_price_brl = excluded.avg_price_brl,
                 updated_at    = excluded.updated_at""",
            (position.symbol, position.quantity, position.avg_price_brl,
             position.exchange, _now_iso()),
        )
        self._conn.commit()

    def upsert_bulk(self, positions: list[PortfolioPosition]) -> None:
        self._conn.executemany(
            """INSERT INTO portfolio (symbol, quantity, avg_price_brl, exchange, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(symbol, exchange) DO UPDATE SET
                 quantity      = excluded.quantity,
                 avg_price_brl = excluded.avg_price_brl,
                 updated_at    = excluded.updated_at""",
            [(p.symbol, p.quantity, p.avg_price_brl, p.exchange, _now_iso())
             for p in positions],
        )
        self._conn.commit()

    def get_all(self, exchange: str = "mercado_bitcoin") -> list[PortfolioPosition]:
        rows = self._conn.execute(
            "SELECT symbol, quantity, avg_price_brl, exchange FROM portfolio WHERE exchange=?",
            (exchange,),
        ).fetchall()
        return [PortfolioPosition(
            symbol=r["symbol"], quantity=r["quantity"],
            avg_price_brl=r["avg_price_brl"], exchange=r["exchange"],
        ) for r in rows]

    def set_avg_price(
        self, symbol: str, avg_price_brl: float, exchange: str = "mercado_bitcoin"
    ) -> bool:
        """Update only avg_price_brl for an existing position. Returns True if found."""
        cur = self._conn.execute(
            """UPDATE portfolio SET avg_price_brl=?, updated_at=?
               WHERE symbol=? AND exchange=?""",
            (avg_price_brl, _now_iso(), symbol.upper(), exchange),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_by_symbol(
        self, symbol: str, exchange: str = "mercado_bitcoin"
    ) -> PortfolioPosition | None:
        row = self._conn.execute(
            "SELECT symbol, quantity, avg_price_brl, exchange FROM portfolio "
            "WHERE symbol=? AND exchange=?",
            (symbol, exchange),
        ).fetchone()
        if row is None:
            return None
        return PortfolioPosition(
            symbol=row["symbol"], quantity=row["quantity"],
            avg_price_brl=row["avg_price_brl"], exchange=row["exchange"],
        )


# ─── TradeRepository ──────────────────────────────────────────────────────────

class TradeRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, trade: TradeRecord, recommendation_id: int | None = None) -> None:
        traded_at = trade.traded_at.isoformat() if isinstance(trade.traded_at, datetime) \
            else trade.traded_at
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO trades
                   (symbol, side, quantity, price_brl, total_brl, fee_brl,
                    exchange, traded_at, recommendation_id)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (trade.symbol, trade.side, trade.quantity, trade.price_brl,
                 trade.total_brl, trade.fee_brl, trade.exchange,
                 traded_at, recommendation_id),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            pass  # duplicate — silently skip

    def get_monthly_sells(
        self,
        year: int,
        month: int,
        exchange: str = "mercado_bitcoin",
    ) -> list[TradeRecord]:
        rows = self._conn.execute(
            """SELECT symbol, side, quantity, price_brl, total_brl, fee_brl,
                      exchange, traded_at
               FROM trades
               WHERE side='sell'
                 AND exchange=?
                 AND strftime('%Y', traded_at)=?
                 AND strftime('%m', traded_at)=?
               ORDER BY traded_at""",
            (exchange, str(year), f"{month:02d}"),
        ).fetchall()
        return [self._row_to_trade(r) for r in rows]

    def get_latest_traded_at(self, exchange: str = "mercado_bitcoin") -> datetime | None:
        row = self._conn.execute(
            "SELECT MAX(traded_at) as latest FROM trades WHERE exchange=?", (exchange,)
        ).fetchone()
        if row["latest"] is None:
            return None
        return datetime.fromisoformat(row["latest"])

    @staticmethod
    def _row_to_trade(row: sqlite3.Row) -> TradeRecord:
        return TradeRecord(
            symbol=row["symbol"],
            side=row["side"],  # type: ignore[arg-type]
            quantity=row["quantity"],
            price_brl=row["price_brl"],
            total_brl=row["total_brl"],
            fee_brl=row["fee_brl"],
            exchange=row["exchange"],
            traded_at=datetime.fromisoformat(row["traded_at"]),
        )


# ─── TaxRepository ────────────────────────────────────────────────────────────

class TaxRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_monthly(
        self, year: int, month: int, exchange: str = "mercado_bitcoin"
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """SELECT total_sold_brl, realized_gain_brl, realized_loss_brl, tax_status
               FROM tax_tracker
               WHERE year=? AND month=? AND exchange=?""",
            (year, month, exchange),
        ).fetchone()
        return dict(row) if row else None

    def upsert(
        self,
        year: int,
        month: int,
        exchange: str,
        total_sold_brl: float,
        realized_gain_brl: float,
        realized_loss_brl: float,
        tax_status: str,
    ) -> None:
        self._conn.execute(
            """INSERT INTO tax_tracker
               (year, month, exchange, total_sold_brl, realized_gain_brl,
                realized_loss_brl, tax_status, updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(year, month, exchange) DO UPDATE SET
                 total_sold_brl    = excluded.total_sold_brl,
                 realized_gain_brl = excluded.realized_gain_brl,
                 realized_loss_brl = excluded.realized_loss_brl,
                 tax_status        = excluded.tax_status,
                 updated_at        = excluded.updated_at""",
            (year, month, exchange, total_sold_brl, realized_gain_brl,
             realized_loss_brl, tax_status, _now_iso()),
        )
        self._conn.commit()


# ─── RecommendationRepository ─────────────────────────────────────────────────

class RecommendationRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(
        self,
        week_date: str,
        symbol: str,
        action: str,
        reasoning: str,
        raw_json: str,
        confidence: str = "medium",
        entry_price_usd: float | None = None,
        stop_loss_usd: float | None = None,
        target_price_usd: float | None = None,
        risk_reward_ratio: float | None = None,
        tax_impact: str = "",
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO recommendations
               (week_date, symbol, action, entry_price_usd, stop_loss_usd,
                target_price_usd, risk_reward_ratio, confidence, reasoning,
                tax_impact, raw_json, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending',?)""",
            (week_date, symbol, action, entry_price_usd, stop_loss_usd,
             target_price_usd, risk_reward_ratio, confidence, reasoning,
             tax_impact, raw_json, _now_iso()),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def save_from_output(self, week_date: str, rec: Any) -> int:
        """Convenience wrapper that accepts a RecommendationOutput model."""
        return self.save(
            week_date=week_date,
            symbol=rec.symbol,
            action=rec.action,
            reasoning=rec.reasoning,
            raw_json=json.dumps(rec.model_dump()),
            confidence=rec.confidence,
            entry_price_usd=rec.entry_price_usd,
            stop_loss_usd=rec.stop_loss_usd,
            target_price_usd=rec.target_price_usd,
            risk_reward_ratio=rec.risk_reward_ratio,
            tax_impact=rec.tax_impact,
        )

    def update_status(self, rec_id: int, status: str) -> None:
        self._conn.execute(
            "UPDATE recommendations SET status=?, reviewed_at=? WHERE id=?",
            (status, _now_iso(), rec_id),
        )
        self._conn.commit()

    def get_pending(self, week_date: str | None = None) -> list[dict[str, Any]]:
        if week_date:
            rows = self._conn.execute(
                "SELECT * FROM recommendations WHERE status='pending' AND week_date=? "
                "ORDER BY created_at",
                (week_date,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM recommendations WHERE status='pending' ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_week(self, week_date: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM recommendations WHERE week_date=? ORDER BY created_at",
            (week_date,),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── PerformanceRepository ────────────────────────────────────────────────────

class PerformanceRepository:
    BREAKEVEN_THRESHOLD = 0.01  # BRL tolerance for breakeven

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def log_close(
        self,
        week_date: str,
        symbol: str,
        entry_price_brl: float,
        exit_price_brl: float,
        quantity: float,
        stop_loss_brl: float,
        recommendation_id: int | None = None,
    ) -> None:
        pnl_brl = (exit_price_brl - entry_price_brl) * quantity
        pnl_pct = (exit_price_brl / entry_price_brl - 1) * 100 if entry_price_brl else 0.0
        risk_per_unit = entry_price_brl - stop_loss_brl
        r_multiple = (
            (exit_price_brl - entry_price_brl) / risk_per_unit
            if risk_per_unit != 0 else 0.0
        )
        if abs(pnl_brl) < self.BREAKEVEN_THRESHOLD:
            outcome = "breakeven"
        elif pnl_brl > 0:
            outcome = "win"
        else:
            outcome = "loss"

        self._conn.execute(
            """INSERT INTO performance_log
               (week_date, recommendation_id, symbol, entry_price_brl, exit_price_brl,
                quantity, pnl_brl, pnl_pct, r_multiple, outcome, closed_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (week_date, recommendation_id, symbol, entry_price_brl, exit_price_brl,
             quantity, round(pnl_brl, 2), round(pnl_pct, 4), round(r_multiple, 4),
             outcome, _now_iso(), _now_iso()),
        )
        self._conn.commit()

    def get_summary(self) -> PerformanceSummary:
        closed = self._conn.execute(
            """SELECT outcome, pnl_brl, r_multiple
               FROM performance_log WHERE outcome != 'open'"""
        ).fetchall()
        open_count = self._conn.execute(
            "SELECT COUNT(*) as c FROM performance_log WHERE outcome='open'"
        ).fetchone()["c"]

        if not closed:
            return PerformanceSummary(open_trades=open_count)

        total = len(closed)
        wins = sum(1 for r in closed if r["outcome"] == "win")
        total_pnl = sum(r["pnl_brl"] for r in closed)
        avg_r = sum(r["r_multiple"] for r in closed) / total

        return PerformanceSummary(
            total_trades=total,
            win_rate_pct=round(wins / total * 100, 2),
            avg_r_multiple=round(avg_r, 4),
            total_pnl_brl=round(total_pnl, 2),
            open_trades=open_count,
        )

    def get_monthly_pnl(self, year: int, month: int) -> float:
        # Filter by week_date (trade date) not closed_at (log timestamp)
        row = self._conn.execute(
            """SELECT COALESCE(SUM(pnl_brl), 0) as total
               FROM performance_log
               WHERE outcome != 'open'
                 AND strftime('%Y', week_date) = ?
                 AND strftime('%m', week_date) = ?""",
            (str(year), f"{month:02d}"),
        ).fetchone()
        return float(row["total"])

    def get_income_goal_progress(
        self, year: int, month: int, goal_brl: float
    ) -> float:
        """Return progress toward monthly income goal as a percentage."""
        monthly_pnl = self.get_monthly_pnl(year, month)
        if goal_brl <= 0:
            return 0.0
        return round(monthly_pnl / goal_brl * 100, 2)
