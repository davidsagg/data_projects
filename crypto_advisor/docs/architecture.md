# CryptoAdvisor — Documento de Arquitetura

**Versão:** 0.1.0  
**Data:** 2026-05-12  
**Autor:** David Saggioro

---

## 1. Visão Geral

O CryptoAdvisor é um agente de análise e recomendação semanal de criptoativos para swing trading no mercado brasileiro. Opera localmente (MacBook M2), sem infraestrutura cloud, com custo marginal próximo de zero.

**Fluxo principal:** toda semana (domingo 18h), o sistema coleta dados de mercado, calcula indicadores técnicos, consulta o portfólio real na exchange, verifica o status fiscal do mês, envia tudo ao Claude Sonnet para análise e geração de recomendações em JSON estruturado, monta um relatório HTML e entrega via Telegram. O usuário aprova ou rejeita cada recomendação na UI Streamlit antes de qualquer execução.

---

## 2. Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CRYPTO ADVISOR                                  │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │  APScheduler │───▶│  Orchestrator│───▶│   Data Collection Layer  │  │
│  │  (domingo    │    │  (main flow) │    │                          │  │
│  │   18h)       │    └──────┬───────┘    │  ┌────────────────────┐  │  │
│  └──────────────┘           │            │  │  CoinGecko Client  │  │  │
│                             │            │  │  - Preços OHLCV    │  │  │
│                             │            │  │  - Market cap top20│  │  │
│                             │            │  │  - Fear & Greed    │  │  │
│                             │            │  └────────────────────┘  │  │
│                             │            │  ┌────────────────────┐  │  │
│                             │            │  │  MB API Client     │  │  │
│                             │            │  │  - Portfólio atual │  │  │
│                             │            │  │  - Histórico trades│  │  │
│                             │            │  └────────────────────┘  │  │
│                             │            └──────────────┬───────────┘  │
│                             │                           │               │
│                             ▼                           ▼               │
│                    ┌─────────────────┐    ┌────────────────────────┐   │
│                    │  Tax Optimizer  │    │  Technical Indicators  │   │
│                    │                 │    │                        │   │
│                    │  - Acumulador   │    │  - MM 9/21/200         │   │
│                    │    mensal BRL   │    │  - RSI (14)            │   │
│                    │  - Zonas:       │    │  - MACD (12/26/9)      │   │
│                    │    SAFE/WARNING/│    │  - Bollinger Bands     │   │
│                    │    CRITICAL/    │    │  - Volume médio        │   │
│                    │    BLOCKED      │    │  timeframes: 4h + 1d   │   │
│                    │  - Loss harvest │    └──────────┬─────────────┘   │
│                    └────────┬────────┘               │                 │
│                             │                        │                 │
│                             └───────────┬────────────┘                 │
│                                         │                               │
│                                         ▼                               │
│                             ┌───────────────────────┐                  │
│                             │  Claude Sonnet Engine  │                  │
│                             │  (claude-sonnet-4-6)   │                  │
│                             │                        │                  │
│                             │  Input:                │                  │
│                             │  - OHLCV + indicadores │                  │
│                             │  - Portfólio atual     │                  │
│                             │  - Status fiscal       │                  │
│                             │  - Fear & Greed        │                  │
│                             │  - Top-20 market cap   │                  │
│                             │                        │                  │
│                             │  Output JSON:          │                  │
│                             │  - action BUY/SELL/... │                  │
│                             │  - entry/stop/target   │                  │
│                             │  - risk_reward_ratio   │                  │
│                             │  - tax_impact          │                  │
│                             │  - reasoning           │                  │
│                             └───────────┬────────────┘                  │
│                                         │                               │
│                          ┌──────────────┴──────────────┐               │
│                          │                             │               │
│                          ▼                             ▼               │
│               ┌──────────────────┐        ┌───────────────────────┐   │
│               │  Report Builder  │        │      SQLite DB         │   │
│               │  (Jinja2 HTML)   │        │                        │   │
│               └────────┬─────────┘        │  portfolio             │   │
│                        │                  │  recommendations       │   │
│                        ▼                  │  trades                │   │
│               ┌──────────────────┐        │  tax_tracker           │   │
│               │  Telegram Bot    │        │  performance_log       │   │
│               │  (entrega report │        │  market_snapshots      │   │
│               │   + alertas tax) │        └──────────┬────────────┘   │
│               └──────────────────┘                   │                 │
│                                                       ▼                 │
│                                            ┌──────────────────────┐    │
│                                            │    Streamlit UI       │    │
│                                            │                       │    │
│                                            │  - Aprovar/Rejeitar  │    │
│                                            │    recomendações      │    │
│                                            │  - Dashboard portfólio│    │
│                                            │  - Performance log   │    │
│                                            │  - Tax status        │    │
│                                            └──────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘

          Dados externos             Runtime local             UI
  ┌──────────────────────┐    ┌────────────────────┐   ┌────────────┐
  │ CoinGecko API        │    │ MacBook M2 24GB     │   │ Browser    │
  │ Mercado Bitcoin API  │───▶│ Python 3.12        │───▶│ localhost  │
  │ Telegram servers     │    │ SQLite WAL          │   │ :8501      │
  └──────────────────────┘    └────────────────────┘   └────────────┘
