# MusicDNA AI — Guia para o Claude Code CLI

Sistema de análise de áudio com embeddings, matching de licenciamento e simulação de jam sessions. Desenvolvido em 7 fases com TDD completo.

---

## Ambiente

- **Diretório do projeto:** `musicdna-ai/` (dev local; venv em `.venv`)
- **Python:** 3.11
- **Executar testes (sem integração):** `make test` ou `pytest tests/ -v --tb=short`
- **Executar TODOS os testes (incluindo Ollama):** `make test-all`
- **Cobertura:** `make coverage` (HTML em `htmlcov/index.html`)
- **Linter/formatter:** `black` — `make lint` (check) e `make format` (aplicar)
- **AI local:** Ollama em `http://localhost:11434` (geração de estilos/progressões)
- **MLflow UI:** `make mlflow` → http://localhost:5000
- **API:** `make api` → http://localhost:8000
- **UI Streamlit:** `make ui` → http://localhost:8502
- **Dev (API + UI juntos):** `make dev`

---

## Regras de segurança (obrigatórias)

**Nunca sem confirmação explícita:** `git push`, deletar arquivos ou diretórios, modificar `.env` ou credenciais, instalar dependências de sistema (`apt-get`).

**Nunca:** transmitir dados para serviços externos não listados, acessar `/data/raw` sem instrução.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Áudio | librosa, soundfile, audioread |
| Embeddings | CLAP (transformers), sentence-transformers |
| ML | PyTorch, scikit-learn |
| Vector DB | ChromaDB |
| Storage | DuckDB + pandas |
| API | FastAPI + uvicorn |
| UI | Streamlit |
| MLOps | MLflow (tracking de experimentos) |
| Jam / MIDI | TensorFlow, note-seq, music21 |
| Orquestração | Apache Airflow (DAG: musicdna_pipeline) |
| Transformações | dbt-duckdb (3 modelos marts) |

---

## Estrutura do projeto

```
src/
  api/
    main.py             ← FastAPI app principal
    routers/            ← routers por domínio (jam, matching, etc.)
  audio/
    features.py         ← extração de features (librosa: BPM, chroma, MFCC, etc.)
    ingestion.py        ← ingestão de arquivos de áudio
  matching/
    catalog_store.py    ← DuckDB — catálogo de faixas (DDL + CRUD)
    engine.py           ← engine de matching de licenciamento
    vector_store.py     ← ChromaDB — busca vetorial por similaridade
  pipeline/
    generator.py        ← geração de embeddings CLAP
    playback.py         ← playback e exportação de sessões
    session.py          ← gestão de sessões de jam
    style_engine.py     ← motor de estilos (Ollama + regras)
  simulator/            ← simulador de jam sessions (TensorFlow/note-seq)
  infrastructure/
    mlflow_tracker.py   ← wrapper MLflow para tracking
  jam/                  ← módulo de jam session (geração MIDI + Ollama)
  sync/                 ← sincronização e integração entre subsistemas
  ui/
    app.py              ← Streamlit (3 telas: Matcher, Jam, Dashboard)
tests/                  ← 17 arquivos de teste TDD
docs/                   ← 9 documentos de fase (Fases 1–7 + guias)
models/
  embeddings/           ← modelos de embeddings persistidos
  llm/                  ← modelos LLM locais
dbt/                    ← 3 modelos marts (faixas_por_genero, ultimas_indexacoes, metricas_qualidade)
airflow/                ← DAG musicdna_pipeline (5 tasks)
mlflow/                 ← experimentos MLflow (backend local)
notebooks/              ← Jupyter notebooks exploratórios
```

---

## Fases de desenvolvimento (histórico de implementação)

| Fase | Entregável | Status |
|---|---|---|
| Fase 1 — Arquitetura e User Stories | PRD, DER, User Stories | ✅ |
| Fase 2 — Pipeline de Áudio (TDD) | features.py, ingestion.py, catalog_store (DuckDB) | ✅ |
| Fase 3 — Vector Database (TDD) | ChromaDB vector_store, CLAP embeddings | ✅ |
| Fase 4 — Sync Matcher (TDD) | matching engine, busca por similaridade | ✅ |
| Fase 5 — Jam Simulator (TDD) | TensorFlow/note-seq, MIDI, geração com Ollama | ✅ |
| Fase 6 — API + UI Streamlit (TDD) | FastAPI routers, Streamlit 3 telas | ✅ |
| Fase 7 — MLOps Final | MLflow tracker, Airflow DAG, dbt models, docker-compose | ✅ |

Documentação completa em `docs/` (9 arquivos .docx por fase).

---

## Testes

17 arquivos de teste — marcador `integration` para testes que requerem Ollama:

```bash
pytest tests/ -v                   # roda tudo exceto @integration (padrão)
pytest tests/ -v -m integration    # roda apenas testes de integração (requer Ollama)
```

| Arquivo | Foco |
|---|---|
| `test_features.py` | Extração de features de áudio (librosa) |
| `test_ingestion.py` | Pipeline de ingestão de faixas |
| `test_catalog_store.py` | DuckDB — CRUD de catálogo |
| `test_vector_store.py` | ChromaDB — upsert e busca vetorial |
| `test_matching_engine.py` | Engine de matching de licenciamento |
| `test_pipeline.py` | Pipeline end-to-end |
| `test_generator.py` | Geração de embeddings CLAP |
| `test_session.py` | Gestão de sessões de jam |
| `test_style_engine.py` | Motor de estilos |
| `test_playback.py` | Playback e exportação |
| `test_jam_router.py` | Endpoints /jam/session |
| `test_api.py` | FastAPI — demais endpoints |
| `test_ui_helpers.py` | Helpers de formatação Streamlit |
| `test_mlflow_tracker.py` | MLflow tracking |
| `test_airflow_dag.py` | DAG musicdna_pipeline |
| `test_dbt_models.py` | Modelos dbt marts |
| `test_integration_ollama.py` | Integração real com Ollama (@integration) |

---

## Convenções de código

- **Formatação:** `black` com linha máx. 88 chars — `make format` antes de commitar
- **Linting:** pylint com threshold ≥ 7.0 — checar com `make lint`
- **Tipagem:** type hints obrigatórios em funções públicas
- **Docstrings:** Google style
- **Testes:** marcador `@pytest.mark.integration` para testes que requerem Ollama ou serviços externos
- **MLflow:** sempre logar via `src/infrastructure/mlflow_tracker.py` — não inline em DAGs
- **DuckDB:** sempre via `src/matching/catalog_store.py` — não abrir conexões diretas
- **ChromaDB:** sempre via `src/matching/vector_store.py`

---

## Contexto importante

- Coluna `bpm` no DuckDB foi padronizada — `bpm_manual` foi removida (ver último commit)
- A UI Streamlit roda na porta **8502** (não 8501) para não conflitar com outros projetos
- Subsistema A (Matching) e Subsistema B (Jam Simulator) são independentes mas integrados via API — ver `docs/MusicDNA_AI_Guia_Uso_Subsistema_A.docx`
- O `style_engine.py` usa Ollama — testes que dependem dele devem ser marcados `@pytest.mark.integration`
- Modelos CLAP ficam em `models/embeddings/` — não commitar (podem ser pesados)
- MLflow backend é local em `mlflow/mlruns/` — não commitado