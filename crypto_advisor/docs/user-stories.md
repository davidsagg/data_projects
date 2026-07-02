# CryptoAdvisor — User Stories

**Versão:** 0.1.0  
**Data:** 2026-05-12  
**Sprint inicial:** Fase 1 (TDD)

---

## Épicos

| ID   | Épico                        | Stories |
|------|------------------------------|---------|
| EP-1 | Coleta de Dados              | US-001 a US-004 |
| EP-2 | Análise Técnica              | US-005 a US-007 |
| EP-3 | Tax Optimizer                | US-008 a US-012 |
| EP-4 | Recommendation Engine        | US-013 a US-015 |
| EP-5 | Relatório e Notificação      | US-016 a US-017 |
| EP-6 | UI de Validação              | US-018 a US-019 |
| EP-7 | Performance e Seleção        | US-020 |

---

## EP-1: Coleta de Dados

---

### US-001 — Leitura de portfólio via Mercado Bitcoin API

**Como** usuário,  
**quero** que o sistema leia automaticamente meu portfólio atual no Mercado Bitcoin,  
**para** que as recomendações considerem as posições já abertas e evitem recomendações duplicadas.

**Critérios de aceitação:**
- [ ] `MercadoBitcoinClient.get_portfolio()` retorna lista de `PortfolioPosition` com symbol, quantity, avg_price_brl
- [ ] Autenticação usa HMAC-SHA256 com `MB_API_ID` e `MB_API_SECRET` do `.env`
- [ ] Saldos zerados (< 0.000001) são filtrados da resposta
- [ ] Em caso de erro 401 ou 403, lança `AuthenticationError` com mensagem clara
- [ ] Em caso de timeout (> 10s), lança `ExchangeTimeoutError`
- [ ] Os dados são persistidos/atualizados na tabela `portfolio` do SQLite

**Notas técnicas:**
- Endpoint: `GET /api/v4/accounts/{account_id}/positions`
- Mock disponível para testes: `tests/fixtures/mb_portfolio_response.json`

---

### US-002 — Busca de preços e market data via CoinGecko

**Como** sistema,  
**quero** buscar preços atuais e dados de mercado dos ativos monitorados,  
**para** calcular indicadores técnicos e alimentar o modelo de análise.

**Critérios de aceitação:**
- [ ] `CoinGeckoClient.get_prices(symbols)` retorna dict `{symbol: MarketData}` com price_usd, change_24h_pct, volume_24h_usd, market_cap_usd
- [ ] Busca top-20 por market cap via `/coins/markets` com `vs_currency=usd`
- [ ] Inclui Fear & Greed Index via alternative.me API
- [ ] Cache local em memória de 60 minutos para evitar rate-limit (50 req/min no plano gratuito)
- [ ] Converte preços para BRL usando cotação USD/BRL em tempo real (via CoinGecko ou BCB)
- [ ] Sinaliza quando um ativo do top-20 não está disponível no Mercado Bitcoin

---

### US-003 — Busca de dados OHLCV históricos

**Como** sistema,  
**quero** buscar candles OHLCV históricos para cada ativo,  
**para** calcular indicadores técnicos nos timeframes 4h e diário.

**Critérios de aceitação:**
- [ ] `CoinGeckoClient.get_ohlcv(symbol, timeframe)` retorna DataFrame com colunas: timestamp, open, high, low, close, volume
- [ ] Suporta timeframes: `"4h"` (últimos 90 dias) e `"1d"` (últimos 365 dias)
- [ ] DataFrame tem pelo menos 200 candles para cálculo da MM200
- [ ] Dados são salvos em `market_snapshots` para auditoria e replay de análises
- [ ] Retorna `InsufficientDataError` se candles < 200

---

### US-004 — Importação de histórico de trades do Mercado Bitcoin

**Como** sistema,  
**quero** importar o histórico de trades executados na exchange,  
**para** manter o `tax_tracker` e o `performance_log` atualizados.

**Critérios de aceitação:**
- [ ] `MercadoBitcoinClient.get_trades(since_date)` retorna lista de `TradeRecord`
- [ ] Importação incremental: busca apenas trades após o último `traded_at` registrado no SQLite
- [ ] Cada trade importado atualiza automaticamente `tax_tracker` (soma `total_brl` em vendas)
- [ ] Deduplicação por `(symbol, traded_at, side, total_brl)` para evitar duplicatas em re-imports
- [ ] Recalcula `tax_status` após cada atualização do `tax_tracker`

---

## EP-2: Análise Técnica

---

### US-005 — Cálculo de Médias Móveis (MM9, MM21, MM200)

**Como** motor de recomendação,  
**quero** calcular as médias móveis simples de 9, 21 e 200 períodos,  
**para** identificar tendência, suporte e resistência dinâmica.

