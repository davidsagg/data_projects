"""
Tests for the TaxOptimizer class (real implementation with SQLite).

Covers:
- get_monthly_status: reads from DB, returns TaxStatus
- add_sale: updates accumulator, returns new zone, detects zone transition
- sync_from_trades: rebuilds tax_tracker from trades table
- get_loss_harvest_candidates: returns sorted candidates
- build_tax_context: assembles TaxContext for Claude prompt
- calculate_max_sell_brl: income strategy helper
"""

import pytest
from datetime import datetime, timezone


CURRENT_PRICES_BRL = {
    "BTC": 300_000.0,   # avg 320k → loss 6.25%
    "ETH": 18_500.0,    # avg 18k  → gain +2.8%
    "SOL": 680.0,       # avg 750  → loss 9.3%
}


# ─── get_monthly_status ───────────────────────────────────────────────────────

class TestGetMonthlyStatus:
    def test_returns_safe_when_no_record(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(db_conn)
        status = opt.get_monthly_status(2026, 5)
        assert status.zone == "safe"
        assert status.total_sold_brl == 0.0

    def test_returns_correct_zone_from_db(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        db_conn.execute(
            "INSERT INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 29500.0, 'warning')"
        )
        db_conn.commit()
        opt = TaxOptimizer(db_conn)
        status = opt.get_monthly_status(2026, 5)
        assert status.zone == "warning"
        assert status.total_sold_brl == pytest.approx(29_500.0)

    def test_margin_available_calculated_correctly(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        db_conn.execute(
            "INSERT INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 10000.0, 'safe')"
        )
        db_conn.commit()
        opt = TaxOptimizer(db_conn)
        status = opt.get_monthly_status(2026, 5)
        assert status.margin_available_brl == pytest.approx(25_000.0)

    def test_default_exchange_is_mercado_bitcoin(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(db_conn)
        status = opt.get_monthly_status(2026, 5)
        assert status.limit_brl == pytest.approx(35_000.0)


# ─── add_sale ─────────────────────────────────────────────────────────────────

class TestAddSale:
    def test_add_sale_updates_total_in_db(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(db_conn)
        opt.add_sale(total_brl=5_000.0, gain_brl=500.0, year=2026, month=5)
        row = db_conn.execute(
            "SELECT total_sold_brl FROM tax_tracker WHERE year=2026 AND month=5"
        ).fetchone()
        assert row["total_sold_brl"] == pytest.approx(5_000.0)

    def test_add_sale_accumulates_on_second_call(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(db_conn)
        opt.add_sale(5_000.0, 500.0, 2026, 5)
        opt.add_sale(8_000.0, 800.0, 2026, 5)
        row = db_conn.execute(
            "SELECT total_sold_brl FROM tax_tracker WHERE year=2026 AND month=5"
        ).fetchone()
        assert row["total_sold_brl"] == pytest.approx(13_000.0)

    def test_add_sale_returns_new_status(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(db_conn)
        status = opt.add_sale(5_000.0, 500.0, 2026, 5)
        assert status.zone == "safe"

    def test_add_sale_transitions_to_warning(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(db_conn)
        opt.add_sale(25_000.0, 2_000.0, 2026, 5)
        status = opt.add_sale(5_000.0, 500.0, 2026, 5)
        assert status.zone == "warning"

    def test_add_sale_transitions_to_blocked(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(db_conn)
        opt.add_sale(34_000.0, 3_000.0, 2026, 5)
        status = opt.add_sale(2_000.0, 200.0, 2026, 5)
        assert status.zone == "blocked"

    def test_add_loss_does_not_change_total_sold(self, db_conn):
        """Loss harvesting: selling at a loss still adds to total_sold_brl (it's volume, not gain)."""
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(db_conn)
        opt.add_sale(total_brl=3_000.0, gain_brl=-500.0, year=2026, month=5)
        row = db_conn.execute(
            "SELECT total_sold_brl FROM tax_tracker WHERE year=2026 AND month=5"
        ).fetchone()
        assert row["total_sold_brl"] == pytest.approx(3_000.0)


# ─── sync_from_trades ─────────────────────────────────────────────────────────

class TestSyncFromTrades:
    def test_sync_rebuilds_correct_total(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        from crypto_advisor.models import PortfolioPosition

        # Insert raw trades (sells in May 2026)
        db_conn.executemany(
            "INSERT INTO trades (symbol, side, quantity, price_brl, total_brl, fee_brl, "
            "exchange, traded_at) VALUES (?,?,?,?,?,?,?,?)",
            [
                ("BTC", "sell", 0.01, 320_000, 3_200.0, 9.6,
                 "mercado_bitcoin", "2026-05-03T14:00:00"),
                ("ETH", "sell", 0.5,  18_000,  9_000.0, 4.5,
                 "mercado_bitcoin", "2026-05-07T11:00:00"),
                ("BTC", "buy",  0.02, 310_000, 6_200.0, 18.6,
                 "mercado_bitcoin", "2026-05-10T09:00:00"),  # buy — should not count
            ],
        )
        db_conn.commit()

        opt = TaxOptimizer(db_conn)
        opt.sync_from_trades(year=2026, month=5)

        row = db_conn.execute(
            "SELECT total_sold_brl FROM tax_tracker WHERE year=2026 AND month=5"
        ).fetchone()
        assert row["total_sold_brl"] == pytest.approx(12_200.0)  # 3200 + 9000


# ─── get_loss_harvest_candidates ─────────────────────────────────────────────

class TestLossHarvestCandidates:
    def test_returns_only_positions_in_loss(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        candidates = opt.get_loss_harvest_candidates(CURRENT_PRICES_BRL)
        symbols = [c.symbol for c in candidates]
        assert "BTC" in symbols
        assert "SOL" in symbols
        assert "ETH" not in symbols

    def test_candidates_sorted_by_loss_pct_desc(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        candidates = opt.get_loss_harvest_candidates(CURRENT_PRICES_BRL)
        losses = [c.loss_pct for c in candidates]
        assert losses == sorted(losses, reverse=True)

    def test_empty_when_all_in_profit(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        from crypto_advisor.models import PortfolioPosition
        db_conn.executemany(
            "INSERT INTO portfolio (symbol, quantity, avg_price_brl, exchange) VALUES (?,?,?,?)",
            [("BTC", 0.05, 250_000.0, "mercado_bitcoin")],  # avg below current
        )
        db_conn.commit()
        opt = TaxOptimizer(db_conn)
        candidates = opt.get_loss_harvest_candidates({"BTC": 300_000.0})
        assert candidates == []

    def test_min_loss_pct_filter_respected(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        # With 20% min loss, neither BTC (-6.25%) nor SOL (-9.3%) qualify
        candidates = opt.get_loss_harvest_candidates(CURRENT_PRICES_BRL, min_loss_pct=0.20)
        assert candidates == []


# ─── build_tax_context ────────────────────────────────────────────────────────

class TestBuildTaxContext:
    def test_returns_tax_context_model(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        from crypto_advisor.models import TaxContext
        opt = TaxOptimizer(sample_portfolio)
        ctx = opt.build_tax_context(2026, 5, CURRENT_PRICES_BRL)
        assert isinstance(ctx, TaxContext)

    def test_zone_safe_when_no_sales(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        ctx = opt.build_tax_context(2026, 5, CURRENT_PRICES_BRL)
        assert ctx.zone == "safe"

    def test_loss_harvest_candidates_included_in_context(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        ctx = opt.build_tax_context(2026, 5, CURRENT_PRICES_BRL)
        assert "BTC" in ctx.loss_harvest_candidates or "SOL" in ctx.loss_harvest_candidates

    def test_instruction_reflects_zone(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        db_conn.execute(
            "INSERT INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 35000.0, 'blocked')"
        )
        db_conn.commit()
        opt = TaxOptimizer(db_conn)
        ctx = opt.build_tax_context(2026, 5, {})
        assert ctx.zone == "blocked"
        assert "venda" in ctx.instruction.lower() or "sell" in ctx.instruction.lower()


# ─── calculate_max_sell_brl ───────────────────────────────────────────────────

class TestCalculateMaxSellBrl:
    def test_full_margin_when_nothing_sold(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(db_conn)
        max_sell = opt.calculate_max_sell_brl(2026, 5)
        assert max_sell == pytest.approx(28_000.0)

    def test_reduced_margin_when_partially_sold(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        db_conn.execute(
            "INSERT INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 15000.0, 'safe')"
        )
        db_conn.commit()
        opt = TaxOptimizer(db_conn)
        max_sell = opt.calculate_max_sell_brl(2026, 5)
        assert max_sell == pytest.approx(13_000.0)

    def test_zero_when_above_warning_threshold(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        db_conn.execute(
            "INSERT INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 29000.0, 'warning')"
        )
        db_conn.commit()
        opt = TaxOptimizer(db_conn)
        assert opt.calculate_max_sell_brl(2026, 5) == 0.0
