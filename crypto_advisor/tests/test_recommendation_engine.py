"""
Tests for the Claude Recommendation Engine output schema.

Covers:
- Pydantic validation of JSON output from Claude
- Valid complete output
- Missing required fields
- Invalid enum values
- Boundary values for risk_reward_ratio
- Parametrized coverage of all action and confidence variants
"""

import json
import pytest
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from typing import Literal


# ─── Schema (mirrors what will live in models.py) ─────────────────────────────

class RecommendationOutput(BaseModel):
    model_config = ConfigDict(strict=False)  # allow coercion from JSON strings

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

    @field_validator("risk_reward_ratio")
    @classmethod
    def rr_must_be_positive(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("risk_reward_ratio must be >= 0")
        return v

    @field_validator("symbol")
    @classmethod
    def symbol_must_be_uppercase(cls, v: str) -> str:
        return v.upper()


class WeeklyReportOutput(BaseModel):
    recommendations: list[RecommendationOutput]
    market_summary: str
    fear_greed_context: str
    generated_at: str


# ─── Fixtures ─────────────────────────────────────────────────────────────────

VALID_RECOMMENDATION = {
    "symbol": "BTC",
    "action": "BUY",
    "entry_price_usd": 65_000.0,
    "stop_loss_usd": 62_000.0,
    "target_price_usd": 71_000.0,
    "risk_reward_ratio": 2.0,
    "confidence": "high",
    "timeframe": "swing",
    "reasoning": "Rompimento de MM200 com volume acima da média; RSI em 55 sem sobrecompra.",
    "tax_impact": "Venda dentro do limite mensal (R$12.400/R$35.000 — zona SAFE).",
}

VALID_WEEKLY_REPORT = {
    "recommendations": [VALID_RECOMMENDATION],
    "market_summary": "Mercado em tendência de alta com Fear & Greed em 72 (Greed).",
    "fear_greed_context": "72 — Greed. Cautela em novas posições especulativas.",
    "generated_at": "2026-05-12T18:00:00Z",
}


# ─── Valid output ──────────────────────────────────────────────────────────────

class TestValidOutput:
    def test_valid_complete_recommendation(self):
        rec = RecommendationOutput(**VALID_RECOMMENDATION)
        assert rec.symbol == "BTC"
        assert rec.action == "BUY"
        assert rec.risk_reward_ratio == pytest.approx(2.0)
        assert rec.confidence == "high"

    def test_valid_weekly_report(self):
        report = WeeklyReportOutput(**VALID_WEEKLY_REPORT)
        assert len(report.recommendations) == 1
        assert report.recommendations[0].symbol == "BTC"

    def test_symbol_normalised_to_uppercase(self):
        rec = RecommendationOutput(**{**VALID_RECOMMENDATION, "symbol": "btc"})
        assert rec.symbol == "BTC"

    def test_optional_price_fields_can_be_none(self):
        minimal = {
            "symbol": "ETH",
            "action": "HOLD",
            "reasoning": "Sem sinal claro; aguardar consolidação.",
        }
        rec = RecommendationOutput(**minimal)
        assert rec.entry_price_usd is None
        assert rec.stop_loss_usd is None

    def test_skip_action_requires_only_reasoning(self):
        rec = RecommendationOutput(
            symbol="MATIC",
            action="SKIP",
            reasoning="Volume insuficiente para análise confiável esta semana.",
        )
        assert rec.action == "SKIP"

    def test_from_json_string(self):
        raw_json = json.dumps(VALID_RECOMMENDATION)
        rec = RecommendationOutput(**json.loads(raw_json))
        assert rec.action == "BUY"


# ─── Invalid enum values ───────────────────────────────────────────────────────

class TestInvalidEnumValues:
    def test_invalid_action_raises(self):
        with pytest.raises(ValidationError) as exc:
            RecommendationOutput(**{**VALID_RECOMMENDATION, "action": "STRONG_BUY"})
        assert "action" in str(exc.value)

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValidationError) as exc:
            RecommendationOutput(**{**VALID_RECOMMENDATION, "confidence": "very_high"})
        assert "confidence" in str(exc.value)

    @pytest.mark.parametrize("action", ["BUY", "SELL", "HOLD", "SKIP"])
    def test_all_valid_actions_accepted(self, action):
        rec = RecommendationOutput(**{**VALID_RECOMMENDATION, "action": action})
        assert rec.action == action

    @pytest.mark.parametrize("confidence", ["high", "medium", "low"])
    def test_all_valid_confidence_levels_accepted(self, confidence):
        rec = RecommendationOutput(**{**VALID_RECOMMENDATION, "confidence": confidence})
        assert rec.confidence == confidence


# ─── Missing required fields ──────────────────────────────────────────────────

class TestMissingRequiredFields:
    def test_missing_symbol_raises(self):
        data = {k: v for k, v in VALID_RECOMMENDATION.items() if k != "symbol"}
        with pytest.raises(ValidationError) as exc:
            RecommendationOutput(**data)
        assert "symbol" in str(exc.value)

    def test_missing_action_raises(self):
        data = {k: v for k, v in VALID_RECOMMENDATION.items() if k != "action"}
        with pytest.raises(ValidationError):
            RecommendationOutput(**data)

    def test_missing_reasoning_raises(self):
        data = {k: v for k, v in VALID_RECOMMENDATION.items() if k != "reasoning"}
        with pytest.raises(ValidationError):
            RecommendationOutput(**data)


# ─── Boundary values ──────────────────────────────────────────────────────────

class TestBoundaryValues:
    def test_rr_zero_is_valid(self):
        rec = RecommendationOutput(**{**VALID_RECOMMENDATION, "risk_reward_ratio": 0.0})
        assert rec.risk_reward_ratio == 0.0

    def test_rr_negative_raises(self):
        with pytest.raises(ValidationError) as exc:
            RecommendationOutput(**{**VALID_RECOMMENDATION, "risk_reward_ratio": -0.1})
        assert "risk_reward_ratio" in str(exc.value)

    def test_rr_very_large_is_valid(self):
        rec = RecommendationOutput(**{**VALID_RECOMMENDATION, "risk_reward_ratio": 100.0})
        assert rec.risk_reward_ratio == 100.0

    def test_rr_below_1_5_signals_low_confidence(self):
        """Business rule from US-013: RR < 1.5 should have confidence=low."""
        data = {**VALID_RECOMMENDATION, "risk_reward_ratio": 1.2, "confidence": "low"}
        rec = RecommendationOutput(**data)
        assert rec.confidence == "low"
        assert rec.risk_reward_ratio < 1.5


# ─── Weekly report structure ──────────────────────────────────────────────────

class TestWeeklyReportStructure:
    def test_multiple_recommendations_parsed(self):
        eth_rec = {**VALID_RECOMMENDATION, "symbol": "ETH", "action": "HOLD",
                   "reasoning": "Consolidando abaixo de $3.500; aguardar rompimento."}
        report = WeeklyReportOutput(**{
            **VALID_WEEKLY_REPORT,
            "recommendations": [VALID_RECOMMENDATION, eth_rec],
        })
        assert len(report.recommendations) == 2

    def test_empty_recommendations_list_is_valid(self):
        report = WeeklyReportOutput(**{**VALID_WEEKLY_REPORT, "recommendations": []})
        assert report.recommendations == []

    def test_report_from_raw_claude_json(self):
        """Simulate parsing raw Claude output string."""
        raw = json.dumps(VALID_WEEKLY_REPORT)
        data = json.loads(raw)
        report = WeeklyReportOutput(**data)
        assert report.recommendations[0].action == "BUY"
