# VeloDNA — Guia para o Claude Code CLI

Plataforma local de performance ciclística. Privacidade-first: dados de saúde e treino nunca saem do dispositivo.

**Versão atual:** v1.1.0 · **Testes:** 89 passando

---

## Ambiente

- **Diretório do projeto:** `velodna/` (dev local)
- **Python:** 3.11 · venv em `.venv`
- **Executar testes:** `.venv/bin/pytest tests/ -v`
- **Linter/formatter:** `ruff check src/ tests/` e `ruff format src/ tests/`
- **Banco de dados:** DuckDB — arquivo único em `data/velodna.duckdb` (ignorado pelo git)
- **AI local:** Ollama em `http://localhost:11434` (llama3:latest, fallback mistral:latest)
- **Variáveis de ambiente:** definidas em `.env` (não commitado) — ver `.env.example` se existir

### Iniciar serviços

```bash
# API (porta 8000)
uvicorn src.api.main:app --reload

# Frontend React (porta 5173)
cd frontend && npm run dev

# Airflow + MLflow: o docker-compose ficava no .devcontainer (removido na migração local).
# Recriar um docker-compose.yml no projeto se precisar orquestrar (não é necessário p/ o core).
```

---

## Stack e ADRs

| Decisão | Escolha | ADR |
|---|---|---|
| Banco de dados | DuckDB embarcado (arquivo único, OLAP, zero infra) | `docs/adr/ADR-001-duckdb.md` |
| Inferência de IA | Ollama local (llama3/mistral, privacidade total) | `docs/adr/ADR-002-ollama-local-ai.md` |
| API | FastAPI + uvicorn | — |
| Frontend | React 19 + Vite + Recharts + react-leaflet | — |
| Orquestração | Apache Airflow 3.x DAGs em `dags/` | — |
| Transformações SQL | dbt-duckdb em `dbt/` | — |
| Experiment tracking | MLflow (backend local `mlflow/mlruns/`) | — |

---

## Estrutura do projeto

```
src/
  ingestion/       ← fit_parser, gpx_loader, garmin_health_client, strava_client, pipeline
  storage/         ← CatalogStore autoritativo (DuckDB DDL + CRUD)
  analytics/       ← PMCCalculator, PowerCurveEngine, ZoneAnalyzer, WPrimeModel, FTPDetector, VeloDNATracker (MLflow)
  api/             ← FastAPI app + 5 routers (activities, analytics, health, routes, coach)
  routes/          ← GPXAnalyzer, SegmentClassifier, PacingStrategy, TimeEstimator
  health/          ← SleepCorrelator, HRVTrendAnalyzer, ReadinessCalculator
  ai/              ← OllamaClient, ContextBuilder, PostActivityCoach, WeeklyPlanCoach
frontend/
  src/
    App.jsx                      ← layout com 3 abas: Visão Geral / Atividade / Coach
    components/
      ReadinessCard.jsx          ← score de recuperação diário (GET /readiness/today)
      PMCChart.jsx               ← CTL/ATL/TSB histórico (GET /pmc)
      PowerCurveChart.jsx        ← curva MMP (GET /power-curve)
      ActivityList.jsx           ← lista clicável de atividades (GET /activities)
      RouteMap.jsx               ← mapa GPS dinâmico (GET /activities/{id}/streams)
      ZoneChart.jsx              ← zonas de potência Coggan (GET /activities/{id}/zones)
      HRVTrendCard.jsx           ← tendência HRV 30 dias (GET /health-daily)
      CoachPanel.jsx             ← insight pós-atividade via Ollama (POST /coach/analyze-activity)
tests/
  unit/            ← 17 arquivos de teste (84 casos)
  integration/     ← pipeline end-to-end
  fixtures/        ← sample.fit, sample.gpx, sample_invalid.fit
dags/
  fit_sync_dag.py        ← velodna_fit_sync: scan → parse FIT → update_metrics (@daily)
  health_sync_dag.py     ← velodna_health_sync: sync Garmin health (@daily)
dbt/
  dbt_project.yml
  models/
    weekly_summary.sql   ← TSS e km por semana
    athlete_profile.sql  ← join athlete_metrics + health_daily
docs/
  adr/             ← ADR-001 (DuckDB), ADR-002 (Ollama)
  architecture/    ← erd.md, system-flow.md
  user-stories/    ← 18 US em 4 módulos
data/              ← fit/, gpx/, velodna.duckdb (ignorados pelo git)
```

