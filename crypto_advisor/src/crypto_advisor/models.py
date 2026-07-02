"""Pydantic models for the CryptoAdvisor system."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── Market data ──────────────────────────────────────────────────────────────

class MarketData(BaseModel):
    symbol: str
    price_usd: float
    price_brl: float = 0.0
    change_24h_pct: float
    change_7d_pct: float = 0.0
    volume_24h_usd: float
    market_cap_usd: float
    market_cap_rank: int | None = None


class FearGreedData(BaseModel):
    value: int
    classification: str
    timestamp: datetime


# ─── Technical analysis ───────────────────────────────────────────────────────

class TechnicalSnapshot(BaseModel):
    symbol: str = ""
    timeframe: str

    sma_9: float | None = None
    sma_21: float | None = None
    sma_200: float | None = None
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    bb_bandwidth: float | None = None
    volume_avg_20: float | None = None

    # Derived signals
    mm_alignment: str = "mixed"       # "bullish" | "bearish" | "mixed"
    rsi_zone: str = "neutral"         # "overbought" | "oversold" | "neutral"
    macd_crossover: str = "none"      # "bullish_cross" | "bearish_cross" | "none"
    bb_position: str = "inside"       # "above_upper" | "below_lower" | "inside"


# ─── Portfolio & trades ───────────────────────────────────────────────────────

class PortfolioPosition(BaseModel):
    symbol: str
    quantity: float
    avg_price_brl: float
    exchange: str = "mercado_bitcoin"


class TradeRecord(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price_brl: float
    total_brl: float
    fee_brl: float = 0.0
    exchange: str = "mercado_bitcoin"
    traded_at: datetime


# ─── Tax ─────────────────────────────────────────────────────────────────────

class TaxContext(BaseModel):
    zone: Literal["safe", "warning", "critical", "blocked"]
    total_sold_brl: float
    limit_brl: float
    margin_available_brl: float
    instruction: str
    loss_harvest_candidates: list[str] = Field(default_factory=list)


# ─── Recommendations ──────────────────────────────────────────────────────────

class RecommendationOutput(BaseModel):
    model_config = ConfigDict(strict=False)

    symbol: str
    action: Literal["BUY", "SELL", "HOLD", "SKIP"]
    entry_price_usd: float | None = None
    stop_loss_usd: float | None = None
    target_price_usd: float | None = None
    risk_reward_ratio: float | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    timeframe: str = "swing"
    reasoning: str
    tax_impact: str = ""

    @field_validator("entry_price_usd", "stop_loss_usd", "target_price_usd", mode="before")
    @classmethod
    def zero_price_to_none(cls, v: object) -> object:
        """Claude sometimes returns 0 instead of null — treat as missing."""
        if isinstance(v, (int, float)) and v == 0:
            return None
        return v

    @field_validator("risk_reward_ratio")
    @classmethod
    def rr_must_be_positive(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("risk_reward_ratio must be >= 0")
        return v

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()


class WeeklyReportOutput(BaseModel):
    recommendations: list[RecommendationOutput]
    market_summary: str
    fear_greed_context: str
    generated_at: str


# ─── Advisor context (assembled before each weekly run) ───────────────────────

class AdvisorContext(BaseModel):
    portfolio: list[PortfolioPosition] = Field(default_factory=list)
    market_data: dict[str, MarketData] = Field(default_factory=dict)
    technical_4h: dict[str, TechnicalSnapshot] = Field(default_factory=dict)
    technical_1d: dict[str, TechnicalSnapshot] = Field(default_factory=dict)
    fear_greed: FearGreedData | None = None
    tax_context: TaxContext | None = None
    top_markets: list[MarketData] = Field(default_factory=list)
    week_date: str = ""


# ─── Performance ─────────────────────────────────────────────────────────────

class PerformanceSummary(BaseModel):
    total_trades: int = 0
    win_rate_pct: float = 0.0
    avg_r_multiple: float = 0.0
    total_pnl_brl: float = 0.0
    open_trades: int = 0


# ─── Legacy models (kept for backward compatibility) ─────────────────────────

class AdvisorRequest(BaseModel):
    question: str
    market_data: list[MarketData] = Field(default_factory=list)
    context: str = ""


class AdvisorResponse(BaseModel):
    answer: str
    reasoning: str
    confidence: str
    disclaimer: str = (
        "This is AI-generated analysis, not financial advice. "
        "Always do your own research before making investment decisions."
    )
