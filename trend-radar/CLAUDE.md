# Trend Radar Musical BR — Guia para o Claude Code CLI

Plataforma de inteligência de tendências do mercado musical brasileiro. Pipeline Medallion completo com ML, LLM local e dashboard interativo.

---

## Ambiente

- **Workspace no container:** `/app`
- **DuckDB:** `/workspace/data/trend_radar.duckdb`
- **Executar testes:** `pytest tests/ -v` ou `make test`
- **Cobertura:** `pytest --cov=src --cov-report=term-missing -v` ou `make coverage`
- **Linter/formatter:** não configurado (sem ruff/black explícito — verificar antes de formatar)
- **AI local:** Ollama em `http://host.docker.internal:11434` (llama3:8b)
- **Variáveis de ambiente:** `.env` — ver `.env.example` para referência
- **Iniciar serviços:** `make up` (Docker Compose com 6 serviços)
- **Demo com dados sintéticos:** `make demo`
- **Health check:** `python scripts/check_health.py`

---

## Stack

| Camada | Tecnologia |
|---|---|
| Ingestão | httpx + tenacity (retry exponencial) + pybreaker (circuit breaker) |
| Orquestração | Apache Airflow 2.9 (TaskFlow API) |
| Armazenamento | DuckDB 1.5 — Medallion Bronze / Silver / Gold |
| Transformação | dbt-duckdb 1.10 + dbt_utils 1.3 |
| ML | Prophet (forecast 4 semanas), Z-score/scipy (anomalia), statsmodels |
| LLM | Ollama + Llama 3 8B — 100% local, zero custo de API |
| API | FastAPI 0.110 + Pydantic v2 + cache InMemory (TTL 1h) |
| Dashboard | Streamlit 1.33 + Plotly 5 |
| MLOps | MLflow 2.12 — params, metrics, artefatos MD+HTML |
| Qualidade | Great Expectations 1.17 + dbt tests (17 testes dbt) |
| Observabilidade | python-json-logger 4.x (JSON estruturado) + health check script |
| Infra | Docker Compose — 6 serviços: api, dashboard, mlflow, airflow×3 |

---

## Arquitetura Medallion (DuckDB)

```
Fontes externas
  └─ Last.fm · YouTube · Deezer · MusicBrainz
       │
       ▼ (DAGs Airflow — ingestão semanal)
  BRONZE — tabelas raw
    bronze_lastfm_artist_weekly
    bronze_youtube_channel_weekly
    bronze_deezer_artist_weekly
    bronze_musicbrainz_artist_weekly
       │
       ▼ (dbt bronze → silver)
  SILVER — tabelas curadas
    silver_artists (mbid único, deduplicado por fonte)
    silver_weekly_plays
       │
       ▼ (dbt silver → gold)
  GOLD — tabelas analíticas
    gold_trend_scores    ← Trend Score composto (0–100) por artista
    gold_rising_artists  ← artistas em ascensão (threshold >65 por 2+ semanas)
    gold_genre_heatmap   ← gêneros crescendo / estáveis / caindo
```

---

## Estrutura do projeto

```
dags/
  dag_ingest_lastfm.py      ← seg 02:00
  dag_ingest_youtube.py     ← seg 03:00
  dag_ingest_deezer.py      ← seg 04:00
  dag_ingest_musicbrainz.py ← enriquecimento
  dag_run_pipeline.py       ← dbt + anomaly + alertas + report + mlflow
dbt/
  models/
    bronze/                 ← views sobre tabelas raw
    silver/                 ← silver_artists, silver_weekly_plays
    gold/                   ← gold_trend_scores, rising_artists, genre_heatmap
src/
  api/                      ← FastAPI: main.py, routers, repository, cache
  config.py                 ← pydantic-settings (configuração centralizada)
  dashboard/                ← Streamlit app (2 páginas)
  db/                       ← connection factory com PRAGMAs otimizados
  ingestion/                ← base.py + 4 clientes + circuit_breakers.py
  nlp/                      ← processamento de linguagem natural
  quality/                  ← Great Expectations 1.x (ephemeral context)
  report/                   ← ReportGenerator (Ollama), AlertEngine, MLflow
  trend_engine/             ← AnomalyDetector, GenreHeatmap, Forecaster
  utils/                    ← logging_config.py (JSON estruturado)
scripts/
  generate_demo_data.py     ← 10 artistas × 12 semanas × 3 fontes
  profile_baseline.py       ← benchmark de queries DuckDB
  optimization_report.py    ← relatório Antes vs Depois
  check_health.py           ← saúde do sistema (healthy/degraded/critical)
tests/                      ← 43 casos de teste (>80% cobertura)
docs/
  optimization_report.md    ← resultados de otimização DuckDB
  baseline_before.json      ← baseline de performance pré-otimização
```