```

---

## 3. Módulos e Responsabilidades

### `data/coingecko.py` — CoinGecko Client
- Busca preços atuais de BTC, ETH, SOL + top-20 por market cap
- Busca dados OHLCV históricos (4h e diário) para cálculo de indicadores
- Busca Fear & Greed Index (alternative.me)
- Implementa cache local de 1h para evitar rate-limiting na tier gratuita

### `data/mercado_bitcoin.py` — MB API Client
- Autentica via HMAC-SHA256 com MB_API_ID + MB_API_SECRET
- Lê saldo atual de cada ativo no portfólio
- Importa histórico de trades do mês corrente para sincronizar o `tax_tracker`
- Consulta book de ordens para validar liquidez antes de recomendar entrada

### `indicators/technical.py` — Technical Indicators
- Recebe DataFrame com OHLCV e calcula todos os indicadores via `pandas-ta`
- Retorna DataFrame enriquecido com colunas nomeadas de forma consistente
- Suporta múltiplos timeframes (4h, diário) produzindo um snapshot por ativo

### `tax/optimizer.py` — Tax Optimizer
- Consulta `tax_tracker` no SQLite para obter total vendido no mês corrente
- Determina a zona (SAFE/WARNING/CRITICAL/BLOCKED)
- Produz `TaxContext` estruturado para injeção no prompt do Claude
- Implementa lógica de loss harvesting: identifica posições com prejuízo não realizado
- Dispara alertas Telegram quando o status muda de zona

### `advisor.py` — Claude Recommendation Engine
- Monta o prompt estruturado com todos os dados coletados
- Usa prompt caching no system prompt (cache_control: ephemeral)
- Parseia o JSON de saída e valida via Pydantic
- Persiste a recomendação no SQLite com status `pending`

### `reporting/report.py` — Report Builder
- Carrega o template Jinja2 `weekly_report.html.j2`
- Injeta dados do portfólio, recomendações, indicadores e status fiscal
- Salva o HTML em `data/reports/YYYY-MM-DD.html`
- Gera também a versão resumida em Markdown para o Telegram

### `notification/telegram.py` — Telegram Delivery
- Envia o resumo Markdown do relatório semanal via Bot API
- Envia alertas de mudança de zona fiscal (WARNING, CRITICAL, BLOCKED)
- Inclui link deep para a UI Streamlit de validação

### `ui/app.py` — Streamlit UI
- Dashboard de portfólio com posições abertas e P&L não realizado
- Listagem das recomendações pendentes com botões Aprovar/Rejeitar
- Histórico de performance com win rate e R-múltiplo acumulado
- Painel de status fiscal com gauge visual das zonas

### `db/schema.py` e `db/repository.py` — Persistência
- `schema.py`: DDL + `init_db()` — única fonte de verdade do schema
- `repository.py`: operações CRUD tipadas para cada tabela (sem ORM)

### `scheduler.py` — APScheduler trigger
- Configura o job semanal: domingo 18h
- Gerencia retry em caso de falha
- Log de execuções em `data/logs/scheduler.log`

---

## 4. Fluxo do Tax Optimizer

```
Início de cada análise semanal
          │
          ▼
  ┌───────────────────────────────────────┐
  │  Consultar tax_tracker no SQLite       │
  │  total_sold_brl do mês/ano/exchange    │
  └───────────────┬───────────────────────┘
                  │
          ┌───────┴────────────────────────────────────────┐
          │                                                │
          ▼                                                │
  total_sold_brl < R$28.000?                               │
    SIM → zona SAFE                                        │
    NÃO → continuar                                        │
          │                                                │
          ▼                                                │
  total_sold_brl < R$33.000?                               │
    SIM → zona WARNING                                     │
          │  • Alertar via Telegram                        │
          │  • Claude prioriza loss harvest                │
          │  • Reduz tamanho de posições novas             │
    NÃO → continuar                                        │
          │                                                │
          ▼                                                │
  total_sold_brl < R$35.000?                               │
    SIM → zona CRITICAL                                    │
          │  • Alertar via Telegram (urgente)              │
          │  • Claude APENAS sugere loss harvest           │
          │  • Bloqueia recomendações BUY com gain         │
    NÃO → zona BLOCKED                                     │
               │  • Alertar via Telegram (bloqueio)        │
               │  • Claude analisa apenas compras          │
               │  • NENHUMA venda aprovada este mês        │
               │                                          │
               └──────────────────────────────────────────┘
                          │
                          ▼
                  Incluir TaxContext no prompt Claude:
                  {
                    zona: "SAFE" | "WARNING" | "CRITICAL" | "BLOCKED",
                    total_vendido_brl: 12400.00,
                    limite_brl: 35000.00,
                    margem_disponivel_brl: 22600.00,
                    instrucao: "...",
                    candidatos_loss_harvest: ["SOL", "MATIC"]
                  }
