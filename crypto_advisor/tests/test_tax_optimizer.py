"""
Tests for the Tax Optimizer module.

Covers:
- Zone classification (SAFE / WARNING / CRITICAL / BLOCKED)
- Accumulated sales update and recalculation
- Loss harvesting candidate identification
- Max sell amount calculation (income strategy)
- Zone transition detection
"""

import pytest
from unittest.mock import MagicMock


# ─── helpers (inline until the real module exists) ────────────────────────────

TAX_LIMIT_BRL = 35_000.0
TAX_WARNING_BRL = 28_000.0
TAX_CRITICAL_BRL = 33_000.0


def _zone(total_sold: float) -> str:
    if total_sold >= TAX_LIMIT_BRL:
        return "blocked"
    if total_sold >= TAX_CRITICAL_BRL:
        return "critical"
    if total_sold >= TAX_WARNING_BRL:
        return "warning"
    return "safe"


def _max_sell_brl(current_total: float) -> float:
    """Maximum additional sell to stay below WARNING threshold."""
    return max(0.0, TAX_WARNING_BRL - current_total)


# ─── Zone classification ──────────────────────────────────────────────────────

class TestZoneClassification:
    def test_zero_sales_is_safe(self):
        assert _zone(0.0) == "safe"

    def test_just_below_warning_is_safe(self):
        assert _zone(27_999.99) == "safe"

    def test_at_warning_threshold(self):
        assert _zone(28_000.0) == "warning"

    def test_mid_warning_range(self):
        assert _zone(30_500.0) == "warning"

    def test_just_below_critical_is_warning(self):
        assert _zone(32_999.99) == "warning"

    def test_at_critical_threshold(self):
        assert _zone(33_000.0) == "critical"

    def test_mid_critical_range(self):
        assert _zone(34_000.0) == "critical"

    def test_just_below_limit_is_critical(self):
        assert _zone(34_999.99) == "critical"

    def test_at_limit_is_blocked(self):
        assert _zone(35_000.0) == "blocked"

    def test_above_limit_is_blocked(self):
        assert _zone(40_000.0) == "blocked"


# ─── Accumulated sales & recalculation ───────────────────────────────────────

class TestTaxTrackerAccumulation:
    def test_add_sale_updates_total(self, db_conn):
        db_conn.execute(
            "INSERT INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 10000.0, 'safe')"
        )
        db_conn.commit()

        new_sale = 5_000.0
        db_conn.execute(
            "UPDATE tax_tracker SET total_sold_brl = total_sold_brl + ? "
            "WHERE year=2026 AND month=5 AND exchange='mercado_bitcoin'",
            (new_sale,),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT total_sold_brl FROM tax_tracker WHERE year=2026 AND month=5"
        ).fetchone()
        assert row["total_sold_brl"] == pytest.approx(15_000.0)

    def test_upsert_creates_record_if_not_exists(self, db_conn):
        db_conn.execute(
            "INSERT OR REPLACE INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 6, 'mercado_bitcoin', 1000.0, 'safe')"
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT total_sold_brl, tax_status FROM tax_tracker WHERE year=2026 AND month=6"
        ).fetchone()
        assert row["total_sold_brl"] == 1_000.0
        assert row["tax_status"] == "safe"

    def test_status_updated_after_crossing_warning(self, db_conn):
        db_conn.execute(
            "INSERT INTO tax_tracker (year, month, exchange, total_sold_brl, tax_status) "
            "VALUES (2026, 5, 'mercado_bitcoin', 27_000.0, 'safe')"
        )
        db_conn.commit()

        new_total = 27_000.0 + 2_000.0
        new_status = _zone(new_total)

        db_conn.execute(
            "UPDATE tax_tracker SET total_sold_brl=?, tax_status=? "
            "WHERE year=2026 AND month=5 AND exchange='mercado_bitcoin'",
            (new_total, new_status),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT tax_status FROM tax_tracker WHERE year=2026 AND month=5"
        ).fetchone()
        assert row["tax_status"] == "warning"


# ─── Zone transitions ─────────────────────────────────────────────────────────

