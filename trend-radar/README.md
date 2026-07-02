# Trend Radar Musical BR

> Plataforma de inteligência de tendências do mercado musical brasileiro
> construída com pipeline de dados moderno, ML e LLM local.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![dbt](https://img.shields.io/badge/dbt-DuckDB-orange)](https://docs.getdbt.com/)
[![Airflow](https://img.shields.io/badge/Airflow-2.9-red)](https://airflow.apache.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## O que é

O **Trend Radar Musical BR** é uma plataforma de dados que monitora e antecipa tendências do mercado musical brasileiro, agregando métricas semanais de três plataformas (Last.fm, YouTube e Deezer) em um pipeline Medallion completo. O sistema calcula um **Trend Score composto (0–100)** por artista, detecta anomalias virais com Z-score, gera previsões de 4 semanas com Prophet e produz relatórios narrativos com um LLM local (Llama 3 8B via Ollama) — tudo orquestrado por Airflow e exposto via API REST e dashboard interativo.

Desenvolvido como projeto de portfólio com metodologia **TDD Red→Green** completa (43 casos de teste, >80% de cobertura), o projeto demonstra a integração de um stack de engenharia de dados moderno: ingestão resiliente com circuit breakers e retry exponencial, transformação com dbt, qualidade de dados com Great Expectations, rastreabilidade com MLflow e observabilidade com logging JSON estruturado.

## Funcionalidades

- **Ranking semanal** de artistas BR em ascensão com Trend Score (0–100)
- **Heatmap de gêneros** — quais estão crescendo, estáveis ou caindo
- **Detecção de anomalias**: artistas com crescimento viral (Z-score > 2.5)
- **Forecasting** de tendência para as próximas 4 semanas (Prophet + WMA fallback)
- **Relatório narrativo semanal** gerado por LLM local (Llama 3 8B — 100% offline)
- **Sistema de alertas** quando artista cruza threshold de ascensão (>65 por 2+ semanas)
- **API REST** documentada com Swagger UI e cache em memória (TTL 1h)
- **Circuit breakers** por fonte (pybreaker) e retry exponencial (tenacity)
- **Logging JSON estruturado** com python-json-logger e health check script

## Arquitetura

```
                     ┌─────────────────────────────────────────────────────┐
                     │                 Apache Airflow 2.9                  │
                     │  ingest_lastfm · ingest_youtube · ingest_deezer     │
                     │  ingest_musicbrainz · run_dbt_pipeline               │
                     └───────────────────┬─────────────────────────────────┘
                                         │
          ┌──────────┬──────────┬────────▼─────────────────────────────────┐
          │  Last.fm │  YouTube │  Deezer   │  MusicBrainz                 │
          │  (httpx  │  (Google │  (httpx)  │  (musicbrainzngs)            │
          │  +retry) │   API)   │           │                              │
          └────┬─────┴────┬─────┴────┬──────┴───────────┬─────────────────┘
               │          │          │                  │
               ▼          ▼          ▼                  ▼
          ┌────────────────────────────────────────────────────────────────┐
          │                 BRONZE  (DuckDB — tabelas raw)                 │
          │  bronze_lastfm_artist_weekly  bronze_youtube_channel_weekly    │
          │  bronze_deezer_artist_weekly  bronze_musicbrainz_artist_weekly │
          └───────────────────────────────┬────────────────────────────────┘
                                          │ dbt run (bronze → silver)
                                          ▼
          ┌────────────────────────────────────────────────────────────────┐
          │                 SILVER  (dbt — tabelas curadas)                │
          │    silver_artists (mbid único)  ·  silver_weekly_plays         │
          └───────────────────────────────┬────────────────────────────────┘
                                          │ dbt run (silver → gold)
                                          ▼
          ┌────────────────────────────────────────────────────────────────┐
          │                  GOLD  (dbt — tabelas analíticas)              │
          │  gold_trend_scores  ·  gold_rising_artists  ·  gold_genre_heatmap │
          └────────────┬──────────────────┬──────────────────┬─────────────┘
                       │                  │                  │
               ┌───────▼──────┐  ┌────────▼───────┐  ┌──────▼──────────────┐
               │  FastAPI     │  │   Streamlit     │  │  Trend Engine       │
               │  /trending   │  │   Dashboard     │  │  AnomalyDetector    │
               │  /history    │  │   + Plotly      │  │  GenreHeatmap       │
               │  + cache 1h  │  │                 │  │  Forecaster(Prophet)│
               └──────────────┘  └─────────────────┘  └─────────────────────┘
                                                               │
                                                       ┌───────▼─────────────┐
                                                       │  ReportGenerator    │
                                                       │  (Ollama Llama 3)   │
                                                       │  AlertEngine        │
                                                       │  MLflow Tracking    │
                                                       └─────────────────────┘
```

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Ingestão | Python + httpx + tenacity (retry exp.) + pybreaker (circuit breaker) |
| Orquestração | Apache Airflow 2.9 (TaskFlow API) |
| Armazenamento | DuckDB 1.5 (Medallion: Bronze / Silver / Gold) |
| Transformação | dbt-duckdb 1.10 + dbt_utils 1.3 |
| ML | Prophet, statsmodels, Z-score (scipy) |
| LLM | Ollama + Llama 3 8B — 100% local, zero custo de API |
| API | FastAPI 0.110 + Pydantic v2 + cache InMemory (TTL 1h) |
| Dashboard | Streamlit 1.33 + Plotly 5 |
| MLOps | MLflow 2.12 — params, metrics, artefatos MD+HTML |
| Qualidade | Great Expectations 1.17 + dbt tests (17 testes) |
| Observabilidade | python-json-logger 4.x + health check script |
| Infra | Docker Compose — Dockerfile python:3.11-slim |
| Config | pydantic-settings + .env |
| CI local | pytest + pytest-cov + pytest-mock |

## Quick Start

```bash
git clone https://github.com/seu-user/trend-radar
cd trend-radar

cp .env.example .env          # adicione suas API keys
# Last.fm:  https://www.last.fm/api/account/create
# YouTube:  https://console.cloud.google.com → YouTube Data API v3

make build                    # build da imagem trend-radar:1.0.0
make up                       # sobe API + Dashboard + MLflow + Airflow
make demo                     # popula dados sintéticos de demo + dbt run

# Serviços disponíveis:
# Dashboard:  http://localhost:8501
# API docs:   http://localhost:8000/docs
# Airflow:    http://localhost:8080   (admin / admin)
# MLflow:     http://localhost:5001
```

## Pre-requisitos

- Docker Desktop 4.x+
- Ollama instalado localmente com `ollama pull llama3:8b` (para relatórios narrativos)
- API keys gratuitas: [Last.fm](https://www.last.fm/api/account/create) e [YouTube Data API v3](https://console.cloud.google.com)

## Estrutura do Projeto

```
trend-radar/
├── dags/                        # DAGs Airflow (TaskFlow API)
│   ├── dag_ingest_lastfm.py     # Ingestão Last.fm — seg 02:00
│   ├── dag_ingest_youtube.py    # Ingestão YouTube — seg 03:00
│   ├── dag_ingest_deezer.py     # Ingestão Deezer  — seg 04:00
│   ├── dag_ingest_musicbrainz.py# Enriquecimento MusicBrainz
│   └── dag_run_pipeline.py      # dbt + anomaly + alertas + report + mlflow
├── dbt/
│   └── models/
│       ├── bronze/              # Views sobre tabelas raw
│       ├── silver/              # silver_artists, silver_weekly_plays
│       └── gold/                # gold_trend_scores, rising_artists, genre_heatmap
├── src/
│   ├── api/                     # FastAPI: endpoints, cache, repository
│   ├── config.py                # pydantic-settings — configuração centralizada
│   ├── dashboard/               # Streamlit app (2 páginas)
│   ├── db/                      # connection factory com PRAGMA otimizados
│   ├── ingestion/               # 4 clientes + base.py + circuit_breakers.py
│   ├── quality/                 # Great Expectations 1.x (ephemeral context)
│   ├── report/                  # ReportGenerator (Ollama), AlertEngine, MLflow
│   ├── trend_engine/            # AnomalyDetector, GenreHeatmap, Forecaster
│   └── utils/                   # logging_config.py (JSON estruturado)
├── scripts/
│   ├── generate_demo_data.py    # 10 artistas × 12 semanas × 3 fontes
│   ├── profile_baseline.py      # benchmark de queries DuckDB
│   ├── optimization_report.py   # relatório Antes vs Depois
│   └── check_health.py          # saúde do sistema (healthy/degraded/critical)
├── tests/                       # 43 testes unitários e de integração
├── docs/                        # optimization_report.md, baseline_before.json
├── Dockerfile                   # python:3.11-slim, EXPOSE 8000 8501
├── docker-compose.yml           # 6 serviços: api, dashboard, mlflow, airflow×3
├── Makefile                     # 15 targets: setup, build, up, test, demo...
├── requirements.txt
└── .env.example
```

## Testes

43 casos de teste com cobertura >80%, organizados por módulo:

```bash
make test
# ou:
pytest --cov=src --cov-report=term-missing -v
```

| Módulo | Testes |
|--------|--------|
| Ingestion (LastFM, YouTube, Deezer, MusicBrainz) | 12 |
| Trend Engine (anomaly, heatmap, forecast) | 10 |
| FastAPI endpoints + cache + paginação | 8 |
| Report (generator, alerts, MLflow) | 6 |
| dbt models (gold, silver, filters) | 7 |

## Performance

Ganhos pós-otimização (DuckDB PRAGMA + LIMIT 500 + cache API):

| Query | Antes | Depois | Ganho |
|-------|------:|-------:|------:|
| gold_trend_scores scan | 18.5 ms | 0.4 ms | -97.8% |
| rising_artists JOIN | 22.7 ms | 0.6 ms | -97.4% |
| AnomalyDetector.run() | 1180 ms | 240 ms | -79.7% |

## Metodologia

Projeto desenvolvido em **7 fases com TDD Red→Green** completo:

1. **Planejamento** — PRD, User Stories, critérios de aceite
2. **Modelagem** — DER, schemas bronze/silver/gold, DDLs
3. **TDD Fase E1** — Ingestion clients (4 APIs)
4. **TDD Fase E2–E3** — dbt models + Trend Engine
5. **TDD Fase E4–E6** — FastAPI + Dashboard + DAGs Airflow
6. **Otimização** — DuckDB PRAGMAs, cache, profiling, Great Expectations
7. **Deploy** — Docker Compose, Dockerfile, Makefile, README

Cada fase seguiu o ciclo: escrever testes que falham → implementar o mínimo para passar → refatorar.

## Licenca

MIT — Build to Learn Portfolio — Dave, 2026