```

---

## 5. Schema do SQLite

### `portfolio`
| Coluna          | Tipo      | Descrição                              |
|-----------------|-----------|----------------------------------------|
| id              | INTEGER PK| Auto-increment                         |
| symbol          | TEXT      | Ex: "BTC", "ETH"                       |
| quantity        | REAL      | Quantidade em custódia                 |
| avg_price_brl   | REAL      | Preço médio de compra em BRL           |
| exchange        | TEXT      | Default: "mercado_bitcoin"             |
| updated_at      | TIMESTAMP | Última sincronização com MB API        |

### `recommendations`
| Coluna           | Tipo      | Descrição                                        |
|------------------|-----------|--------------------------------------------------|
| id               | INTEGER PK|                                                  |
| week_date        | DATE      | Data do domingo da análise                       |
| symbol           | TEXT      | Ativo analisado                                  |
| action           | TEXT      | BUY / SELL / HOLD / SKIP                         |
| entry_price_usd  | REAL      | Ponto de entrada sugerido (USD)                  |
| stop_loss_usd    | REAL      | Stop loss (USD)                                  |
| target_price_usd | REAL      | Alvo de saída (USD)                              |
| risk_reward_ratio| REAL      | (target-entry)/(entry-stop)                      |
| confidence       | TEXT      | high / medium / low                              |
| timeframe        | TEXT      | "swing" (1 semana típico)                        |
| reasoning        | TEXT      | Justificativa do Claude                          |
| tax_impact       | TEXT      | Descrição do impacto fiscal                      |
| raw_json         | TEXT      | JSON bruto retornado pelo Claude                 |
| status           | TEXT      | pending / approved / rejected / executed         |
| created_at       | TIMESTAMP |                                                  |
| reviewed_at      | TIMESTAMP | Quando aprovado/rejeitado pelo usuário           |
| reviewed_by      | TEXT      | "streamlit_ui" ou "telegram"                     |

### `trades`
| Coluna            | Tipo      | Descrição                               |
|-------------------|-----------|-----------------------------------------|
| id                | INTEGER PK|                                         |
| symbol            | TEXT      |                                         |
| side              | TEXT      | buy / sell                              |
| quantity          | REAL      |                                         |
| price_brl         | REAL      | Preço de execução em BRL                |
| total_brl         | REAL      | quantity × price_brl                    |
| fee_brl           | REAL      | Taxa de corretagem                      |
| exchange          | TEXT      |                                         |
| traded_at         | TIMESTAMP | Timestamp da execução na exchange       |
| recommendation_id | INTEGER FK| Recomendação que originou o trade       |

### `tax_tracker`
| Coluna             | Tipo      | Descrição                                   |
|--------------------|-----------|---------------------------------------------|
| id                 | INTEGER PK|                                             |
| year               | INTEGER   | Ex: 2026                                    |
| month              | INTEGER   | 1–12                                        |
| exchange           | TEXT      | Por exchange (limite é individual)          |
| total_sold_brl     | REAL      | Soma de todas as vendas do mês em BRL       |
| realized_gain_brl  | REAL      | Ganho realizado acumulado no mês            |
| realized_loss_brl  | REAL      | Perda realizada acumulada no mês            |
| tax_status         | TEXT      | safe / warning / critical / blocked         |
| updated_at         | TIMESTAMP |                                             |

### `performance_log`
| Coluna            | Tipo      | Descrição                                |
|-------------------|-----------|------------------------------------------|
| id                | INTEGER PK|                                          |
| week_date         | DATE      |                                          |
| recommendation_id | INTEGER FK|                                          |
| symbol            | TEXT      |                                          |
| entry_price_brl   | REAL      | Preço de entrada em BRL                  |
| exit_price_brl    | REAL      | Preço de saída em BRL                    |
| quantity          | REAL      |                                          |
| pnl_brl           | REAL      | P&L realizado em BRL                     |
| pnl_pct           | REAL      | P&L percentual                           |
| r_multiple        | REAL      | PnL / (entry - stop) × qty              |
| outcome           | TEXT      | win / loss / breakeven / open            |
| closed_at         | TIMESTAMP |                                          |

### `market_snapshots`
| Coluna          | Tipo      | Descrição                              |
|-----------------|-----------|----------------------------------------|
| id              | INTEGER PK|                                        |
| symbol          | TEXT      |                                        |
| timeframe       | TEXT      | "4h" ou "1d"                           |
| fetched_at      | TIMESTAMP | Quando os dados foram coletados        |
| ohlcv_json      | TEXT      | Array JSON de candles OHLCV            |
| indicators_json | TEXT      | JSON com valores calculados de MM/RSI/MACD/BB |

---

## 6. Decisões de Design

- **Human-in-the-loop obrigatório:** o sistema nunca executa um trade. Toda recomendação fica em status `pending` até aprovação explícita na UI Streamlit
- **Sem ORM:** repositório usa `sqlite3` diretamente para manter a dependência zero e queries transparentes
- **Prompt caching:** o system prompt do Claude (análise de mercado ~2k tokens) é marcado como `ephemeral` para aproveitar o cache de 5 min da Anthropic API, reduzindo custo em ~90%
- **Seleção dinâmica de ativos:** BTC, ETH, SOL são fixos; os demais 7–17 ativos são selecionados semanalmente com base no top-20 CoinGecko por market cap, filtrando os que já estão no portfólio e os com volume < $10M/dia
