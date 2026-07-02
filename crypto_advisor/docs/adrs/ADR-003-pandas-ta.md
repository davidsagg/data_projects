# ADR-003: pandas-ta como biblioteca de indicadores técnicos

**Status:** Aceito  
**Data:** 2026-05-12  
**Autores:** David Saggioro

---

## Contexto

A estratégia de swing trading requer os seguintes indicadores técnicos calculados sobre dados OHLCV:

| Indicador              | Timeframes   | Uso na estratégia                         |
|------------------------|-------------|-------------------------------------------|
| Médias Móveis (MM)     | 9, 21, 200  | Tendência e suporte/resistência dinâmica  |
| RSI (14)               | 4h, Diário  | Sobrecompra/sobrevenda                    |
| MACD (12/26/9)         | 4h, Diário  | Momentum e cruzamentos                    |
| Bollinger Bands (20,2) | 4h, Diário  | Volatilidade e bandas de preço            |
| Volume médio           | 20 períodos | Confirmação de rompimentos                |

Alternativas consideradas: TA-Lib (requer compilação C), ta (menos funcionalidades), backtesting.py (focado em backtests, não em cálculo puro de indicadores).

---

## Decisão

Usar **pandas-ta >= 0.3.14b** como única biblioteca de indicadores técnicos.

---

## Racional

- **API pandas-nativa:** `df.ta.rsi()`, `df.ta.macd()` — sem boilerplate, integra direto com DataFrames vindos da CoinGecko
- **Cobertura completa:** todos os indicadores necessários em uma dependência só
- **Sem compilação nativa:** TA-Lib requer instalação de binários C no DevContainer; pandas-ta é pure Python
- **Manutenção ativa:** suporte a 130+ indicadores, incluindo extensões pandas via `df.ta.strategy()`

### Exemplo de uso

```python
import pandas_ta as ta

df.ta.sma(length=9, append=True)     # MM9
df.ta.sma(length=21, append=True)    # MM21
df.ta.sma(length=200, append=True)   # MM200
df.ta.rsi(length=14, append=True)
df.ta.macd(fast=12, slow=26, signal=9, append=True)
df.ta.bbands(length=20, std=2, append=True)
```

---

## Consequências

- **Positivas:** Zero overhead de instalação, integração direta com pipeline de dados CoinGecko → DataFrame → Claude
- **Negativas:** pandas-ta 0.3.14b ainda em beta; alguns indicadores menos testados que TA-Lib
- **Mitigações:** Fixar versão no pyproject.toml; escrever testes de smoke para os 5 indicadores usados; documentar os nomes exatos das colunas geradas para garantir acesso consistente no código