**Critérios de aceitação:**
- [ ] `TechnicalIndicators.calculate(df)` adiciona colunas `SMA_9`, `SMA_21`, `SMA_200` ao DataFrame
- [ ] Calculado nos dois timeframes: 4h e diário
- [ ] Retorna `InsufficientDataError` se df tiver menos de 200 linhas (MM200 inválida)
- [ ] Os valores das 3 MMs do último candle são incluídos no snapshot salvo em `market_snapshots.indicators_json`
- [ ] Sinal derivado: `mm_alignment` = "bullish" se SMA_9 > SMA_21 > SMA_200, "bearish" se invertido, "mixed" nos demais casos

---

### US-006 — Cálculo de RSI, MACD e Bollinger Bands

**Como** motor de recomendação,  
**quero** calcular RSI(14), MACD(12/26/9) e Bollinger Bands(20,2),  
**para** avaliar momentum, força da tendência e volatilidade.

**Critérios de aceitação:**
- [ ] `TechnicalIndicators.calculate(df)` adiciona colunas: `RSI_14`, `MACD_12_26_9`, `MACDh_12_26_9`, `MACDs_12_26_9`, `BBL_20_2`, `BBM_20_2`, `BBU_20_2`, `BBB_20_2`
- [ ] RSI retorna valor entre 0–100; NaN nos primeiros 14 períodos
- [ ] Sinais derivados incluídos no snapshot: `rsi_zone` = "overbought" (>70), "oversold" (<30), "neutral"
- [ ] Sinal MACD: `macd_signal` = "bullish_cross" se MACD cruzou acima da linha de sinal no último candle
- [ ] Posição nas Bandas: `bb_position` = "above_upper", "below_lower", "inside"

---

### US-007 — Seleção dinâmica de ativos por market cap

**Como** sistema,  
**quero** selecionar semanalmente os ativos a analisar com base no top-20 CoinGecko,  
**para** ter um mix de ativos sólidos (BTC/ETH/SOL) e promissores de alta liquidez.

**Critérios de aceitação:**
- [ ] BTC, ETH, SOL são sempre incluídos (lista fixa de âncoras)
- [ ] Demais ativos: top-20 CoinGecko por market cap, excluindo stablecoins (USDT, USDC, DAI, BUSD)
- [ ] Filtro adicional: volume 24h > $10M (liquidez mínima para swing trading)
- [ ] Ativos sem par BRL no Mercado Bitcoin são marcados como `exchange_available: false` e incluídos apenas para análise, não para recomendação de trade
- [ ] A lista final é registrada no log de cada análise semanal

---

## EP-3: Tax Optimizer

---

### US-008 — Rastreamento mensal de vendas em BRL

**Como** usuário,  
**quero** que o sistema rastreie automaticamente o total vendido em BRL por mês e por exchange,  
**para** nunca ultrapassar o limite de isenção fiscal de R$35.000 (IN RFB 2.312/2026).

**Critérios de aceitação:**
- [ ] `TaxOptimizer.get_monthly_status(year, month, exchange)` retorna `TaxStatus` com total_sold_brl, tax_status, margem_disponivel_brl
- [ ] Atualizado automaticamente após cada importação de trades via `US-004`
- [ ] O método `add_sale(total_brl, symbol, exchange)` atualiza o acumulador e recalcula a zona
- [ ] O registro em `tax_tracker` usa UPSERT: `INSERT OR REPLACE` para o par (year, month, exchange)

---

### US-009 — Zonas de operação e alertas fiscais

**Como** usuário,  
**quero** ser notificado via Telegram quando o total vendido no mês se aproximar do limite de isenção,  
**para** tomar decisões conscientes sobre novas vendas.

**Critérios de aceitação:**
- [ ] Zona SAFE (< R$28.000): nenhuma ação especial; status incluído no relatório semanal
- [ ] Zona WARNING (R$28k–R$33k): alerta Telegram enviado imediatamente ao mudar de zona; Claude recebe instrução de priorizar loss harvesting
- [ ] Zona CRITICAL (R$33k–R$35k): alerta Telegram urgente; apenas recomendações de loss harvesting são geradas
- [ ] Zona BLOCKED (≥ R$35.000): alerta Telegram de bloqueio; sistema não gera nenhuma recomendação de venda
- [ ] A transição de zona é detectada comparando o status antes e depois de `add_sale()`

---

### US-010 — Loss Harvesting automático

**Como** usuário,  
**quero** que o sistema identifique posições com prejuízo não realizado como candidatos a loss harvesting,  
**para** realizar perdas estrategicamente sem impacto no limite de isenção.

