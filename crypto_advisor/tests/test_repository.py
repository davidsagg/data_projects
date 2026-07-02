"""
Tests for the Repository layer (SQLite CRUD operations).

Uses in-memory SQLite via the db_conn fixture in conftest.py.

Covers:
- PortfolioRepository: upsert, get_all, get_by_symbol
- TradeRepository: add, get_monthly_sells, get_latest_traded_at, dedup
- TaxRepository: get_monthly, upsert, monthly_total
- RecommendationRepository: save, update_status, get_pending
"""

import pytest
from datetime import datetime, timezone


# ─── PortfolioRepository ──────────────────────────────────────────────────────

class TestPortfolioRepository:
    def test_upsert_inserts_new_position(self, db_conn):
        from crypto_advisor.db.repository import PortfolioRepository
        from crypto_advisor.models import PortfolioPosition
        repo = PortfolioRepository(db_conn)
        pos = PortfolioPosition(symbol="BTC", quantity=0.05, avg_price_brl=320_000.0)
        repo.upsert(pos)
        rows = db_conn.execute("SELECT * FROM portfolio WHERE symbol='BTC'").fetchall()
        assert len(rows) == 1
        assert rows[0]["quantity"] == pytest.approx(0.05)

    def test_upsert_updates_existing_position(self, db_conn):
        from crypto_advisor.db.repository import PortfolioRepository
        from crypto_advisor.models import PortfolioPosition
        repo = PortfolioRepository(db_conn)
        repo.upsert(PortfolioPosition(symbol="BTC", quantity=0.01, avg_price_brl=300_000.0))
        repo.upsert(PortfolioPosition(symbol="BTC", quantity=0.05, avg_price_brl=320_000.0))
        rows = db_conn.execute("SELECT * FROM portfolio WHERE symbol='BTC'").fetchall()
        assert len(rows) == 1
        assert rows[0]["quantity"] == pytest.approx(0.05)
        assert rows[0]["avg_price_brl"] == pytest.approx(320_000.0)

    def test_get_all_returns_all_positions(self, sample_portfolio):
        from crypto_advisor.db.repository import PortfolioRepository
        repo = PortfolioRepository(sample_portfolio)
        positions = repo.get_all()
        assert len(positions) == 3
        symbols = {p.symbol for p in positions}
        assert {"BTC", "ETH", "SOL"} == symbols

    def test_get_by_symbol_returns_correct_position(self, sample_portfolio):
        from crypto_advisor.db.repository import PortfolioRepository
        repo = PortfolioRepository(sample_portfolio)
        btc = repo.get_by_symbol("BTC")
        assert btc is not None
        assert btc.quantity == pytest.approx(0.05)

    def test_get_by_symbol_returns_none_when_not_found(self, db_conn):
        from crypto_advisor.db.repository import PortfolioRepository
        repo = PortfolioRepository(db_conn)
        assert repo.get_by_symbol("DOGE") is None

    def test_upsert_bulk_replaces_all_positions(self, sample_portfolio):
        from crypto_advisor.db.repository import PortfolioRepository
        from crypto_advisor.models import PortfolioPosition
        repo = PortfolioRepository(sample_portfolio)
        new_positions = [
            PortfolioPosition(symbol="BTC", quantity=0.10, avg_price_brl=330_000.0),
        ]
        repo.upsert_bulk(new_positions)
        assert repo.get_by_symbol("BTC").quantity == pytest.approx(0.10)


# ─── TradeRepository ──────────────────────────────────────────────────────────

