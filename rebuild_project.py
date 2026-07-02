#!/usr/bin/env python3
"""
Reconstrutor do Projeto RAG Finance App
Executa: python3 rebuild_project.sh

Reconstrói:
- Estrutura de pastas
- Backend FastAPI completo
- Frontend React
- Arquivos de configuração
- Documentos de exemplo
"""

import os
import sys
from pathlib import Path
from datetime import datetime

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def print_success(text):
    print(f"✓ {text}")

def print_error(text):
    print(f"✗ {text}")

def print_info(text):
    print(f"ℹ {text}")

def create_directory_structure():
    """Criar estrutura de pastas"""
    print_header("CRIANDO ESTRUTURA DE PASTAS")
    
    base_path = Path.home() / "rag-finance-app"
    
    folders = [
        base_path,
        base_path / "backend",
        base_path / "frontend",
        base_path / "data",
        base_path / "data" / "documents",
        base_path / "data" / "chroma_db",
        base_path / "logs",
        base_path / "wallet",
    ]
    
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        print_success(f"Pasta criada: {folder.name}")
    
    return base_path

def create_env_file(base_path):
    """Criar arquivo .env"""
    print_header("CRIANDO ARQUIVO .ENV")
    
    env_content = """# ===== OLLAMA =====
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# ===== API =====
API_HOST=localhost
API_PORT=8000
API_RELOAD=true

# ===== CHROMA (Vector Store) =====
CHROMA_DB_PATH=./data/chroma_db
DOCUMENTS_PATH=./data/documents

# ===== SQLITE (Histórico local) =====
SQLITE_DB_PATH=./data/chat_history.db

# ===== LOGGING =====
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log

# ===== FRONTEND =====
REACT_APP_API_URL=http://localhost:8000
"""
    
    env_file = base_path / ".env"
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print_success(f"Arquivo criado: .env")
    return env_file