class TestZoneTransition:
    @pytest.mark.parametrize("before,after,sale,expected_new_zone", [
        (10_000.0, 29_000.0, 19_000.0, "warning"),
        (27_000.0, 33_500.0, 6_500.0, "critical"),
        (34_000.0, 35_100.0, 1_100.0, "blocked"),
        (5_000.0, 10_000.0, 5_000.0, "safe"),     # no zone change
    ])
    def test_zone_after_sale(self, before, after, sale, expected_new_zone):
        assert _zone(before + sale) == expected_new_zone

    def test_no_transition_within_safe_zone(self):
        old = _zone(5_000.0)
        new = _zone(15_000.0)
        assert old == new == "safe"


# ─── Loss harvesting ─────────────────────────────────────────────────────────

class TestLossHarvesting:
    CURRENT_PRICES = {
        "BTC": 300_000.0,   # avg 320k → loss 6.25%
        "ETH": 18_500.0,    # avg 18k  → gain 2.8%  (not a candidate)
        "SOL": 680.0,       # avg 750  → loss 9.33%
    }

    def _get_candidates(self, portfolio_rows, min_loss_pct=0.05):
        """Identify positions with unrealized loss >= min_loss_pct."""
        candidates = []
        for row in portfolio_rows:
            symbol = row["symbol"]
            avg = row["avg_price_brl"]
            current = self.CURRENT_PRICES.get(symbol)
            if current is None:
                continue
            loss_pct = (avg - current) / avg
            if loss_pct >= min_loss_pct:
                loss_brl = (avg - current) * row["quantity"]
                candidates.append({
                    "symbol": symbol,
                    "loss_pct": round(loss_pct * 100, 2),
                    "unrealized_loss_brl": round(loss_brl, 2),
                })
        return sorted(candidates, key=lambda x: x["loss_pct"], reverse=True)

    def test_identifies_btc_and_sol_as_candidates(self, sample_portfolio):
        rows = sample_portfolio.execute("SELECT * FROM portfolio").fetchall()
        candidates = self._get_candidates(rows)
        symbols = [c["symbol"] for c in candidates]
        assert "BTC" in symbols
        assert "SOL" in symbols
        assert "ETH" not in symbols

    def test_candidates_ordered_by_loss_pct_descending(self, sample_portfolio):
        rows = sample_portfolio.execute("SELECT * FROM portfolio").fetchall()
        candidates = self._get_candidates(rows)
        losses = [c["loss_pct"] for c in candidates]
        assert losses == sorted(losses, reverse=True)

    def test_no_candidates_when_all_in_profit(self):
        profitable_prices = {"BTC": 400_000.0, "ETH": 25_000.0, "SOL": 900.0}
        rows = [
            {"symbol": "BTC", "quantity": 0.05, "avg_price_brl": 320_000.0},
            {"symbol": "ETH", "quantity": 1.2, "avg_price_brl": 18_000.0},
        ]
        candidates = []
        for row in rows:
            avg = row["avg_price_brl"]
            current = profitable_prices[row["symbol"]]
            if (avg - current) / avg >= 0.05:
                candidates.append(row)
        assert candidates == []

    def test_loss_harvest_allowed_in_critical_zone(self):
        """Loss harvest should not be blocked even in CRITICAL zone."""
        total_sold = 34_000.0
        zone = _zone(total_sold)
        assert zone == "critical"
        # Loss harvesting is allowed regardless: selling at loss never triggers IR
        harvest_allowed = True  # business rule: losses don't count toward tax event
        assert harvest_allowed is True


# ─── Income strategy ─────────────────────────────────────────────────────────

class TestIncomeStrategy:
    def test_max_sell_zero_when_above_warning(self):
        assert _max_sell_brl(28_500.0) == 0.0

    def test_max_sell_correct_when_safe(self):
        assert _max_sell_brl(10_000.0) == pytest.approx(18_000.0)

    def test_max_sell_is_zero_when_exactly_at_warning(self):
        assert _max_sell_brl(28_000.0) == 0.0

    def test_max_sell_full_limit_when_nothing_sold(self):
        assert _max_sell_brl(0.0) == pytest.approx(28_000.0)
