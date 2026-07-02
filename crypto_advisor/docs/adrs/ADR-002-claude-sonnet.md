# ADR-002: Claude Sonnet API como motor de recomendação

**Status:** Aceito  
**Data:** 2026-05-12  
**Autores:** David Saggioro

---

## Contexto

O núcleo do projeto é um motor de análise que recebe dados de mercado (preços, indicadores técnicos, sentimento, portfólio, status fiscal) e produz recomendações estruturadas de swing trading com entry/stop/target/RR e impacto fiscal.

Requisitos do motor:
- Output JSON estritamente tipado e validável por Pydantic
- Raciocínio explícito e auditável (human-in-the-loop)
- Suporte a prompt caching (sistema rodando 1x/semana, contexto fixo extenso)
- Custo previsível para uso semanal (1 análise/semana ~10–15 ativos)

---

## Decisão

Usar **claude-sonnet-4-6** via Anthropic SDK com prompt caching habilitado no system prompt.

---

## Racional

| Critério                        | claude-sonnet-4-6 | GPT-4o     | Gemini 1.5 Pro |
|---------------------------------|-------------------|------------|----------------|
| Output JSON estruturado         | Sim (nativo)      | Sim        | Sim            |
| Prompt caching                  | Sim (ephemeral)   | Não        | Sim            |
| Custo por MTok input            | $3,00             | $5,00      | $3,50          |
| Custo cacheado por MTok         | $0,30 (90% off)   | N/A        | ~$0,35         |
| Janela de contexto              | 200k tokens       | 128k       | 1M             |
| Qualidade análise financeira    | Alta              | Alta       | Média-Alta     |
| SDK Python maduro               | Sim               | Sim        | Sim            |

O prompt caching é especialmente relevante: o system prompt de análise (~2k tokens) + contexto de mercado (~3k tokens) será reutilizado a cada execução semanal, gerando ~90% de economia nos tokens de entrada.

---

## Implementação

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    system=[{
        "type": "text",
        "text": ANALYSIS_SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"}  # TTL 5min
    }],
    messages=[{"role": "user", "content": market_context}],
)
```

### Schema JSON de saída esperado

```json
{
  "recommendations": [
    {
      "symbol": "BTC",
      "action": "BUY",
      "entry_price_usd": 65000,
      "stop_loss_usd": 62000,
      "target_price_usd": 71000,
      "risk_reward_ratio": 2.0,
      "confidence": "high",
      "timeframe": "4h-diário",
      "reasoning": "Rompimento de MM200 com volume acima da média...",
      "tax_impact": "Venda dentro do limite mensal atual (R$12.400/R$35.000)"
    }
  ],
  "market_summary": "...",
  "fear_greed_context": "...",
  "generated_at": "2026-05-12T18:00:00Z"
}
```

---

## Consequências

- **Positivas:** Custo semanal estimado < R$0,50 com caching; output auditável; integração limpa via SDK oficial
- **Negativas:** Dependência de API externa; latência de rede (contornada pelo schedule semanal)
- **Mitigações:** Retry com backoff exponencial em falha de API; fallback para relatório de dados brutos sem recomendação IA se API indisponível
