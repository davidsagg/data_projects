# RAG Finance Chat

Sistema de chat com **RAG** (Retrieval Augmented Generation) sobre documentos de finanças,
usando **Mistral 7B** local (via Ollama), **Chroma** como vector store e **PostgreSQL** no backend.
100% local — nada é enviado para serviços externos.

> **Nota (reprodutibilidade):** a pasta `data/` (seus documentos + o índice Chroma) **não vem no
> repositório** — é grande e específica de cada usuário. Para usar: coloque seus arquivos em
> `data/documents/` e rode `python reindex_rag.py` para (re)construir o índice.

## Pré-requisitos

- **Python 3.11** e **Node 20+**
- **Ollama** com o modelo Mistral: `ollama pull mistral` (e o servidor rodando: `ollama serve`)
- **PostgreSQL** acessível (padrão do backend: `127.0.0.1:5433` — ajuste via `.env`)

## Setup

No monorepo, o `setup_local.sh` já cria o venv e instala as dependências. Manualmente:

```bash
# a partir de saggirag/
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # se existir; ajuste OLLAMA_BASE_URL, credenciais do Postgres, etc.
```

## Rodar

**Backend (FastAPI, porta 8000):**
```bash
source .venv/bin/activate
uvicorn backend.main:app --host localhost --port 8000 --reload
```

**Frontend (React + Vite):**
```bash
cd frontend
npm install
npm run dev
```

## Adicionar documentos

1. Coloque arquivos `.txt` ou `.pdf` em `data/documents/`
2. Rode `python reindex_rag.py` para reindexar
3. Reinicie o backend

`convert_pdfs.py` ajuda a preparar/converter PDFs antes da indexação.

## Estrutura

```
saggirag/
├── backend/          # FastAPI (main.py) — RAG + endpoints de chat
├── frontend/         # React + Vite
├── convert_pdfs.py   # utilitário de preparação de PDFs
├── reindex_rag.py    # (re)constrói o índice Chroma a partir de data/documents/
├── data/             # documentos + chroma_db (NÃO versionado)
├── .env              # configurações (não versionado)
└── requirements.txt
```

## Stack

Python 3.11 · FastAPI · LangChain (community / ollama / text-splitters) · Chroma · Ollama (Mistral 7B) · PostgreSQL · React + Vite