class TestTradeRepository:
    def _make_trade(self, **kwargs):
        from crypto_advisor.models import TradeRecord
        defaults = dict(
            symbol="BTC", side="sell", quantity=0.01,
            price_brl=320_000.0, total_brl=3_200.0, fee_brl=9.6,
            exchange="mercado_bitcoin",
            traded_at=datetime(2026, 5, 3, 14, 0, 0, tzinfo=timezone.utc),
        )
        return TradeRecord(**{**defaults, **kwargs})

    def test_add_trade_persists_to_db(self, db_conn):
        from crypto_advisor.db.repository import TradeRepository
        repo = TradeRepository(db_conn)
        repo.add(self._make_trade())
        rows = db_conn.execute("SELECT * FROM trades").fetchall()
        assert len(rows) == 1

    def test_get_monthly_sells_returns_only_sell_side(self, db_conn):
        from crypto_advisor.db.repository import TradeRepository
        repo = TradeRepository(db_conn)
        repo.add(self._make_trade(side="sell", total_brl=3_200.0))
        repo.add(self._make_trade(side="buy",  symbol="ETH", total_brl=18_000.0,
                                   price_brl=18_000.0, quantity=1.0,
                                   traded_at=datetime(2026, 5, 4, tzinfo=timezone.utc)))
        sells = repo.get_monthly_sells(year=2026, month=5)
        assert len(sells) == 1
        assert sells[0].side == "sell"

    def test_get_monthly_sells_sums_correctly(self, db_conn):
        from crypto_advisor.db.repository import TradeRepository
        repo = TradeRepository(db_conn)
        for i in range(3):
            repo.add(self._make_trade(
                total_brl=5_000.0 + i * 1_000,
                traded_at=datetime(2026, 5, i + 1, tzinfo=timezone.utc),
            ))
        sells = repo.get_monthly_sells(year=2026, month=5)
        total = sum(t.total_brl for t in sells)
        assert total == pytest.approx(18_000.0)  # 5000 + 6000 + 7000

    def test_get_monthly_sells_excludes_other_months(self, db_conn):
        from crypto_advisor.db.repository import TradeRepository
        repo = TradeRepository(db_conn)
        repo.add(self._make_trade(total_brl=5_000.0,
                                   traded_at=datetime(2026, 5, 1, tzinfo=timezone.utc)))
        repo.add(self._make_trade(total_brl=8_000.0,
                                   traded_at=datetime(2026, 6, 1, tzinfo=timezone.utc)))
        may_sells = repo.get_monthly_sells(year=2026, month=5)
        assert len(may_sells) == 1
        assert may_sells[0].total_brl == pytest.approx(5_000.0)

    def test_get_latest_traded_at_returns_none_when_empty(self, db_conn):
        from crypto_advisor.db.repository import TradeRepository
        repo = TradeRepository(db_conn)
        assert repo.get_latest_traded_at() is None

    def test_get_latest_traded_at_returns_most_recent(self, db_conn):
        from crypto_advisor.db.repository import TradeRepository
        repo = TradeRepository(db_conn)
        repo.add(self._make_trade(traded_at=datetime(2026, 5, 1, tzinfo=timezone.utc)))
        repo.add(self._make_trade(traded_at=datetime(2026, 5, 10, tzinfo=timezone.utc)))
        latest = repo.get_latest_traded_at()
        assert latest is not None
        assert latest.day == 10

    def test_duplicate_trade_not_inserted_twice(self, db_conn):
        from crypto_advisor.db.repository import TradeRepository
        repo = TradeRepository(db_conn)
        trade = self._make_trade()
        repo.add(trade)
        repo.add(trade)  # duplicate
        rows = db_conn.execute("SELECT COUNT(*) as c FROM trades").fetchone()["c"]
        assert rows == 1


# ─── TaxRepository ────────────────────────────────────────────────────────────

