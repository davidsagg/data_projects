"""Technical indicator calculations.

Uses pandas-ta when available (Python 3.12 / MacBook M2).
Falls back to pure-pandas implementations in environments where
pandas-ta is not installed (e.g. Python 3.11 DevContainer / CI).
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from ..models import TechnicalSnapshot

try:
    import pandas_ta as ta  # type: ignore[import-untyped]
    _HAS_PANDAS_TA = True
except ImportError:
    _HAS_PANDAS_TA = False


# ─── Custom exceptions ────────────────────────────────────────────────────────

class InsufficientDataError(Exception):
    """Raised when the DataFrame has fewer than 200 rows (MM200 would be invalid)."""


# ─── Pure-pandas fallback implementations ────────────────────────────────────

def _sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    # avg_loss == 0 means no down-closes → RSI = 100 (extreme uptrend)
    rs = avg_gain / avg_loss.where(avg_loss != 0, other=np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.where(avg_loss != 0, other=100.0)


def _macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bbands(
    series: pd.Series, length: int = 20, std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    middle = series.rolling(length).mean()
    stdev = series.rolling(length).std()
    upper = middle + std * stdev
    lower = middle - std * stdev
    bandwidth = (upper - lower) / middle.replace(0, np.nan) * 100
    return upper, middle, lower, bandwidth


# ─── Derived signal helpers (exported for direct testing) ─────────────────────

def _rsi_zone(rsi_val: float) -> str:
    if rsi_val > 70:
        return "overbought"
    if rsi_val < 30:
        return "oversold"
    return "neutral"


def _mm_alignment(sma9: float, sma21: float, sma200: float) -> str:
    if sma9 > sma21 > sma200:
        return "bullish"
    if sma9 < sma21 < sma200:
        return "bearish"
    return "mixed"


def _macd_crossover_signal(
    macd_prev: float,
    signal_prev: float,
    macd_curr: float,
    signal_curr: float,
) -> str:
    was_below = macd_prev < signal_prev
    is_above = macd_curr > signal_curr
    if was_below and is_above:
        return "bullish_cross"
    was_above = macd_prev > signal_prev
    is_below = macd_curr < signal_curr
    if was_above and is_below:
        return "bearish_cross"
    return "none"


def _bb_position(close: float, bb_lower: float, bb_upper: float) -> str:
    if close > bb_upper:
        return "above_upper"
    if close < bb_lower:
        return "below_lower"
    return "inside"


# ─── Main class ───────────────────────────────────────────────────────────────

class TechnicalIndicators:
    """Compute technical indicators for a given OHLCV DataFrame.

    MIN_ROWS = 100 ensures RSI(14), MACD(12/26/9) and Bollinger(20) are
    meaningful. MM200 is computed only when len(df) >= 200; otherwise it
    returns None and mm_alignment falls back to "mixed".
    """

    MIN_ROWS = 50

    @classmethod
    def calculate(
        cls,
        df: pd.DataFrame,
        timeframe: str,
        symbol: str = "",
    ) -> TechnicalSnapshot:
        if len(df) < cls.MIN_ROWS:
            raise InsufficientDataError(
                f"DataFrame has {len(df)} rows; need >= {cls.MIN_ROWS} for MM200."
            )

        close = df["close"]
        volume = df.get("volume", pd.Series(np.zeros(len(df)), index=df.index))

        if _HAS_PANDAS_TA:
            snapshot = cls._calculate_with_pandas_ta(df, close, volume, timeframe, symbol)
        else:
            snapshot = cls._calculate_pure_pandas(close, volume, timeframe, symbol)

        return snapshot

    @classmethod
    def _calculate_with_pandas_ta(
        cls,
        df: pd.DataFrame,
        close: pd.Series,
        volume: pd.Series,
        timeframe: str,
        symbol: str,
    ) -> TechnicalSnapshot:
        wdf = df.copy()
        wdf.ta.sma(length=9, append=True)
        wdf.ta.sma(length=21, append=True)
        wdf.ta.sma(length=200, append=True)
        wdf.ta.rsi(length=14, append=True)
        wdf.ta.macd(fast=12, slow=26, signal=9, append=True)
        wdf.ta.bbands(length=20, std=2, append=True)

        last = wdf.iloc[-1]
        prev = wdf.iloc[-2]

        sma9 = float(last.get("SMA_9", np.nan))
        sma21 = float(last.get("SMA_21", np.nan))
        sma200 = float(last.get("SMA_200", np.nan))
        rsi = float(last.get("RSI_14", np.nan))
        macd_val = float(last.get("MACD_12_26_9", np.nan))
        macd_sig = float(last.get("MACDs_12_26_9", np.nan))
        macd_hist = float(last.get("MACDh_12_26_9", np.nan))
        # pandas-ta >= 0.3.14b appends an extra '_2.0' suffix to the std param
        bb_upper = float(last.get("BBU_20_2.0_2.0", last.get("BBU_20_2.0", np.nan)))
        bb_mid = float(last.get("BBM_20_2.0_2.0", last.get("BBM_20_2.0", np.nan)))
        bb_lower = float(last.get("BBL_20_2.0_2.0", last.get("BBL_20_2.0", np.nan)))
        bb_bw = float(last.get("BBB_20_2.0_2.0", last.get("BBB_20_2.0", np.nan)))
        vol_avg = float(volume.rolling(20).mean().iloc[-1])

        return cls._build_snapshot(
            symbol, timeframe,
            sma9, sma21, sma200, rsi,
            macd_val, macd_sig, macd_hist,
            bb_upper, bb_mid, bb_lower, bb_bw,
            vol_avg, float(close.iloc[-1]),
            float(prev.get("MACD_12_26_9", np.nan)),
            float(prev.get("MACDs_12_26_9", np.nan)),
        )

    @classmethod
    def _calculate_pure_pandas(
        cls,
        close: pd.Series,
        volume: pd.Series,
        timeframe: str,
        symbol: str,
    ) -> TechnicalSnapshot:
        sma9_s = _sma(close, 9)
        sma21_s = _sma(close, 21)
        sma200_s = _sma(close, 200)
        rsi_s = _rsi(close, 14)
        macd_s, signal_s, hist_s = _macd(close)
        bb_upper_s, bb_mid_s, bb_lower_s, bb_bw_s = _bbands(close)
        vol_avg_s = volume.rolling(20).mean()

        def _last(s: pd.Series) -> float:
            v = s.iloc[-1]
            return float(v) if pd.notna(v) else float("nan")

        return cls._build_snapshot(
            symbol, timeframe,
            _last(sma9_s), _last(sma21_s), _last(sma200_s),
            _last(rsi_s),
            _last(macd_s), _last(signal_s), _last(hist_s),
            _last(bb_upper_s), _last(bb_mid_s), _last(bb_lower_s), _last(bb_bw_s),
            _last(vol_avg_s), float(close.iloc[-1]),
            float(macd_s.iloc[-2]) if len(macd_s) > 1 else float("nan"),
            float(signal_s.iloc[-2]) if len(signal_s) > 1 else float("nan"),
        )

    @staticmethod
    def _build_snapshot(
        symbol: str,
        timeframe: str,
        sma9: float, sma21: float, sma200: float,
        rsi: float,
        macd_val: float, macd_sig: float, macd_hist: float,
        bb_upper: float, bb_mid: float, bb_lower: float, bb_bw: float,
        vol_avg: float,
        last_close: float,
        macd_prev: float,
        signal_prev: float,
    ) -> TechnicalSnapshot:
        def _safe(v: float) -> float | None:
            return None if (v != v) else v  # NaN check without math.isnan

        alignment = (
            _mm_alignment(sma9, sma21, sma200)
            if all(v == v for v in (sma9, sma21, sma200))
            else "mixed"
        )
        rsi_z = _rsi_zone(rsi) if rsi == rsi else "neutral"
        crossover = (
            _macd_crossover_signal(macd_prev, signal_prev, macd_val, macd_sig)
            if all(v == v for v in (macd_prev, signal_prev, macd_val, macd_sig))
            else "none"
        )
        bb_pos = (
            _bb_position(last_close, bb_lower, bb_upper)
            if all(v == v for v in (last_close, bb_lower, bb_upper))
            else "inside"
        )

        return TechnicalSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            sma_9=_safe(sma9),
            sma_21=_safe(sma21),
            sma_200=_safe(sma200),
            rsi_14=_safe(rsi),
            macd=_safe(macd_val),
            macd_signal=_safe(macd_sig),
            macd_hist=_safe(macd_hist),
            bb_upper=_safe(bb_upper),
            bb_middle=_safe(bb_mid),
            bb_lower=_safe(bb_lower),
            bb_bandwidth=_safe(bb_bw),
            volume_avg_20=_safe(vol_avg),
            mm_alignment=alignment,
            rsi_zone=rsi_z,
            macd_crossover=crossover,
            bb_position=bb_pos,
        )
