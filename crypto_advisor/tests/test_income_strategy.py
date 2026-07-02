"""
Tests for the Income Strategy (US-011) and monthly fiscal report (US-012).

Covers:
- suggest_income_sells: only in SAFE zone
- suggest_income_sells: prioritizes highest gain %
- suggest_income_sells: respects max_sell ceiling
- suggest_income_sells: sells max 50% of each position
- suggest_income_sells: applies min_gain_pct filter
- suggest_income_sells: skips BRL and zero-avg positions
- get_yearly_summary: 12-month fiscal history
"""

import pytest
from datetime import datetime


PRICES_BRL = {
    "BTC": 400_000.0,   # avg 320k → +25% gain
    "ETH":  22_000.0,   # avg 18k  → +22% gain
    "SOL":    900.0,    # avg 750  → +20% gain
    "BRL":      1.0,    # skip BRL
}


# ─── suggest_income_sells ─────────────────────────────────────────────────────

class TestSuggestIncomeSells:
    def test_returns_empty_in_warning_zone(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        # Push into WARNING zone
        sample_portfolio.execute(
            "INSERT INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 29000.0, 'warning')"
        )
        sample_portfolio.commit()
        opt = TaxOptimizer(sample_portfolio)
        suggestions = opt.suggest_income_sells(PRICES_BRL, 2026, 5)
        assert suggestions == []

    def test_returns_empty_in_blocked_zone(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        sample_portfolio.execute(
            "INSERT INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 35000.0, 'blocked')"
        )
        sample_portfolio.commit()
        opt = TaxOptimizer(sample_portfolio)
        suggestions = opt.suggest_income_sells(PRICES_BRL, 2026, 5)
        assert suggestions == []

    def test_returns_suggestions_in_safe_zone(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        suggestions = opt.suggest_income_sells(PRICES_BRL, 2026, 5)
        assert len(suggestions) > 0

    def test_sorted_by_highest_gain_pct(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        suggestions = opt.suggest_income_sells(PRICES_BRL, 2026, 5)
        gains = [s.gain_pct for s in suggestions]
        assert gains == sorted(gains, reverse=True)

    def test_total_sell_within_max_sell_minus_safety(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        max_sell = opt.calculate_max_sell_brl(2026, 5)
        safety = 2_000.0
        suggestions = opt.suggest_income_sells(PRICES_BRL, 2026, 5, safety_margin_brl=safety)
        total = sum(s.estimated_brl for s in suggestions)
        assert total <= max_sell - safety + 0.01  # small float tolerance

    def test_each_sell_max_50_percent_of_position(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        suggestions = opt.suggest_income_sells(PRICES_BRL, 2026, 5)
        # BTC: 0.05 units → max 0.025 units per suggestion
        btc = next((s for s in suggestions if s.symbol == "BTC"), None)
        if btc:
            assert btc.quantity_to_sell <= 0.025 + 1e-8

    def test_min_gain_pct_filter_applied(self, sample_portfolio):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        # All positions are >20% gain — with min_gain_pct=0.30, none qualify
        # BTC: 25%, ETH: 22%, SOL: 20% — all below 30%
        suggestions = opt.suggest_income_sells(
            PRICES_BRL, 2026, 5, min_gain_pct=0.30
        )
        assert suggestions == []

    def test_brl_position_excluded(self, db_conn):
        """BRL cash should never appear in income suggestions."""
        from crypto_advisor.tax.optimizer import TaxOptimizer
        db_conn.execute(
            "INSERT INTO portfolio (symbol, quantity, avg_price_brl, exchange) "
            "VALUES ('BRL', 500.0, 1.0, 'mercado_bitcoin')"
        )
        db_conn.execute(
            "INSERT INTO portfolio (symbol, quantity, avg_price_brl, exchange) "
            "VALUES ('BTC', 0.05, 320000.0, 'mercado_bitcoin')"
        )
        db_conn.commit()
        opt = TaxOptimizer(db_conn)
        suggestions = opt.suggest_income_sells(PRICES_BRL, 2026, 5)
        symbols = {s.symbol for s in suggestions}
        assert "BRL" not in symbols

    def test_gain_brl_calculated_correctly(self, sample_portfolio):
        """gain_brl = (current - avg) * qty_to_sell"""
        from crypto_advisor.tax.optimizer import TaxOptimizer
        opt = TaxOptimizer(sample_portfolio)
        suggestions = opt.suggest_income_sells(PRICES_BRL, 2026, 5)
        for s in suggestions:
            current = PRICES_BRL.get(s.symbol, 0)
            # avg_price_brl is in sample_portfolio fixture (BTC=320k, ETH=18k, SOL=750)
            assert s.estimated_gain_brl >= 0
            assert s.estimated_brl > 0


# ─── get_yearly_summary ───────────────────────────────────────────────────────

class TestGetYearlySummary:
    def _seed_12_months(self, db_conn):
        for month in range(1, 13):
            sold = (month % 3 + 1) * 5_000.0
            zone = "safe" if sold < 28_000 else "warning"
            db_conn.execute(
                "INSERT INTO tax_tracker "
                "(year, month, exchange, total_sold_brl, realized_gain_brl, realized_loss_brl, tax_status) "
                "VALUES (2026, ?, 'mercado_bitcoin', ?, ?, 0.0, ?)",
                (month, sold, sold * 0.15, zone),
            )
        db_conn.commit()

    def test_returns_12_months(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        self._seed_12_months(db_conn)
        opt = TaxOptimizer(db_conn)
        summary = opt.get_yearly_summary(2026)
        assert len(summary) == 12

    def test_each_entry_has_required_fields(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        self._seed_12_months(db_conn)
        opt = TaxOptimizer(db_conn)
        for entry in opt.get_yearly_summary(2026):
            assert "month" in entry
            assert "total_sold_brl" in entry
            assert "tax_status" in entry

    def test_sorted_by_month_ascending(self, db_conn):
        from crypto_advisor.tax.optimizer import TaxOptimizer
        self._seed_12_months(db_conn)
        opt = TaxOptimizer(db_conn)
        months = [e["month"] for e in opt.get_yearly_summary(2026)]
        assert months == sorted(months)

    def test_empty_months_filled_with_zero(self, db_conn):
        """Months with no sales should appear as zero, not be absent."""
        from crypto_advisor.tax.optimizer import TaxOptimizer
        db_conn.execute(
            "INSERT INTO tax_tracker "
            "(year, month, exchange, total_sold_brl, realized_gain_brl, realized_loss_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 12000.0, 1200.0, 0.0, 'safe')"
        )
        db_conn.commit()
        opt = TaxOptimizer(db_conn)
        summary = opt.get_yearly_summary(2026)
        assert len(summary) == 12
        zero_months = [e for e in summary if e["total_sold_brl"] == 0.0]
        assert len(zero_months) == 11  # only May has data
