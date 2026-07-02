#!/usr/bin/env python3
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
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_ollama import OllamaEmbeddings, OllamaLLM
import chromadb

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "./data/documents")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/chat_history.db")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SAGGIRAG - Data & ML Assistant", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class QueryRequest(BaseModel):
    query: str
    category: str = "data_science"

class QueryResponse(BaseModel):
    query: str
    response: str
    category: str
    timestamp: str

class HistoryResponse(BaseModel):
    total: int
    history: list

# System prompts para cada categoria
SYSTEM_PROMPTS = {
    "financas": """Você é especialista em Finanças Pessoais, Investimentos e Análise Financeira.

Ajude o usuário com:
- Estratégias de investimento e alocação de portfólio
- Análise fundamental e técnica
- Planejamento financeiro e aposentadoria
- Instrumentos financeiros (ações, fundos, renda fixa, criptomoedas)
- Gestão de riscos financeiros
- Impostos e deduções fiscais

Baseie-se nos documentos fornecidos. Se a pergunta estiver fora do escopo de finanças, redirecione ou indique que não é seu domínio.""",

    "data_science": """Você é especialista em Ciência de Dados, Machine Learning, Estatística e Análise de Dados.

Ajude o usuário com:
- Técnicas de exploração e visualização de dados (EDA)
- Preparação, limpeza e engenharia de features
- Seleção de algoritmos ML apropriados ao caso de uso
- Validação, avaliação e interpretação de modelos
- Metodologias estatísticas e testes de hipóteses
- Boas práticas em ML (overfitting, underfitting, regularização)
- Ferramentas e bibliotecas (pandas, scikit-learn, TensorFlow, etc)
- Programação em Python e SQL para Ciência de Dados e Machine Learning

Sempre considere o contexto do problema. Baseie-se nos documentos fornecidos.""",

    "Engenharia de Software": """Você é especialista em Engenharia de Software, Arquitetura de Software e Engenharia de Código.

Ajude o usuário com:
- Design patterns e arquitetura de software
- Boas práticas de codificação e clean code
- Otimização de performance e escalabilidade
- Testes e debugging
- Versionamento e CI/CD
- Paradigmas de programação (OOP, funcional, etc)
- Linguagens específicas e frameworks
- Segurança e criptografia

Baseie-se nos documentos fornecidos e forneça exemplos práticos quando possível."""
}

db_connection = None
chroma_client = None
retrievers = {}

def init_sqlite():
    global db_connection
    Path(SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db_connection = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    cursor = db_connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            response TEXT NOT NULL,
            category TEXT DEFAULT 'data_science',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db_connection.commit()

def save_to_sqlite(query: str, response: str, category: str):
    if db_connection:
        cursor = db_connection.cursor()
        cursor.execute("INSERT INTO chat_history (query, response, category) VALUES (?, ?, ?)", 
                      (query, response, category))
        db_connection.commit()

def get_history_from_sqlite(limit: int = 10, category: str = None):
    if not db_connection:
        return []
    cursor = db_connection.cursor()
    if category:
        cursor.execute("""SELECT id, query, response, category, created_at FROM chat_history 
                         WHERE category = ? ORDER BY created_at DESC LIMIT ?""", (category, limit))
    else:
        cursor.execute("""SELECT id, query, response, category, created_at FROM chat_history 
                         ORDER BY created_at DESC LIMIT ?""", (limit,))
    rows = cursor.fetchall()
    history = [{"id": row[0], "query": row[1], "response": row[2], "category": row[3], "created_at": row[4]} for row in rows]
    history.reverse()
    return history

def init_rag():
    global chroma_client, retrievers
    
    docs_path = Path(DOCUMENTS_PATH)
    if not docs_path.exists():
        docs_path.mkdir(parents=True, exist_ok=True)
    
    try:
        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        
        # Inicializar coleções para cada categoria
        for category in SYSTEM_PROMPTS.keys():
            category_path = docs_path / category
            if category_path.exists():
                logger.info(f"[RAG] Inicializando categoria: {category}")
                collection_name = f"documents_{category}"
                chroma_client.get_or_create_collection(name=collection_name)
        
        logger.info("[RAG] ✓ ChromaDB pronto")
        return True
    except Exception as e:
        logger.error(f"[RAG] ✗ Erro: {str(e)}")
        return False

@app.on_event("startup")
async def startup():
    logger.info("\n" + "="*70 + "\nINICIANDO SAGGIRAG\n" + "="*70 + "\n")
    init_rag()
    init_sqlite()
    logger.info("✓ Pronto\n")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "rag": chroma_client is not None,
        "db": db_connection is not None,
        "categories": list(SYSTEM_PROMPTS.keys()),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not chroma_client:
        raise HTTPException(status_code=503, detail="RAG não inicializado")
    
    category = request.category if request.category in SYSTEM_PROMPTS else "data_science"
    
    try:
        logger.info(f"[QUERY] {request.query} (Categoria: {category})")
        
        # Buscar contexto na coleção apropriada
        collection_name = f"documents_{category}"
        try:
            collection = chroma_client.get_collection(name=collection_name)
            # Buscar documentos similares
            embeddings = OllamaEmbeddings(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL)
            query_embedding = embeddings.embed_query(request.query)
            results = collection.query(query_embeddings=[query_embedding], n_results=3)
            context = "\n".join(results["documents"][0]) if results["documents"] else "Sem contexto disponível"
        except Exception as e:
            logger.warning(f"Erro ao buscar contexto: {str(e)}")
            context = "Sem contexto disponível"
        
        # Preparar prompt com sistema específico
        system_prompt = SYSTEM_PROMPTS[category]
        prompt = f"""{system_prompt}

DOCUMENTOS RELEVANTES:
{context}

PERGUNTA: {request.query}

RESPOSTA:"""
        
        logger.info(f"[QUERY] Processando com {OLLAMA_MODEL}...")
        llm = OllamaLLM(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL, temperature=0.7)
        response_text = llm.invoke(prompt)
        
        save_to_sqlite(request.query, response_text, category)
        logger.info("[QUERY] ✓ Sucesso\n")
        
        return QueryResponse(
            query=request.query,
            response=response_text,
            category=category,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"[QUERY] ✗ Erro: {str(e)}\n")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
async def get_history(limit: int = 10, category: str = None):
    history = get_history_from_sqlite(limit=limit, category=category)
    return HistoryResponse(total=len(history), history=history)

@app.get("/categories")
async def list_categories():
    return {"categories": list(SYSTEM_PROMPTS.keys())}

@app.get("/")
async def root():
    return {
        "app": "SAGGIRAG",
        "version": "1.0.0",
        "categories": list(SYSTEM_PROMPTS.keys())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000, reload=True)
