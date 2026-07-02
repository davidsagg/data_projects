"""
Tests for the Performance Tracker.

Covers:
- log_close: persists a closed trade to performance_log
- get_summary: win rate, avg R-multiple, total P&L
- R-multiple calculation
- open trades count
- weekly progress toward monthly income goal
"""

import pytest
from datetime import datetime, timezone


# ─── log_close ────────────────────────────────────────────────────────────────

class TestLogClose:
    def test_log_close_persists_to_db(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        repo.log_close(
            week_date="2026-05-12",
            symbol="BTC",
            entry_price_brl=320_000.0,
            exit_price_brl=330_000.0,
            quantity=0.05,
            stop_loss_brl=310_000.0,
        )
        rows = db_conn.execute("SELECT * FROM performance_log").fetchall()
        assert len(rows) == 1

    def test_win_outcome_when_pnl_positive(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        repo.log_close(
            week_date="2026-05-12", symbol="BTC",
            entry_price_brl=320_000.0, exit_price_brl=330_000.0,
            quantity=0.05, stop_loss_brl=310_000.0,
        )
        row = db_conn.execute("SELECT outcome, pnl_brl FROM performance_log").fetchone()
        assert row["outcome"] == "win"
        assert row["pnl_brl"] == pytest.approx(500.0)  # (330k-320k)*0.05

    def test_loss_outcome_when_pnl_negative(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        repo.log_close(
            week_date="2026-05-12", symbol="ETH",
            entry_price_brl=18_000.0, exit_price_brl=17_000.0,
            quantity=1.0, stop_loss_brl=17_500.0,
        )
        row = db_conn.execute("SELECT outcome FROM performance_log").fetchone()
        assert row["outcome"] == "loss"

    def test_breakeven_outcome_when_pnl_zero(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        repo.log_close(
            week_date="2026-05-12", symbol="SOL",
            entry_price_brl=750.0, exit_price_brl=750.0,
            quantity=10.0, stop_loss_brl=700.0,
        )
        row = db_conn.execute("SELECT outcome FROM performance_log").fetchone()
        assert row["outcome"] == "breakeven"

    def test_r_multiple_calculated_correctly(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        # entry=320k, stop=310k → risk per unit = 10k
        # exit=340k → gain per unit = 20k → R = 20k/10k = 2.0
        repo.log_close(
            week_date="2026-05-12", symbol="BTC",
            entry_price_brl=320_000.0, exit_price_brl=340_000.0,
            quantity=0.05, stop_loss_brl=310_000.0,
        )
        row = db_conn.execute("SELECT r_multiple FROM performance_log").fetchone()
        assert row["r_multiple"] == pytest.approx(2.0)

    def test_negative_r_multiple_on_loss(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        # entry=320k, stop=310k → risk=10k; exit=310k → loss=10k → R = -1.0
        repo.log_close(
            week_date="2026-05-12", symbol="BTC",
            entry_price_brl=320_000.0, exit_price_brl=310_000.0,
            quantity=0.05, stop_loss_brl=310_000.0,
        )
        row = db_conn.execute("SELECT r_multiple FROM performance_log").fetchone()
        assert row["r_multiple"] == pytest.approx(-1.0)

    def test_pnl_pct_calculated(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        repo.log_close(
            week_date="2026-05-12", symbol="BTC",
            entry_price_brl=320_000.0, exit_price_brl=330_000.0,
            quantity=0.05, stop_loss_brl=310_000.0,
        )
        row = db_conn.execute("SELECT pnl_pct FROM performance_log").fetchone()
        # (330k - 320k) / 320k = 3.125%
        assert row["pnl_pct"] == pytest.approx(3.125)


# ─── get_summary ──────────────────────────────────────────────────────────────

class TestGetSummary:
    def _seed_trades(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        # 3 wins, 1 loss, 1 open
        repo.log_close("2026-05-12", "BTC",  320_000, 330_000, 0.05, 310_000)  # win R=1.0
        repo.log_close("2026-05-12", "ETH",   18_000,  19_000, 1.0,  17_000)   # win R=1.0
        repo.log_close("2026-05-12", "SOL",     750,     850, 10.0,    700)     # win R=2.0
        repo.log_close("2026-05-12", "BNB",    1_500,   1_400, 2.0,  1_450)    # loss R=-2.0
        # open trade (no exit yet)
        db_conn.execute(
            "INSERT INTO performance_log (week_date, symbol, entry_price_brl, quantity, outcome) "
            "VALUES ('2026-05-19', 'MATIC', 3.50, 100, 'open')"
        )
        db_conn.commit()
        return repo

    def test_win_rate_correct(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = self._seed_trades(db_conn)
        summary = repo.get_summary()
        # 3 wins / 4 closed = 75%
        assert summary.win_rate_pct == pytest.approx(75.0)

    def test_total_trades_excludes_open(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = self._seed_trades(db_conn)
        summary = repo.get_summary()
        assert summary.total_trades == 4

    def test_open_trades_counted_separately(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = self._seed_trades(db_conn)
        summary = repo.get_summary()
        assert summary.open_trades == 1

    def test_avg_r_multiple_calculated(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = self._seed_trades(db_conn)
        summary = repo.get_summary()
        # R values: 1.0, 1.0, 2.0, -2.0 → avg = 2/4 = 0.5
        assert summary.avg_r_multiple == pytest.approx(0.5)

    def test_total_pnl_brl_correct(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = self._seed_trades(db_conn)
        summary = repo.get_summary()
        # BTC: (330k-320k)*0.05 = 500
        # ETH: (19k-18k)*1.0   = 1000
        # SOL: (850-750)*10     = 1000
        # BNB: (1400-1500)*2    = -200
        assert summary.total_pnl_brl == pytest.approx(2_300.0)

    def test_empty_summary_when_no_trades(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        summary = repo.get_summary()
        assert summary.total_trades == 0
        assert summary.win_rate_pct == 0.0
        assert summary.avg_r_multiple == 0.0
        assert summary.total_pnl_brl == 0.0


# ─── Monthly income goal progress ─────────────────────────────────────────────

class TestIncomeGoalProgress:
    def test_monthly_pnl_returns_only_current_month(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        repo.log_close("2026-04-30", "BTC", 300_000, 310_000, 0.05, 290_000)  # April
        repo.log_close("2026-05-12", "ETH",  18_000,  19_000, 1.0,  17_000)  # May
        may_pnl = repo.get_monthly_pnl(year=2026, month=5)
        assert may_pnl == pytest.approx(1_000.0)  # only ETH May trade

    def test_income_goal_progress_pct(self, db_conn):
        from crypto_advisor.db.repository import PerformanceRepository
        repo = PerformanceRepository(db_conn)
        repo.log_close("2026-05-12", "BTC", 320_000, 330_000, 0.05, 310_000)  # +500 BRL
        progress = repo.get_income_goal_progress(year=2026, month=5, goal_brl=3_000.0)
        assert progress == pytest.approx(500.0 / 3_000.0 * 100, rel=0.01)