---

## Serviços Docker (portas)

| Serviço | URL |
|---|---|
| FastAPI | http://localhost:8000/docs |
| Streamlit | http://localhost:8501 |
| MLflow | http://localhost:5002 |
| Airflow | http://localhost:8080 (admin / admin) |

---

## Testes

43 casos de teste organizados por módulo:

| Arquivo | Foco |
|---|---|
| `test_ingestion_lastfm.py` | Cliente Last.fm + circuit breaker |
| `test_ingestion_youtube.py` | Cliente YouTube + retry |
| `test_ingestion_deezer_mbz.py` | Clientes Deezer e MusicBrainz |
| `test_trend_engine.py` | AnomalyDetector, GenreHeatmap, Forecaster |
| `test_api.py` | Endpoints FastAPI + cache + paginação |
| `test_report_alerts_mlflow.py` | ReportGenerator + AlertEngine + MLflow |
| `test_dbt_models.py` | Modelos gold/silver via DuckDB in-memory |

**Marcadores pytest:**
- `unit` — sem I/O externo
- `integration` — DuckDB real
- `dbt` — modelos dbt

---

## Convenções de código

- **Tipagem:** type hints obrigatórios em funções públicas
- **Docstrings:** Google style, em português
- **Logging:** sempre via `logging_config.py` (JSON estruturado) — nunca `print()`
- **Config:** sempre via `src/config.py` (pydantic-settings) — nunca hardcode de env vars
- **DB:** sempre via `src/db/` (connection factory) — nunca abrir `duckdb.connect()` diretamente nas rotas
- **Circuit breakers:** já configurados em `src/ingestion/circuit_breakers.py` — usar para todas as chamadas externas
- **MLflow:** logar experimentos via `src/report/` — não inline em DAGs

---

## Status atual

Projeto **completo** como portfólio TDD. Todas as 7 fases implementadas:

1. ✅ Planejamento — PRD, User Stories, critérios de aceite
2. ✅ Modelagem — DER, schemas bronze/silver/gold, DDLs
3. ✅ Ingestion clients (Last.fm, YouTube, Deezer, MusicBrainz)
4. ✅ dbt models + Trend Engine (anomaly, heatmap, forecast)
5. ✅ FastAPI + Dashboard Streamlit + DAGs Airflow
6. ✅ Otimização — DuckDB PRAGMAs, cache, profiling, Great Expectations
7. ✅ Deploy — Docker Compose, Dockerfile, Makefile, README

**Ganhos de performance pós-otimização:**
- `gold_trend_scores` scan: 18.5 ms → 0.4 ms (−97.8%)
- `rising_artists` JOIN: 22.7 ms → 0.6 ms (−97.4%)
- `AnomalyDetector.run()`: 1180 ms → 240 ms (−79.7%)

---

## Contexto importante

- O `genre_heatmap.py` tem dual-path em `compute()` — um para produção e outro para testes (ver commit mais recente)
- O endpoint `/history` e o dashboard foram alinhados ao schema real de `gold_rising_artists` (não ao schema do ERD inicial)
- `read_only=True` no DuckDB da API para coexistir com processos Airflow (single-writer)
- Dados sintéticos gerados por `scripts/generate_demo_data.py` — rodar `make demo` antes de testar o dashboard sem dados reais