**Critérios de aceitação:**
- [ ] `TaxOptimizer.get_loss_harvest_candidates(portfolio, current_prices)` retorna lista de `LossHarvestCandidate` com symbol, unrealized_loss_brl, loss_pct
- [ ] Candidato qualificado: preço atual < avg_price_brl em pelo menos 5%
- [ ] Lista ordenada por maior perda percentual (mais interessante primeiro)
- [ ] Em zonas WARNING e CRITICAL, candidatos são automaticamente incluídos no contexto enviado ao Claude
- [ ] Venda de loss harvest não é bloqueada em zona CRITICAL (pois realiza perda, não ganho)

---

### US-011 — Income Strategy: distribuição de lucros mensais

**Como** usuário,  
**quero** que o sistema sugira vendas parciais para gerar renda em BRL dentro do limite de isenção,  
**para** converter ganhos não realizados em renda sem pagar IR.

**Critérios de aceitação:**
- [ ] Em zona SAFE, Claude inclui sugestão de realização parcial de lucro para ativos com gain > 20%
- [ ] O valor sugerido de venda não ultrapassa R$33.000 acumulados no mês (margem de R$2.000 abaixo do limite)
- [ ] `TaxOptimizer.calculate_max_sell_brl(current_month_total)` retorna o máximo a vender sem entrar em zona WARNING
- [ ] Sugestão inclui valor exato em BRL a realizar e impacto fiscal estimado

---

### US-012 — Relatório fiscal mensal

**Como** usuário,  
**quero** visualizar um resumo fiscal mensal na UI Streamlit,  
**para** acompanhar minha posição fiscal a qualquer momento.

**Critérios de aceitação:**
- [ ] Painel fiscal na UI mostra: total vendido, limite, margem, zona atual com cor (verde/amarelo/laranja/vermelho)
- [ ] Histórico dos últimos 12 meses com ganho realizado, perda realizada e status de cada mês
- [ ] Exportação do histórico fiscal para CSV
- [ ] Disclaimer visível: "Esta ferramenta é auxiliar. Consulte um contador para declaração de IR."

---

## EP-4: Recommendation Engine

---

### US-013 — Geração de recomendações estruturadas pelo Claude

**Como** usuário,  
**quero** que o Claude analise os dados de mercado e gere recomendações semanais em formato JSON estruturado,  
**para** ter uma análise fundamentada com entry/stop/target/RR e impacto fiscal.

**Critérios de aceitação:**
- [ ] `CryptoAdvisor.generate_weekly_recommendations(context)` retorna `WeeklyReport` validado por Pydantic
- [ ] Cada recomendação tem: symbol, action, entry_price_usd, stop_loss_usd, target_price_usd, risk_reward_ratio, confidence, reasoning, tax_impact
- [ ] Risk/Reward mínimo: recomendações BUY com RR < 1.5 têm confidence = "low"
- [ ] System prompt usa `cache_control: ephemeral` para prompt caching
- [ ] Recomendação salva em `recommendations` com status `pending`
- [ ] Se Claude retornar JSON inválido, tenta 1 retry com instrução explícita de formato; falha após 2 tentativas

---

### US-014 — Validação do schema JSON de output do Claude

**Como** desenvolvedor,  
**quero** garantir que o output do Claude sempre corresponde ao schema Pydantic esperado,  
**para** evitar falhas silenciosas em produção.

**Critérios de aceitação:**
- [ ] `RecommendationOutput` é um modelo Pydantic com validação estrita (`model_config = ConfigDict(strict=True)`)
- [ ] Campos obrigatórios: symbol, action, reasoning — todos os demais têm defaults seguros
- [ ] action deve ser um dos valores: "BUY", "SELL", "HOLD", "SKIP"
- [ ] confidence deve ser: "high", "medium", "low"
- [ ] risk_reward_ratio deve ser ≥ 0 se fornecido
- [ ] Teste parametrizado cobre: JSON válido completo, JSON com campos ausentes, JSON com tipos errados, JSON com valores fora do enum

---

### US-015 — Contexto de mercado completo no prompt

**Como** motor de análise,  
**quero** que o prompt enviado ao Claude inclua todos os contextos relevantes,  
**para** que as recomendações considerem dados técnicos, fundamentais e fiscais de forma integrada.

**Critérios de aceitação:**
- [ ] Prompt inclui: portfólio atual, indicadores técnicos (4h + diário), Fear & Greed Index, status fiscal do Tax Optimizer, market cap ranking
- [ ] Prompt tem seção de instrução explícita sobre o schema JSON de saída esperado
- [ ] Prompt inclui instrução de confidência: "Se os dados forem insuficientes para uma recomendação confiante, retorne action=SKIP com reasoning explicando a ausência de dados"
- [ ] Tamanho do prompt de mercado não ultrapassa 4.000 tokens (validado em teste)

---

## EP-5: Relatório e Notificação

---

### US-016 — Relatório HTML semanal com Jinja2