def create_backend_main(base_path):
    """Criar arquivo backend/main.py"""
    print_header("CRIANDO BACKEND")
    
    main_py = """#!/usr/bin/env python3
import os
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, OllamaLLM

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "./data/documents")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/chat_history.db")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Finance API", version="4.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    response: str
    timestamp: str

class HistoryResponse(BaseModel):
    total: int
    history: list

db_connection = None
retriever = None

def init_sqlite():
    global db_connection
    logger.info("[SQLite] Inicializando...")
    Path(SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    try:
        db_connection = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
        cursor = db_connection.cursor()
        cursor.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        \"\"\")
        db_connection.commit()
        logger.info(f"[SQLite] ✓ Inicializado")
        return True
    except Exception as e:
        logger.error(f"[SQLite] ✗ Erro: {str(e)}")
        return False

def save_to_sqlite(query: str, response: str):
    if not db_connection:
        return False
    try:
        cursor = db_connection.cursor()
        cursor.execute("INSERT INTO chat_history (query, response) VALUES (?, ?)", (query, response))
        db_connection.commit()
        return True
    except Exception as e:
        logger.error(f"[SQLite] ✗ Erro: {str(e)}")
        return False

def get_history_from_sqlite(limit: int = 10):
    if not db_connection:
        return []
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT id, query, response, created_at FROM chat_history ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        history = [{"id": row[0], "query": row[1], "response": row[2], "created_at": row[3]} for row in rows]
        history.reverse()
        return history
    except Exception as e:
        logger.error(f"[SQLite] ✗ Erro: {str(e)}")
        return []

def format_history_for_prompt(history):
    if not history:
        return ""
    formatted = "📚 HISTÓRICO:\\n" + "="*60 + "\\n"
    for i, item in enumerate(history, 1):
        formatted += f"\\n{i}. P: {item['query']}\\n   R: {item['response'][:150]}...\\n"
    formatted += "\\n" + "="*60 + "\\n\\n"
    return formatted

def init_rag():
    global retriever
    try:
        logger.info("[RAG] Inicializando...")
        if not Path(CHROMA_DB_PATH).exists():
            logger.info("[RAG] Criando vector store...")
            Path(DOCUMENTS_PATH).mkdir(parents=True, exist_ok=True)
            example_doc = Path(DOCUMENTS_PATH) / "glossario.txt"
            if not example_doc.exists():
                with open(example_doc, "w") as f:
                    f.write(\"\"\"Glossário Financeiro

Juros Simples: Juro calculado apenas sobre o capital inicial.
Exemplo: R$ 1.000 a 10% a.a. por 3 anos = R$ 1.300

Juros Compostos: Juro calculado sobre capital + juros anteriores.
Exemplo: R$ 1.000 a 10% a.a. por 3 anos = R$ 1.331

ROI: Retorno sobre Investimento = (Lucro - Custo) / Custo × 100%

Diversificação: Distribuição de investimentos em diferentes ativos.

TIR: Taxa Interna de Retorno = taxa que iguala fluxos de caixa

VPL: Valor Presente Líquido = soma de fluxos descontados ao presente
\"\"\")
            loader = DirectoryLoader(DOCUMENTS_PATH, glob="**/*.txt", loader_cls=TextLoader)
            documents = loader.load()
            if not documents:
                return False
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
            chunks = text_splitter.split_documents(documents)
            embeddings = OllamaEmbeddings(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL)
            db = Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory=CHROMA_DB_PATH)
        else:
            embeddings = OllamaEmbeddings(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL)
            db = Chroma(persist_directory=CHROMA_DB_PATH, embedding_function=embeddings)
        retriever = db.as_retriever(search_kwargs={"k": 3})
        logger.info("[RAG] ✓ Pronto\\n")
        return True
    except Exception as e:
        logger.error(f"[RAG] ✗ Erro: {str(e)}\\n")
        return False

@app.on_event("startup")
async def startup():
    logger.info("\\n" + "="*70 + "\\nINICIANDO APLICAÇÃO\\n" + "="*70 + "\\n")
    init_rag()
    init_sqlite()
    logger.info("✓ Pronto\\n")

@app.get("/health")
async def health():
    return {"status": "ok", "rag": retriever is not None, "db": db_connection is not None, "timestamp": datetime.now().isoformat()}

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not retriever:
        raise HTTPException(status_code=503, detail="RAG não inicializado")
    try:
        logger.info(f"[QUERY] {request.query}")
        history = get_history_from_sqlite(limit=5)
        history_text = format_history_for_prompt(history)
        try:
            docs = retriever.invoke(request.query)
        except (AttributeError, TypeError):
            try:
                docs = retriever.get_relevant_documents(request.query)
            except AttributeError:
                docs = []
        context = "\\n".join([doc.page_content for doc in docs]) if docs else "Sem contexto"
        logger.info(f"[QUERY] {len(docs)} docs")
        llm = OllamaLLM(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL, temperature=0.7)
        prompt = f\"\"\"Você é especialista em finanças.

{history_text}

CONTEXTO: {context}

PERGUNTA: {request.query}

Responda com base no contexto. Se não souber, diga.

RESPOSTA:\"\"\"
        logger.info("[QUERY] Processando...")
        response_text = llm.invoke(prompt)
        save_to_sqlite(request.query, response_text)
        logger.info("[QUERY] ✓ Sucesso\\n")
        return QueryResponse(query=request.query, response=response_text, timestamp=datetime.now().isoformat())
    except Exception as e:
        logger.error(f"[QUERY] ✗ Erro: {str(e)}\\n")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
async def get_history(limit: int = 10):
    history = get_history_from_sqlite(limit=limit)
    return HistoryResponse(total=len(history), history=history)

@app.get("/")
async def root():
    return {"app": "RAG Finance API", "version": "4.2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000, reload=True)
"""
    
    main_file = base_path / "backend" / "main.py"
    with open(main_file, 'w') as f:
        f.write(main_py)
    
    print_success(f"Arquivo criado: backend/main.py")
    return main_file

def create_requirements(base_path):
    """Criar arquivo requirements.txt"""
    print_header("CRIANDO REQUIREMENTS.TXT")
    
    requirements = """fastapi==0.104.1
uvicorn==0.24.0
python-dotenv==1.0.0
pydantic==2.5.0
sqlalchemy==2.0.23

langchain==0.1.0
langchain-core==0.1.0
langchain-community==0.0.13
langchain-ollama==0.1.0
langchain-chroma==0.1.0

chromadb==0.4.17
pandas==2.1.1
openpyxl==3.11.0
pypdf==3.17.1
python-docx==0.8.11
"""
    
    req_file = base_path / "requirements.txt"
    with open(req_file, 'w') as f:
        f.write(requirements)
    
    print_success(f"Arquivo criado: requirements.txt")
    return req_file

def create_frontend_files(base_path):
    """Criar arquivos de frontend placeholder"""
    print_header("CRIANDO FRONTEND")
    
    frontend_dir = base_path / "frontend"
    
    # package.json
    package_json = """{
  "name": "rag-finance-chat",
  "version": "1.0.0",
  "description": "RAG Finance Chat with React",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "dev": "vite"
  }
}
"""
    
    with open(frontend_dir / "package.json", 'w') as f:
        f.write(package_json)
    
    print_success("Arquivo criado: frontend/package.json")