class TestTaxRepository:
    def test_get_monthly_returns_none_when_no_record(self, db_conn):
        from crypto_advisor.db.repository import TaxRepository
        repo = TaxRepository(db_conn)
        assert repo.get_monthly(2026, 5, "mercado_bitcoin") is None

    def test_upsert_creates_record(self, db_conn):
        from crypto_advisor.db.repository import TaxRepository
        repo = TaxRepository(db_conn)
        repo.upsert(year=2026, month=5, exchange="mercado_bitcoin",
                    total_sold_brl=12_000.0, realized_gain_brl=1_500.0,
                    realized_loss_brl=0.0, tax_status="safe")
        record = repo.get_monthly(2026, 5, "mercado_bitcoin")
        assert record is not None
        assert record["total_sold_brl"] == pytest.approx(12_000.0)
        assert record["tax_status"] == "safe"

    def test_upsert_updates_existing_record(self, db_conn):
        from crypto_advisor.db.repository import TaxRepository
        repo = TaxRepository(db_conn)
        repo.upsert(2026, 5, "mercado_bitcoin", 10_000.0, 1_000.0, 0.0, "safe")
        repo.upsert(2026, 5, "mercado_bitcoin", 29_000.0, 2_000.0, 0.0, "warning")
        record = repo.get_monthly(2026, 5, "mercado_bitcoin")
        assert record["total_sold_brl"] == pytest.approx(29_000.0)
        assert record["tax_status"] == "warning"

    def test_different_months_are_independent(self, db_conn):
        from crypto_advisor.db.repository import TaxRepository
        repo = TaxRepository(db_conn)
        repo.upsert(2026, 4, "mercado_bitcoin", 5_000.0, 500.0, 0.0, "safe")
        repo.upsert(2026, 5, "mercado_bitcoin", 30_000.0, 2_000.0, 0.0, "warning")
        apr = repo.get_monthly(2026, 4, "mercado_bitcoin")
        may = repo.get_monthly(2026, 5, "mercado_bitcoin")
        assert apr["total_sold_brl"] == pytest.approx(5_000.0)
        assert may["total_sold_brl"] == pytest.approx(30_000.0)


# ─── RecommendationRepository ─────────────────────────────────────────────────

class TestRecommendationRepository:
    def _make_rec_data(self, symbol="BTC", action="BUY"):
        import json
        raw = {"symbol": symbol, "action": action, "reasoning": "Test", "confidence": "high"}
        return dict(
            week_date="2026-05-12",
            symbol=symbol,
            action=action,
            entry_price_usd=65_000.0,
            stop_loss_usd=62_000.0,
            target_price_usd=71_000.0,
            risk_reward_ratio=2.0,
            confidence="high",
            reasoning="Test setup",
            tax_impact="",
            raw_json=json.dumps(raw),
        )

    def test_save_returns_id(self, db_conn):
        from crypto_advisor.db.repository import RecommendationRepository
        repo = RecommendationRepository(db_conn)
        rec_id = repo.save(**self._make_rec_data())
        assert isinstance(rec_id, int)
        assert rec_id > 0

    def test_saved_recommendation_has_pending_status(self, db_conn):
        from crypto_advisor.db.repository import RecommendationRepository
        repo = RecommendationRepository(db_conn)
        rec_id = repo.save(**self._make_rec_data())
        row = db_conn.execute("SELECT status FROM recommendations WHERE id=?", (rec_id,)).fetchone()
        assert row["status"] == "pending"

    def test_get_pending_returns_only_pending(self, db_conn):
        from crypto_advisor.db.repository import RecommendationRepository
        repo = RecommendationRepository(db_conn)
        id1 = repo.save(**self._make_rec_data("BTC", "BUY"))
        id2 = repo.save(**self._make_rec_data("ETH", "HOLD"))
        repo.update_status(id1, "approved")
        pending = repo.get_pending()
        pending_ids = [r["id"] for r in pending]
        assert id1 not in pending_ids
        assert id2 in pending_ids

    def test_update_status_sets_reviewed_at(self, db_conn):
        from crypto_advisor.db.repository import RecommendationRepository
        repo = RecommendationRepository(db_conn)
        rec_id = repo.save(**self._make_rec_data())
        repo.update_status(rec_id, "rejected")
        row = db_conn.execute(
            "SELECT status, reviewed_at FROM recommendations WHERE id=?", (rec_id,)
        ).fetchone()
        assert row["status"] == "rejected"
        assert row["reviewed_at"] is not None

    def test_save_multiple_recommendations_for_same_week(self, db_conn):
        from crypto_advisor.db.repository import RecommendationRepository
        repo = RecommendationRepository(db_conn)
        repo.save(**self._make_rec_data("BTC", "BUY"))
        repo.save(**self._make_rec_data("ETH", "SELL"))
        repo.save(**self._make_rec_data("SOL", "HOLD"))
        pending = repo.get_pending()
        assert len(pending) == 3
