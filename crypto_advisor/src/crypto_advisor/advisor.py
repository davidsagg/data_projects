"""Claude-powered crypto swing trading recommendation engine."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

from .models import (
    AdvisorContext,
    AdvisorRequest,
    AdvisorResponse,
    MarketData,
    RecommendationOutput,
    TechnicalSnapshot,
    WeeklyReportOutput,
)

load_dotenv()

_CHARS_PER_TOKEN = 4  # rough estimate for mixed Portuguese/English/numbers


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token (safe upper bound)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


_MARKET_SECTION_TOKEN_LIMIT = 3_800  # hard cap for the user message market section


# ─── System prompt (cached — stable instructions, changes rarely) ─────────────

_SYSTEM_PROMPT = """You are a professional crypto swing trading analyst specialising in the Brazilian market.
Your role is to generate structured weekly trading recommendations for the Mercado Bitcoin exchange.

LANGUAGE: Respond entirely in Brazilian Portuguese (pt-BR). All text fields (reasoning, market_summary,
fear_greed_context, tax_impact) must be written in Portuguese. Keep technical terms (BUY, SELL, HOLD,
SKIP, RSI, MACD, etc.) in their standard English abbreviations.

CURRENCY:
- JSON price fields (entry_price_usd, stop_loss_usd, target_price_usd): provide in USD.
  Convert from BRL by dividing by the USD/BRL rate shown in the MARKET DATA section header.
  Example: if BTC entry is R$435.000 and rate is 5.75 → entry_price_usd = 75652.
- All TEXT fields (reasoning, market_summary, fear_greed_context, tax_impact): always express
  prices in BRL (R$), never in USD ($). Use the BRL values from the MARKET DATA section.

STRATEGY PARAMETERS:
- Style: Swing trading (typical hold 2-7 days)
- Timeframes: 4h confirmation, Daily trend
- Risk management: always define stop loss at a technical level

RECOMMENDATION RULES:
1. BUY        — setup de alta com entrada / stop / alvo definidos (todos os preços > 0)
2. SELL       — stop atingido, alvo alcançado, ou setup invalidado (respeite TaxContext)
3. SELL (take-profit) — ativo com forte valorização recente apresenta sinais de exaustão:
     • RSI 4h ou diário acima de 70 (sobrecomprado)
     • Preço no terço superior das Bandas de Bollinger (bb_position = "upper")
     • Variação 7d ou 30d elevada (acima de +25% ou +50% respectivamente)
     • Qualquer combinação de dois ou mais dos fatores acima
     Use action "SELL", reasoning explicando o risco de reversão e o ganho já realizado.
     Defina entry = preço atual, target = suporte mais próximo, stop = máxima recente + 2%.
4. HOLD       — posição aberta, setup ainda válido
5. SKIP       — dados insuficientes ou sem setup acionável (entry/stop/target = null)

CRITICAL: entry_price_usd, stop_loss_usd e target_price_usd NUNCA podem ser 0.
- Para BUY/SELL: use o preço atual do MARKET DATA como referência de entrada.
- Se não tiver preço para o símbolo, use action "SKIP" e preços null.

RISK / REWARD:
- R:R >= 2.0 → confidence "high"
- R:R >= 1.5 → confidence "medium"
- R:R <  1.5 → confidence "low" (sobrescreve qualquer outro sinal)
- Para SELL take-profit: calcule RR como (entrada − stop) / (entrada − alvo)

TAX RULES (crítico — nunca ignorar):
- Zona BLOCKED  → NENHUMA venda; apenas BUY e HOLD
- Zona CRITICAL → apenas SELLs de loss-harvesting (posições em prejuízo)
- Zona WARNING  → priorizar loss-harvesting; reduzir volume de vendas
- Sempre preencher tax_impact para toda recomendação SELL

