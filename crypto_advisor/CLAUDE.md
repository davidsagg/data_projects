# CryptoAdvisor

Agente de análise e recomendação semanal de criptoativos para swing trading no
Mercado Bitcoin, com tax optimization automático para isenção de IR (IN RFB 2.312/2026).

## Setup rápido

```bash
# 1. Copie e preencha as variáveis de ambiente
cp .env.example .env
# edite .env com: ANTHROPIC_API_KEY, MB_API_ID, MB_API_SECRET,
#                 MB_TAPI_ID, MB_TAPI_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# 2. Instale dependências
pip install -e ".[dev]"

# 3. Valide conectividade com todas as APIs
python -m crypto_advisor --smoke-test

# 4. Execute a primeira análise imediatamente (sem esperar domingo)
python -m crypto_advisor --run-now
```

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Runtime | Python 3.12 |
| AI engine | `anthropic` SDK — claude-sonnet-4-6 |
| Validação | `pydantic` v2 |
| Indicadores técnicos | `pandas-ta` (fallback pure-pandas) |
| Exchange | Mercado Bitcoin API v4 + TAPI v3 |
| Market data | CoinGecko API (free tier) |
| Notificação | `python-telegram-bot` |
| UI de validação | `streamlit` |
| Agendamento | `apscheduler` (domingo 18h BRT) |
| Templates | `jinja2` |
| Persistência | SQLite (WAL mode) |

## Estrutura do projeto

```
crypto_advisor/
├── src/crypto_advisor/
│   ├── __main__.py           # Entry point (CLI)
│   ├── advisor.py            # Claude recommendation engine + prompt builder
│   ├── models.py             # Todos os modelos Pydantic
│   ├── scheduler.py          # Pipeline semanal + APScheduler
│   ├── data/
│   │   ├── coingecko.py      # CoinGecko API client (preços, OHLCV, Fear&Greed)
│   │   ├── mercado_bitcoin.py# MB API client (portfólio, trades)
│   │   └── asset_selector.py # Seleção dinâmica de ativos (top-20 + âncoras)
│   ├── indicators/
│   │   └── technical.py      # MM9/21/200, RSI, MACD, Bollinger Bands
│   ├── tax/
│   │   └── optimizer.py      # Tax Optimizer (zonas, loss harvest, income strategy)
│   ├── reporting/
│   │   ├── report.py         # HTML report (Jinja2) + Telegram summary
│   │   └── templates/
│   │       └── weekly_report.html.j2
│   ├── notification/
│   │   └── telegram.py       # Entrega Telegram + alertas fiscais
│   ├── ui/
│   │   └── app.py            # Streamlit UI (aprovar/rejeitar + dashboards)
│   └── db/
│       ├── schema.py         # DDL SQLite (6 tabelas) + init_db()
│       └── repository.py     # CRUD tipado (sem ORM)
├── tests/                    # 290 testes — pytest
├── scripts/
│   └── smoke_test.py         # Validação de conectividade das APIs
├── docs/
│   ├── architecture.md       # Diagrama de componentes + schema SQLite
│   ├── user-stories.md       # 20 User Stories com critérios de aceitação
│   └── adrs/                 # 6 Architecture Decision Records
├── data/                     # Runtime: banco SQLite + relatórios HTML
├── .env.example
└── pyproject.toml
```

## Comandos

```bash
# Análise e entrega
python -m crypto_advisor               # inicia o scheduler (domingo 18h)
python -m crypto_advisor --run-now     # executa análise imediatamente
python -m crypto_advisor --status      # exibe portfólio, tax e próximo run
python -m crypto_advisor --smoke-test  # valida conectividade das APIs

# UI de validação (aprovar/rejeitar recomendações)
streamlit run src/crypto_advisor/ui/app.py

# Desenvolvimento
pytest                     # 290 testes
ruff check .               # lint
mypy src/                  # type-check
python scripts/smoke_test.py  # smoke test manual
```

## Fluxo semanal (domingo 18h)

```
MB API → portfólio + trades
       ↓
CoinGecko → preços + OHLCV + Fear&Greed
       ↓
AssetSelector → top-20 filtrado (anchors BTC/ETH/SOL + dinâmicos)
       ↓
TechnicalIndicators → MM9/21/200, RSI, MACD, Bollinger Bands (4h + diário)
       ↓
TaxOptimizer → zona SAFE/WARNING/CRITICAL/BLOCKED + candidatos loss harvest
       ↓
Claude Sonnet → recomendações JSON (entry/stop/target/RR/tax_impact)
       ↓
SQLite → recomendações persistidas com status 'pending'
       ↓
Jinja2 → relatório HTML salvo em data/reports/YYYY-MM-DD.html
       ↓
Telegram → resumo entregue ao usuário
       ↓
Streamlit → usuário aprova/rejeita cada recomendação (human-in-the-loop)
```

## Tax Optimizer — zonas

| Zona | Vendido BRL/mês | Ação |
|------|----------------|------|
| SAFE | < R$ 28.000 | Opera normalmente |
| WARNING | R$ 28k – R$ 33k | Prioriza loss harvesting |
| CRITICAL | R$ 33k – R$ 35k | Apenas loss harvesting |
| BLOCKED | ≥ R$ 35.000 | Nenhuma venda este mês |

Referência legal: IN RFB 2.312/2026 (isenção por exchange/mês).

## Guidelines

- `ANTHROPIC_API_KEY` e credenciais MB/Telegram sempre via `.env`, nunca hardcoded
- Prompt caching habilitado no system prompt (`cache_control: ephemeral`)
- Human-in-the-loop obrigatório: o sistema **nunca executa trades** — apenas recomenda
- MM200 retorna `None` no CoinGecko free tier (< 200 candles); alinhamento = "mixed"
- Limite de rate do CoinGecko free tier: ~30 req/min — espere ≥ 2 min entre smoke tests
- Todos os modelos de dados passam por Pydantic antes de persistir ou enviar ao Claude
- Repositório usa `sqlite3` direto (sem ORM) — queries legíveis e auditáveis
