"""Shared fixtures for all test modules."""

import sqlite3
import pytest

from crypto_advisor.db.schema import init_db


@pytest.fixture
def db_conn():
    """In-memory SQLite database initialised with the full schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    from crypto_advisor.db.schema import DDL, INDEXES
    conn.executescript(DDL)
    conn.executescript(INDEXES)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_portfolio(db_conn):
    """Seed portfolio table with a few positions."""
    db_conn.executemany(
        "INSERT INTO portfolio (symbol, quantity, avg_price_brl, exchange) VALUES (?,?,?,?)",
        [
            ("BTC", 0.05, 320_000.0, "mercado_bitcoin"),
            ("ETH", 1.2, 18_000.0, "mercado_bitcoin"),
            ("SOL", 10.0, 750.0, "mercado_bitcoin"),
        ],
    )
    db_conn.commit()
    return db_conn