OUTPUT — return ONLY valid JSON, no extra text, matching this schema exactly:
{
  "recommendations": [
    {
      "symbol":            "BTC",
      "action":            "BUY",
      "entry_price_usd":   65000,
      "stop_loss_usd":     62000,
      "target_price_usd":  71000,
      "risk_reward_ratio": 2.0,
      "confidence":        "high",
      "timeframe":         "swing",
      "reasoning":         "...",
      "tax_impact":        ""
    }
  ],
  "market_summary":    "2-3 sentences on overall market conditions",
  "fear_greed_context":"Fear & Greed value and its implication",
  "generated_at":      "ISO 8601 timestamp"
}"""


# ─── Prompt builder ───────────────────────────────────────────────────────────

def _derive_rate(ctx: AdvisorContext) -> float:
    """USD/BRL rate from BTC market data (most liquid pair)."""
    btc = ctx.market_data.get("BTC") or next(
        (m for m in ctx.top_markets if m.symbol == "BTC"), None
    )
    if btc and btc.price_usd:
        return btc.price_brl / btc.price_usd
    return 5.8  # fallback


def _r(usd: float | None, rate: float) -> str:
    """Format a USD value as BRL string for the prompt."""
    if usd is None:
        return "N/D"
    return f"R${usd * rate:,.0f}"


def _fmt_snapshot(snap: TechnicalSnapshot, rate: float) -> str:
    """Format technical indicators with BRL prices (converted from USD OHLCV)."""
    has_data = all(
        v is not None
        for v in (snap.sma_9, snap.sma_21, snap.rsi_14, snap.macd,
                  snap.macd_hist, snap.bb_lower, snap.bb_middle, snap.bb_upper)
    )
    if not has_data:
        return "  [dados insuficientes para indicadores completos]"
    mm200 = _r(snap.sma_200, rate) if snap.sma_200 else "N/D"
    return (
        f"  MM9={_r(snap.sma_9, rate)} | MM21={_r(snap.sma_21, rate)} | MM200={mm200} "
        f"| Alinhamento={snap.mm_alignment.upper()}\n"
        f"  RSI={snap.rsi_14:.1f} ({snap.rsi_zone}) | "
        f"MACD={snap.macd * rate:,.0f} hist={snap.macd_hist * rate:,.0f} ({snap.macd_crossover})\n"
        f"  BB inferior={_r(snap.bb_lower, rate)} meio={_r(snap.bb_middle, rate)} "
        f"superior={_r(snap.bb_upper, rate)} | Posição: {snap.bb_position}"
    )


def build_user_prompt(ctx: AdvisorContext) -> str:
    lines: list[str] = []
    rate = _derive_rate(ctx)

    # Portfolio
    lines.append("=== PORTFÓLIO (Mercado Bitcoin) ===")
    if ctx.portfolio:
        for pos in ctx.portfolio:
            md = ctx.market_data.get(pos.symbol)
            current_brl = md.price_brl if md else 0.0
            pnl_brl = (current_brl - pos.avg_price_brl) * pos.quantity
            pnl_pct = (current_brl / pos.avg_price_brl - 1) * 100 if pos.avg_price_brl else 0
            lines.append(
                f"  {pos.symbol}: {pos.quantity:.6g} un | Médio R${pos.avg_price_brl:,.0f} "
                f"| Atual R${current_brl:,.0f} | P&L R${pnl_brl:+,.0f} ({pnl_pct:+.1f}%)"
            )
    else:
        lines.append("  [portfólio não disponível]")

    # Tax status
    lines.append("\n=== STATUS FISCAL ===")
    if ctx.tax_context:
        tc = ctx.tax_context
        lines.append(
            f"  Zona: {tc.zone.upper()} | Vendido: R${tc.total_sold_brl:,.0f} / "
            f"R${tc.limit_brl:,.0f} ({tc.total_sold_brl/tc.limit_brl*100:.0f}%) | "
            f"Margem: R${tc.margin_available_brl:,.0f}"
        )
        lines.append(f"  Instrução: {tc.instruction}")
        if tc.loss_harvest_candidates:
            lines.append(f"  Candidatos loss harvest: {', '.join(tc.loss_harvest_candidates)}")
    else:
        lines.append("  [status fiscal não disponível — operar com cautela]")

    # Market data — BRL primary, USD parenthetical for JSON back-calculation
    lines.append(f"\n=== DADOS DE MERCADO (taxa USD/BRL: {rate:.2f}) ===")
    for sym, md in ctx.market_data.items():
        lines.append(
            f"  {sym}: R${md.price_brl:,.0f} (${md.price_usd:,.0f} USD)"
            f" | 24h: {md.change_24h_pct:+.1f}%  7d: {md.change_7d_pct:+.1f}%"
            f" | MCap R${md.market_cap_usd * rate / 1e9:.0f}B"
            + (f" | #{md.market_cap_rank}" if md.market_cap_rank else "")
        )

    # Technical 4h — indicator prices converted to BRL
    if ctx.technical_4h:
        lines.append("\n=== ANÁLISE TÉCNICA (4h) — preços em BRL ===")
        for sym, snap in ctx.technical_4h.items():
            lines.append(f"  [{sym}]")
            lines.append(_fmt_snapshot(snap, rate))

    # Technical 1d — indicator prices converted to BRL
    if ctx.technical_1d:
        lines.append("\n=== ANÁLISE TÉCNICA (Diário) — preços em BRL ===")
        for sym, snap in ctx.technical_1d.items():
            lines.append(f"  [{sym}]")
            lines.append(_fmt_snapshot(snap, rate))

    # Top markets — BRL prices, trim to token budget
    if ctx.top_markets:
        lines.append("\n=== TOP MARKET CAP ===")
        lines.append("  Rank | Ativo | Preço BRL | MCap(B BRL) | 24h%")
        current_tokens = estimate_tokens("\n".join(lines))
        budget_left = _MARKET_SECTION_TOKEN_LIMIT - current_tokens
        max_markets = min(20, max(5, budget_left // 15))
        for m in ctx.top_markets[:max_markets]:
            lines.append(
                f"  #{m.market_cap_rank or '?':<3} | {m.symbol:<6} | "
                f"R${m.price_brl:,.0f} | R${m.market_cap_usd * rate / 1e9:.0f}B | {m.change_24h_pct:+.1f}%"
            )

    # Fear & Greed
    lines.append("\n=== FEAR & GREED INDEX ===")
    if ctx.fear_greed:
        fg = ctx.fear_greed
        lines.append(f"  {fg.value} — {fg.classification}")
    else:
        lines.append("  [não disponível]")

    # Instruction
    week = ctx.week_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines.append(
        f"\n=== INSTRUÇÃO ===\n"
        f"Analise todos os ativos e gere recomendações de swing trading para a semana de {week}.\n"
        "Priorize setups com R:R >= 2.0. Aplique rigorosamente as regras de TaxContext."
    )

    return "\n".join(lines)


# ─── CryptoAdvisor ────────────────────────────────────────────────────────────

class CryptoAdvisor:
    MAX_RETRIES = 2

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # ── Weekly recommendations (Sprint 1 primary path) ────────────────────────

    def generate_weekly_recommendations(
        self, ctx: AdvisorContext
    ) -> WeeklyReportOutput:
        user_msg = build_user_prompt(ctx)

        for attempt in range(self.MAX_RETRIES):
            raw = self._call_claude(user_msg, attempt)
            try:
                data = json.loads(raw)
                report = WeeklyReportOutput(**data)
                return report
            except (json.JSONDecodeError, Exception):
                if attempt == self.MAX_RETRIES - 1:
                    raise
                # On first failure, append explicit schema reminder
                user_msg += (
                    "\n\nERROR: previous response was not valid JSON. "
                    "Return ONLY the JSON object — no markdown, no prose, no code fences."
                )

        raise RuntimeError("Claude failed to return valid JSON after retries.")

    def _call_claude(self, user_msg: str, attempt: int = 0) -> str:
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_msg}],
        )
        content = response.content[0]
        return content.text  # type: ignore[union-attr]

    # ── Legacy method (kept for backward compatibility) ───────────────────────

    def analyze(self, request: AdvisorRequest) -> AdvisorResponse:
        legacy_prompt = """You are a crypto market analyst. Analyse the provided data and respond
with JSON: {"answer": "...", "reasoning": "...", "confidence": "high|medium|low"}"""

        user_message = request.question
        if request.market_data:
            user_message += "\n\nMarket data:\n" + self._format_market_data(request.market_data)
        if request.context:
            user_message += f"\n\nContext:\n{request.context}"

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=[{"type": "text", "text": legacy_prompt,
                      "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text  # type: ignore[union-attr]
        return AdvisorResponse(**json.loads(raw))

    @staticmethod
    def _format_market_data(market_data: list[MarketData], rate: float = 5.8) -> str:
        return "\n".join(
            f"- {m.symbol}: R${m.price_brl:,.0f} ({m.change_24h_pct:+.2f}% 24h) "
            f"MCap: R${m.market_cap_usd * rate / 1e9:.0f}B"
            for m in market_data
        )
