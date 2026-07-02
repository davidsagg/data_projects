# RAG Finance Chat

Sistema de Chat com RAG (Retrieval Augmented Generation) usando Mistral 7B.

## Setup

### 1. Instalar dependências

\`\`\`bash
cd ~/rag-finance-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
\`\`\`

### 2. Instalar Ollama

- Download: https://ollama.ai
- Pull model: `ollama pull mistral`
- Rodar: `ollama serve`

### 3. Rodar Backend

\`\`\`bash
cd ~/rag-finance-app
source venv/bin/activate
uvicorn backend.main:app --host localhost --port 8000 --reload
\`\`\`

### 4. Rodar Frontend

\`\`\`bash
cd ~/rag-finance-app/frontend
npm install
npm start
\`\`\`

## Scripts Úteis

### Reindexar Documentos

\`\`\`bash
python3 reindex_rag.py
\`\`\`

### Converter Excel para Markdown

\`\`\`bash
python3 excel_to_markdown.py seu_arquivo.xlsx
\`\`\`

## Adicionar Documentos

1. Coloque arquivos .txt, .pdf, .docx em `data/documents/`
2. Execute `python3 reindex_rag.py`
3. Reinicie o backend

## Estrutura

\`\`\`
rag-finance-app/
├── backend/          # FastAPI backend
├── frontend/         # React frontend
├── data/
│   ├── documents/    # Seus documentos
│   └── chroma_db/    # Vector store
├── .env              # Configurações
└── requirements.txt  # Dependências Python
\`\`\`
