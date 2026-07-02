# 🎵 MusicDNA AI

> **Sync Licensing Matcher + Jam Session Simulator**  
> Build to Learn Portfolio — Dave | 2025

---

## 🧬 O que é

**MusicDNA AI** é uma plataforma de inteligência musical com dois módulos complementares:

| Módulo | Descrição |
|--------|-----------|
| 🔍 **Sync Licensing Matcher** | Analisa o DNA sonoro de uma faixa e conecta com oportunidades de licenciamento em mídia (série, filme, publicidade, games) |
| 🎹 **Jam Session Simulator** | Músico virtual com IA que improvisa em resposta ao que você toca em tempo real (Jazz, MPB) |

---

## 🎯 Objetivo

Projeto de portfólio técnico **Build to Learn** — ciclo completo de desenvolvimento, da ideação ao deploy, aplicando:
- Audio Machine Learning (embeddings, CLAP, librosa)
- Vector Databases (ChromaDB / FAISS)
- Generative AI para música (Magenta, HuggingFace)
- LLMs locais (Ollama / Llama 3)
- Engenharia de dados com pipelines públicos
- Metodologia XP + TDD

---

## 🗂️ Estrutura do Projeto

```
musicdna-ai/
├── docs/               # Project Charter, ADRs, diagramas de arquitetura
├── src/
│   ├── sync/           # Módulo A — Sync Licensing Matcher
│   ├── jam/            # Módulo B — Jam Session Simulator
│   ├── pipeline/       # ETL, ingestão de dados, feature store
│   └── api/            # FastAPI endpoints
├── data/               # Datasets locais, features extraídas
├── tests/              # Test suite completa (TDD)
├── notebooks/          # EDA, experimentos, prototipagem
└── README.md
```

---

## 🛠️ Stack

```
Audio ML       librosa · Essentia · CLAP (HuggingFace)
Generative ML  Magenta · HuggingFace Transformers
Vector DB      ChromaDB · FAISS
LLM local      Ollama · Llama 3 (8B)
API            FastAPI · Pydantic
Pipeline       DuckDB · Airflow · dbt
Experiments    MLflow
Dashboard      Streamlit · Plotly
Infra          Mac M2 24GB · Metal GPU · 100% local
Linguagem      Python 3.11+
```

---

## 🚀 Fases do Projeto

- [x] **Idealização** — Curadoria e seleção do projeto
- [ ] **Fase 1** — Planejamento & Arquitetura
- [ ] **Fase 2** — User Stories
- [ ] **Fase 3** — Casos de Teste
- [ ] **Fase 4** — Desenvolvimento (XP)
- [ ] **Fase 5** — TDD
- [ ] **Fase 6** — Otimização
- [ ] **Fase 7** — Deploy

---

## 📄 Documentação

- [`docs/project_charter.docx`](docs/project_charter.docx) — Project Charter completo
- `docs/adr/` — Architecture Decision Records *(a criar na Fase 1)*
- `docs/architecture/` — Diagramas C4 *(a criar na Fase 1)*

---

> *"The music is not in the notes, but in the silence between."* — Mozart