---

## API REST — endpoints implementados

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/health` | Healthcheck |
| GET | `/activities` | Lista atividades (filtro `start`, `end`) |
| GET | `/activities/latest` | Atividade mais recente |
| GET | `/activities/{id}/streams` | Streams GPS decimados (`every_n`) |
| GET | `/activities/{id}/zones` | Distribuição por zona de potência Coggan |
| POST | `/activities/ingest/fit` | Upload .FIT → persiste + recalcula PMC |
| GET | `/pmc` | Série histórica CTL/ATL/TSB |
| GET | `/power-curve` | Curva MMP ordenada por duração |
| GET | `/health-daily` | Últimos N registros de saúde Garmin |
| GET | `/readiness/today` | Score de recuperação do dia |
| POST | `/routes/analyze` | Upload GPX → perfil de elevação |
| POST | `/coach/analyze-activity` | Análise de atividade via Ollama |

---

## Schema do banco (DuckDB)

Tabelas principais — ver `docs/schema.sql` e `src/storage/catalog_store.py` para DDL completo:

- `athletes` — perfil do atleta (FTP, peso, FC max)
- `activities` — resumo de cada atividade (TSS, NP, IF, distância, elevação)
- `activity_streams` — série temporal por atividade (power, HR, cadência, GPS, altitude)
- `health_daily` — métricas diárias Garmin (HRV, sono, FC repouso, body battery)
- `athlete_metrics` — CTL / ATL / TSB / ftp_w por data
- `power_curve` — melhores potências por duração (MMP)
- `routes` — rotas GPX analisadas
- `route_segments` — segmentos de 500 m de cada rota
- `segments` + `segment_efforts` — segmentos pessoais e histórico de passagens
- `ai_conversations` + `ai_insights` — histórico do AI Coach

---

## Status de implementação

| Módulo | Arquivo(s) | Status |
|---|---|---|
| Storage (DuckDB) | `src/storage/catalog_store.py` | ✅ Completo |
| Parser FIT | `src/ingestion/fit_parser.py` | ✅ Completo |
| Loader GPX | `src/ingestion/gpx_loader.py` | ✅ Completo |
| Cliente Garmin | `src/ingestion/garmin_health_client.py` | ✅ Completo |
| Cliente Strava | `src/ingestion/strava_client.py` | ✅ Esqueleto |
| Pipeline de ingestão | `src/ingestion/pipeline.py` | ✅ Completo |
| PMC Calculator (CTL/ATL/TSB) | `src/analytics/pmc_calculator.py` | ✅ Completo |
| Power Curve Engine | `src/analytics/power_curve_engine.py` | ✅ Completo |
| Zone Analyzer (Coggan) | `src/analytics/zone_analyzer.py` | ✅ Completo |
| W' Prime Model | `src/analytics/wprime_model.py` | ✅ Completo |
| FTP Detector | `src/analytics/pmc_calculator.py` (FTPDetector) | ✅ Completo |
| MLflow Tracker | `src/analytics/mlflow_tracker.py` | ✅ Completo |
| GPX Analyzer | `src/routes/gpx_analyzer.py` | ✅ Completo |
| Segment Classifier | `src/routes/segment_classifier.py` | ✅ Completo |
| Pacing Strategy | `src/routes/pacing_strategy.py` | ✅ Completo |
| Time Estimator | `src/routes/time_estimator.py` | ✅ Completo |
| Sleep Correlator | `src/health/sleep_correlator.py` | ✅ Completo |
| HRV Trend Analyzer | `src/health/hrv_trend.py` | ✅ Completo |
| Readiness Calculator | `src/health/readiness.py` | ✅ Completo |
| Ollama Client | `src/ai/ollama_client.py` | ✅ Completo |
| Context Builder | `src/ai/context_builder.py` | ✅ Completo |
| Post Activity Coach | `src/ai/post_activity_coach.py` | ✅ Completo |
| Weekly Plan Coach | `src/ai/weekly_plan_coach.py` | ✅ Completo |
| FastAPI app + routers | `src/api/` | ✅ Completo |
| Frontend React (8 componentes) | `frontend/src/` | ✅ Completo |
| Airflow DAGs | `dags/` | ✅ Completo |
| dbt models | `dbt/models/` | ✅ Completo |
| US-04 Comparação de atividades | — | ⏳ Pendente |
| US-05 Exportação CSV | — | ⏳ Pendente |
| US-07/08 Segmentos pessoais | — | ⏳ Pendente |
| US-12 Correlação sono/performance | — | ⏳ Pendente |
| US-13 Alerta overreaching | `src/health/overreaching_alerts.py` + `GET /health/alerts` | ✅ Completo |
| US-14 Chat livre com coach | — | ⏳ Pendente |
| US-16 Periodização semanal | `POST /coach/weekly-plan` | ✅ Completo |
| US-17 Nutrição para treinos longos | `POST /coach/nutrition-advice` | ✅ Completo |
| US-18 Risco de lesão | `src/ai/injury_risk_coach.py` + `POST /coach/assess-injury-risk` + DAG semanal | ✅ Completo |

---

## User Stories e módulos

18 User Stories em 4 módulos — ver `docs/user-stories/user-stories.md`.

- **Módulo 1 — Training Analytics** (US-01 a US-05): upload FIT/GPX ✅, zonas de potência ✅, CTL/ATL/TSB ✅, comparação de atividades ⏳, exportação CSV ⏳
- **Módulo 2 — Route Intelligence** (US-06 a US-09): perfil de elevação ✅, segmentos pessoais ⏳, histórico em segmentos ⏳, pacing strategy ✅ (backend)
- **Módulo 3 — Health Insights** (US-10 a US-13): HRV trend ✅, recovery score ✅, correlação sono/performance ⏳, alerta overreaching ✅
- **Módulo 4 — AI Coach** (US-14 a US-18): chat livre ⏳, insight pós-atividade ✅, periodização semanal ✅, nutrição ✅, risco de lesão ✅

---

## Convenções de código

- **Imports:** `from __future__ import annotations` em todo arquivo Python
- **Tipagem:** type hints obrigatórios em todas as funções públicas
- **Docstrings:** estilo Google, em português
- **Testes:** pytest + pytest-asyncio; fixtures em `tests/fixtures/`
- **Linting:** ruff com `line-length = 88`, `target-version = "py311"`
- **Sem mocks do banco:** testes de integração usam DuckDB real (in-memory) — não mockar a camada de storage

---

## Padrão de implementação de uma nova rota

1. Criar o endpoint em `src/api/routers/<módulo>.py` com FastAPI router
2. Registrar o router em `src/api/main.py`
3. Usar `CatalogStore` via dependency injection (`get_db`) — nunca abrir conexão direta
4. Computar métricas via funções de `src/analytics/` ou `src/health/` — nunca inline na rota
5. Escrever teste em `tests/unit/test_api.py` antes de considerar concluído

---

## Contexto importante

- **CatalogStore autoritativo:** `src/storage/catalog_store.py` — nunca usar o duplicado em `src/ingestion/catalog_store.py` (artefato de fase anterior; mantido por compatibilidade com testes de ingestão)
- **Airflow 3.x:** usar `schedule=` (não `schedule_interval=`) e `airflow.providers.standard.operators.python.PythonOperator`
- **MLflow FutureWarning:** backend `FileStore` foi depreciado em fev/2026 — não afeta funcionamento, mas migrar para SQLite em produção
- Arquivos `.fit` e `.gpx` ficam em `data/fit/` e `data/gpx/`
- O banco `velodna.duckdb` fica em `data/` — nunca commitado
- **RouteMap:** usa `GET /activities/{id}/streams?every_n=6` — streams decimados para performance no mapa
- **ZoneChart:** usa `GET /activities/{id}/zones` — FTP buscado de `athlete_metrics` (mais recente com `ftp_w IS NOT NULL`)