**Como** usuário,  
**quero** receber um relatório HTML formatado com todas as recomendações e análises da semana,  
**para** ter um documento de referência antes de tomar decisões de trade.

**Critérios de aceitação:**
- [ ] Template `weekly_report.html.j2` renderiza: portfólio atual, recomendações com indicadores, status fiscal, market summary
- [ ] Relatório salvo em `data/reports/YYYY-MM-DD.html` automaticamente
- [ ] Design responsivo (legível em mobile via Telegram preview)
- [ ] Inclui timestamp de geração e disclaimer padrão
- [ ] Testa renderização do template com dados mock sem exceções

---

### US-017 — Entrega via Telegram (domingo 18h)

**Como** usuário,  
**quero** receber o resumo semanal de recomendações no Telegram todo domingo às 18h,  
**para** ser notificado sem precisar abrir o sistema manualmente.

**Critérios de aceitação:**
- [ ] APScheduler dispara o job `weekly_analysis` toda domingo às 18h00 (fuso America/Sao_Paulo)
- [ ] Telegram recebe mensagem com resumo em HTML (truncado a 4.096 chars se necessário) + link para o relatório completo
- [ ] Em caso de falha na API Telegram, o relatório HTML é salvo localmente e uma nova tentativa é feita em 30 minutos
- [ ] Alertas fiscais (WARNING, CRITICAL, BLOCKED) são enviados imediatamente, independente do schedule semanal
- [ ] Mensagem inclui botão/link "Acessar UI de validação → http://localhost:8501"

---

## EP-6: UI de Validação

---

### US-018 — Aprovação e rejeição de recomendações no Streamlit

**Como** usuário,  
**quero** revisar cada recomendação do Claude na UI e aprovar ou rejeitar individualmente,  
**para** manter controle total sobre as decisões de trade (human-in-the-loop).

**Critérios de aceitação:**
- [ ] Página "Recomendações" lista todas as recomendações com status `pending`
- [ ] Cada item mostra: symbol, action, entry/stop/target, RR, confidence, reasoning, tax_impact
- [ ] Botões "Aprovar" e "Rejeitar" atualizam `recommendations.status` e `reviewed_at` no SQLite
- [ ] Após aprovação, exibe instruções claras de execução manual na exchange (não executa automaticamente)
- [ ] Recomendações aprovadas/rejeitadas ficam visíveis no histórico com filtro por semana

---

### US-019 — Dashboard de portfólio e performance

**Como** usuário,  
**quero** visualizar o estado atual do meu portfólio e o histórico de performance na UI,  
**para** acompanhar a evolução do capital e a qualidade das recomendações.

**Critérios de aceitação:**
- [ ] Página "Portfólio" mostra tabela de posições com: symbol, quantity, avg_price_brl, current_price_brl, P&L_brl, P&L_%
- [ ] Valor total do portfólio em BRL com variação vs. semana anterior
- [ ] Página "Performance" mostra: win rate, R-múltiplo médio, P&L total acumulado, drawdown máximo
- [ ] Gráfico de evolução do portfólio em BRL (semanal)
- [ ] Tabela de todos os trades fechados com outcome (win/loss/breakeven)

---

## EP-7: Seleção e Evolução

---

### US-020 — Performance tracker com win rate e R-múltiplo

**Como** usuário,  
**quero** que o sistema calcule automaticamente o win rate e o R-múltiplo acumulado das recomendações aceitas,  
**para** avaliar a qualidade do modelo e ajustar a estratégia ao longo do tempo.

**Critérios de aceitação:**
- [ ] `PerformanceTracker.record_close(trade_id, exit_price_brl)` calcula pnl_brl, pnl_pct, r_multiple e persiste em `performance_log`
- [ ] `PerformanceTracker.get_summary()` retorna: win_rate_pct, avg_r_multiple, total_pnl_brl, total_trades, open_trades
- [ ] Win rate calculado apenas sobre trades fechados (outcome ≠ "open")
- [ ] R-múltiplo = PnL_brl / (entry_price_brl - stop_loss_brl) × quantity
- [ ] Meta de 12-18 meses (R$3.000/mês de renda passiva) é exibida com progresso na UI
- [ ] Alerta no Streamlit se win rate < 40% ou R-múltiplo médio < 1.0 por 4 semanas consecutivas

---

## Priorização para Fase 1 (TDD)

```
Sprint 1 (semanas 1-2): Core pipeline
  US-002 → US-003 → US-005 → US-006 → US-013 → US-014

Sprint 2 (semanas 3-4): Exchange + Tax
  US-001 → US-004 → US-008 → US-009 → US-010

Sprint 3 (semanas 5-6): Output + UI
  US-016 → US-017 → US-018 → US-019 → US-020

Sprint 4 (semana 7): Polimento
  US-007 → US-011 → US-012 → US-015
```