def create_documentation(base_path):
    """Criar arquivo README"""
    print_header("CRIANDO DOCUMENTAÇÃO")
    
    readme = """# RAG Finance Chat

Sistema de Chat com RAG (Retrieval Augmented Generation) usando Mistral 7B.

## Setup

### 1. Instalar dependências

\\`\\`\\`bash
cd ~/rag-finance-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
\\`\\`\\`

### 2. Instalar Ollama

- Download: https://ollama.ai
- Pull model: `ollama pull mistral`
- Rodar: `ollama serve`

### 3. Rodar Backend

\\`\\`\\`bash
cd ~/rag-finance-app
source venv/bin/activate
uvicorn backend.main:app --host localhost --port 8000 --reload
\\`\\`\\`

### 4. Rodar Frontend

\\`\\`\\`bash
cd ~/rag-finance-app/frontend
npm install
npm start
\\`\\`\\`

## Scripts Úteis

### Reindexar Documentos

\\`\\`\\`bash
python3 reindex_rag.py
\\`\\`\\`

### Converter Excel para Markdown

\\`\\`\\`bash
python3 excel_to_markdown.py seu_arquivo.xlsx
\\`\\`\\`

## Adicionar Documentos

1. Coloque arquivos .txt, .pdf, .docx em `data/documents/`
2. Execute `python3 reindex_rag.py`
3. Reinicie o backend

## Estrutura

\\`\\`\\`
rag-finance-app/
├── backend/          # FastAPI backend
├── frontend/         # React frontend
├── data/
│   ├── documents/    # Seus documentos
│   └── chroma_db/    # Vector store
├── .env              # Configurações
└── requirements.txt  # Dependências Python
\\`\\`\\`
"""
    
    readme_file = base_path / "README.md"
    with open(readme_file, 'w') as f:
        f.write(readme)
    
    print_success("Arquivo criado: README.md")

def create_helper_scripts(base_path):
    """Criar scripts auxiliares"""
    print_header("CRIANDO SCRIPTS AUXILIARES")
    
    # Script para reindexar
    reindex_py = '''#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "./data/documents")

def main():
    docs_path = Path(DOCUMENTS_PATH)
    txt_files = list(docs_path.glob("**/*.txt"))
    
    if not txt_files:
        print("✗ Nenhum documento encontrado")
        return False
    
    print(f"✓ {len(txt_files)} arquivo(s) encontrado(s)")
    
    chroma_path = Path(CHROMA_DB_PATH)
    if chroma_path.exists():
        shutil.rmtree(chroma_path)
        print("✓ ChromaDB deletado")
    
    print("ℹ Reindexando...")
    
    loader = DirectoryLoader(DOCUMENTS_PATH, glob="**/*.txt", loader_cls=TextLoader)
    documents = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = text_splitter.split_documents(documents)
    
    embeddings = OllamaEmbeddings(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL)
    db = Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory=CHROMA_DB_PATH)
    
    print(f"✓ {len(chunks)} chunks indexados")
    print("✓ Reindexação concluída!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
'''
    
    with open(base_path / "reindex_rag.py", 'w') as f:
        f.write(reindex_py)
    
    print_success("Script criado: reindex_rag.py")

def main():
    print_header("RECONSTRUTOR - RAG FINANCE APP")
    
    print_info("Isto vai recrear o projeto do zero")
    print_info("Localização: ~/rag-finance-app")
    
    response = input("\nContinuar? (s/n): ").lower()
    if response != 's':
        print_error("Cancelado")
        return False
    
    try:
        base_path = create_directory_structure()
        create_env_file(base_path)
        create_backend_main(base_path)
        create_requirements(base_path)
        create_frontend_files(base_path)
        create_documentation(base_path)
        create_helper_scripts(base_path)
        
        print_header("RECONSTRUÇÃO CONCLUÍDA")
        print_success("Projeto recriado com sucesso!")
        print_info(f"Localização: {base_path}")
        
        print("\nPróximos passos:")
        print("1. cd ~/rag-finance-app")
        print("2. python3 -m venv venv")
        print("3. source venv/bin/activate")
        print("4. pip install -r requirements.txt")
        print("5. ollama serve (em outro terminal)")
        print("6. uvicorn backend.main:app --host localhost --port 8000 --reload")
        
        return True
        
    except Exception as e:
        print_error(f"Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
