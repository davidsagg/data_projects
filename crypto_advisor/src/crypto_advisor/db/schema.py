"""SQLite schema definitions and database initialisation."""

import sqlite3
from pathlib import Path

DDL = """
-- ─────────────────────────────────────────────────────────────────────────────
-- portfolio: posições abertas sincronizadas com a exchange
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol        TEXT    NOT NULL,
    quantity      REAL    NOT NULL,
    avg_price_brl REAL    NOT NULL,
    exchange      TEXT    NOT NULL DEFAULT 'mercado_bitcoin',
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, exchange)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- recommendations: saídas do Claude para aprovação human-in-the-loop
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recommendations (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    week_date          DATE    NOT NULL,
    symbol             TEXT    NOT NULL,
    action             TEXT    NOT NULL CHECK(action IN ('BUY','SELL','HOLD','SKIP')),
    entry_price_usd    REAL,
    stop_loss_usd      REAL,
    target_price_usd   REAL,
    risk_reward_ratio  REAL,
    confidence         TEXT    CHECK(confidence IN ('high','medium','low')),
    timeframe          TEXT    NOT NULL DEFAULT 'swing',
    reasoning          TEXT,
    tax_impact         TEXT,
    raw_json           TEXT    NOT NULL,
    status             TEXT    NOT NULL DEFAULT 'pending'
                               CHECK(status IN ('pending','approved','rejected','executed','cancelled')),
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at        TIMESTAMP,
    reviewed_by        TEXT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- trades: execuções reais (importadas da exchange)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trades (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol            TEXT    NOT NULL,
    side              TEXT    NOT NULL CHECK(side IN ('buy','sell')),
    quantity          REAL    NOT NULL,
    price_brl         REAL    NOT NULL,
    total_brl         REAL    NOT NULL,
    fee_brl           REAL    NOT NULL DEFAULT 0,
    exchange          TEXT    NOT NULL DEFAULT 'mercado_bitcoin',
    traded_at         TIMESTAMP NOT NULL,
    recommendation_id INTEGER REFERENCES recommendations(id),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, side, quantity, traded_at, exchange)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- tax_tracker: acumulador mensal de vendas por exchange (IN RFB 2.312/2026)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tax_tracker (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    year                INTEGER NOT NULL,
    month               INTEGER NOT NULL,
    exchange            TEXT    NOT NULL DEFAULT 'mercado_bitcoin',
    total_sold_brl      REAL    NOT NULL DEFAULT 0,
    realized_gain_brl   REAL    NOT NULL DEFAULT 0,
    realized_loss_brl   REAL    NOT NULL DEFAULT 0,
    tax_status          TEXT    NOT NULL DEFAULT 'safe'
                                CHECK(tax_status IN ('safe','warning','critical','blocked')),
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year, month, exchange)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- performance_log: métricas de cada trade fechado (win/loss/R-múltiplo)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS performance_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    week_date         DATE    NOT NULL,
    recommendation_id INTEGER REFERENCES recommendations(id),
    symbol            TEXT    NOT NULL,
    entry_price_brl   REAL,
    exit_price_brl    REAL,
    quantity          REAL,
    pnl_brl           REAL,
    pnl_pct           REAL,
    r_multiple        REAL,
    outcome           TEXT    CHECK(outcome IN ('win','loss','breakeven','open')),
    closed_at         TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────────────────────────────────────
-- portfolio_snapshots: série temporal do valor do portfólio (gráfico de evolução)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    total_value_brl REAL    NOT NULL,
    total_cost_brl  REAL    NOT NULL DEFAULT 0,
    captured_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────────────────────────────────────
-- market_snapshots: cache dos dados de mercado usados em cada análise
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,
    timeframe   TEXT    NOT NULL,
    fetched_at  TIMESTAMP NOT NULL,
    ohlcv_json  TEXT    NOT NULL,
    indicators_json TEXT
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_trades_symbol_date    ON trades(symbol, traded_at);
CREATE INDEX IF NOT EXISTS idx_trades_side_date      ON trades(side, traded_at);
CREATE INDEX IF NOT EXISTS idx_tax_tracker_ym        ON tax_tracker(year, month, exchange);
CREATE INDEX IF NOT EXISTS idx_recommendations_week  ON recommendations(week_date, status);
CREATE INDEX IF NOT EXISTS idx_performance_outcome   ON performance_log(outcome, week_date);
CREATE INDEX IF NOT EXISTS idx_snapshots_date        ON portfolio_snapshots(captured_at);
"""


def init_db(db_path: str | Path = "./data/crypto_advisor.db") -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(DDL)
    conn.executescript(INDEXES)
    conn.commit()
    return conn
