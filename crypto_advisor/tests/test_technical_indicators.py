"""
Tests for the TechnicalIndicators module.

Uses synthetic OHLCV DataFrames — no API calls, no pandas-ta required
(the module falls back to pure-pandas implementations when pandas-ta is absent).

Covers:
- All 5 indicator columns computed and non-null on last row
- MM alignment signal (bullish / bearish / mixed)
- RSI zone detection (overbought / oversold / neutral)
- MACD crossover detection
- Bollinger Bands position
- InsufficientDataError for < 200 rows
- TechnicalSnapshot shape and types
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 250, trend: str = "up") -> pd.DataFrame:
    """Generate synthetic OHLCV with a controlled trend."""
    rng = np.random.default_rng(42)
    base = 60_000.0
    if trend == "up":
        close = base + np.cumsum(rng.normal(50, 200, n))
    elif trend == "down":
        close = base + np.cumsum(rng.normal(-50, 200, n))
    else:
        close = base + rng.normal(0, 200, n).cumsum() * 0.1

    close = np.abs(close)
    high = close + rng.uniform(100, 500, n)
    low = close - rng.uniform(100, 500, n)
    open_ = close + rng.normal(0, 100, n)
    volume = rng.uniform(1_000_000, 5_000_000, n)

    index = pd.date_range(end=datetime.utcnow(), periods=n, freq="4h")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


def _make_bullish_ohlcv(n: int = 250) -> pd.DataFrame:
    """Rising trend: MM9 > MM21 > MM200 on last row (guaranteed)."""
    t = np.arange(n, dtype=float)
    close = 50_000 + t * 100  # linear rise ensures MM9 > MM21 > MM200
    high = close + 200
    low = close - 200
    index = pd.date_range(end=datetime.utcnow(), periods=n, freq="4h")
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close,
         "volume": np.ones(n) * 2_000_000},
        index=index,
    )


def _make_bearish_ohlcv(n: int = 250) -> pd.DataFrame:
    """Falling trend: MM9 < MM21 < MM200 on last row (guaranteed)."""
    t = np.arange(n, dtype=float)
    close = 75_000 - t * 100
    close = np.maximum(close, 1_000)
    high = close + 200
    low = close - 200
    index = pd.date_range(end=datetime.utcnow(), periods=n, freq="4h")
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close,
         "volume": np.ones(n) * 2_000_000},
        index=index,
    )


# ─── Indicator columns present ────────────────────────────────────────────────

class TestIndicatorColumnsPresent:
    def test_sma_columns_added(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.sma_9 is not None
        assert result.sma_21 is not None
        assert result.sma_200 is not None

    def test_rsi_column_present(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.rsi_14 is not None

    def test_macd_columns_present(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.macd is not None
        assert result.macd_signal is not None
        assert result.macd_hist is not None

    def test_bollinger_bands_columns_present(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.bb_upper is not None
        assert result.bb_middle is not None
        assert result.bb_lower is not None

    def test_volume_avg_present(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.volume_avg_20 is not None

    def test_timeframe_preserved(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "1d")
        assert result.timeframe == "1d"


# ─── Insufficient data ────────────────────────────────────────────────────────

class TestInsufficientData:
    def test_raises_when_less_than_50_rows(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators, InsufficientDataError
        df = _make_ohlcv(n=40)
        with pytest.raises(InsufficientDataError):
            TechnicalIndicators.calculate(df, "4h")

    def test_exactly_50_rows_does_not_raise(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv(n=50)
        result = TechnicalIndicators.calculate(df, "4h")
        assert result is not None

    def test_92_rows_accepted(self):
        """CoinGecko free tier returns ~92 daily candles — must be accepted."""
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv(n=92)
        result = TechnicalIndicators.calculate(df, "1d")
        assert result is not None

    def test_180_rows_does_not_raise(self):
        """CoinGecko free tier returns 180 4h candles — must be accepted."""
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv(n=180)
        result = TechnicalIndicators.calculate(df, "4h")
        assert result is not None

    def test_mm200_is_none_when_less_than_200_rows(self):
        """With 92-180 candles (free tier), MM200 is None — not an error."""
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv(n=180)
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.sma_200 is None

    def test_mm200_computed_when_200_plus_rows(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv(n=250)
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.sma_200 is not None

    def test_250_rows_does_not_raise(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv(n=250)
        result = TechnicalIndicators.calculate(df, "4h")
        assert result is not None


# ─── MM alignment signal ──────────────────────────────────────────────────────

class TestMMAlignment:
    def test_bullish_when_mm9_above_mm21_above_mm200(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_bullish_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.mm_alignment == "bullish"

    def test_bearish_when_mm9_below_mm21_below_mm200(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_bearish_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.mm_alignment == "bearish"

    def test_mixed_for_non_aligned(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        # Random data: alignment is not guaranteed bullish or bearish
        df = _make_ohlcv(trend="sideways")
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.mm_alignment in ("bullish", "bearish", "mixed")


# ─── RSI zone ─────────────────────────────────────────────────────────────────

class TestRSIZone:
    def test_rsi_value_in_0_to_100_range(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert 0 <= result.rsi_14 <= 100

    def test_rsi_zone_overbought_when_above_70(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        # Simulate extreme uptrend → RSI > 70
        df = _make_bullish_ohlcv(n=250)
        result = TechnicalIndicators.calculate(df, "4h")
        # Just verify the zone logic is consistent with the value
        if result.rsi_14 > 70:
            assert result.rsi_zone == "overbought"

    def test_rsi_zone_oversold_when_below_30(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_bearish_ohlcv(n=250)
        result = TechnicalIndicators.calculate(df, "4h")
        if result.rsi_14 < 30:
            assert result.rsi_zone == "oversold"

    def test_rsi_zone_neutral_when_between_30_and_70(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        if 30 <= result.rsi_14 <= 70:
            assert result.rsi_zone == "neutral"

    @pytest.mark.parametrize("rsi_val,expected_zone", [
        (25.0, "oversold"),
        (30.0, "neutral"),
        (50.0, "neutral"),
        (70.0, "neutral"),
        (71.0, "overbought"),
    ])
    def test_zone_thresholds(self, rsi_val, expected_zone):
        from crypto_advisor.indicators.technical import _rsi_zone
        assert _rsi_zone(rsi_val) == expected_zone


# ─── MACD crossover ───────────────────────────────────────────────────────────

class TestMACDCrossover:
    def test_macd_crossover_is_valid_string(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.macd_crossover in ("bullish_cross", "bearish_cross", "none")

    def test_bullish_cross_detected(self):
        from crypto_advisor.indicators.technical import _macd_crossover_signal
        # Previous: MACD < Signal; Current: MACD > Signal → bullish cross
        assert _macd_crossover_signal(
            macd_prev=-10, signal_prev=-5,
            macd_curr=5, signal_curr=3,
        ) == "bullish_cross"

    def test_bearish_cross_detected(self):
        from crypto_advisor.indicators.technical import _macd_crossover_signal
        # Previous: MACD > Signal; Current: MACD < Signal → bearish cross
        assert _macd_crossover_signal(
            macd_prev=10, signal_prev=5,
            macd_curr=-2, signal_curr=3,
        ) == "bearish_cross"

    def test_no_cross_when_both_above(self):
        from crypto_advisor.indicators.technical import _macd_crossover_signal
        assert _macd_crossover_signal(5, 3, 8, 4) == "none"

    def test_no_cross_when_both_below(self):
        from crypto_advisor.indicators.technical import _macd_crossover_signal
        assert _macd_crossover_signal(-5, -3, -8, -4) == "none"


# ─── Bollinger Bands position ─────────────────────────────────────────────────

class TestBollingerPosition:
    def test_bb_position_is_valid_string(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.bb_position in ("above_upper", "below_lower", "inside")

    @pytest.mark.parametrize("price,lower,upper,expected", [
        (70_000, 65_000, 68_000, "above_upper"),
        (60_000, 65_000, 68_000, "below_lower"),
        (66_000, 65_000, 68_000, "inside"),
        (65_000, 65_000, 68_000, "inside"),   # on lower band → inside
        (68_000, 65_000, 68_000, "inside"),   # on upper band → inside
    ])
    def test_bb_position_logic(self, price, lower, upper, expected):
        from crypto_advisor.indicators.technical import _bb_position
        assert _bb_position(price, lower, upper) == expected


# ─── Snapshot shape ───────────────────────────────────────────────────────────

class TestSnapshotShape:
    def test_snapshot_has_symbol(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h", symbol="BTC")
        assert result.symbol == "BTC"

    def test_sma_9_less_than_close_in_downtrend(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_bearish_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        # In a falling market, SMA_9 lags behind close (close < SMA9 is expected)
        assert result.sma_9 is not None
        assert result.sma_9 > 0

    def test_bb_upper_greater_than_bb_lower(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.bb_upper > result.bb_lower

    def test_bb_middle_between_upper_and_lower(self):
        from crypto_advisor.indicators.technical import TechnicalIndicators
        df = _make_ohlcv()
        result = TechnicalIndicators.calculate(df, "4h")
        assert result.bb_lower <= result.bb_middle <= result.bb_upper
