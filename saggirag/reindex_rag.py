#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
import chromadb
from langchain_ollama import OllamaEmbeddings

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "./data/documents")

CATEGORIES = {
    "financas": "Finanças e Investimentos",
    "data_science": "Análise de Dados e Machine Learning",
    "software_engineering": "Engenharia e Arquitetura de Software"
}

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

def process_category(category, category_name):
    """Processa uma categoria específica de documentos"""
    print_info(f"Processando categoria: {category_name}")
    
    category_path = Path(DOCUMENTS_PATH) / category
    if not category_path.exists():
        print_error(f"Pasta não encontrada: {category_path}")
        return False
    
    # Procurar TXT e PDF
    txt_files = list(category_path.glob("*.txt"))
    pdf_files = list(category_path.glob("*.pdf"))
    all_files = txt_files + pdf_files
    
    if not all_files:
        print_error(f"Nenhum arquivo em {category}")
        return False
    
    print_success(f"{len(all_files)} arquivo(s) em {category}")
    
    try:
        print_info("Carregando documentos...")
        documents = []
        
        if txt_files:
            txt_loader = DirectoryLoader(str(category_path), glob="*.txt", loader_cls=TextLoader)
            documents.extend(txt_loader.load())
        
        if pdf_files:
            pdf_loader = DirectoryLoader(str(category_path), glob="*.pdf", loader_cls=PyPDFLoader)
            documents.extend(pdf_loader.load())
        
        print_success(f"{len(documents)} documento(s) carregado(s)")
        
        print_info("Dividindo em chunks...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)
        print_success(f"{len(chunks)} chunk(s) criado(s)")
        
        print_info("Criando embeddings...")
        embeddings = OllamaEmbeddings(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL)
        
        # Criar ChromaDB
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection_name = f"documents_{category}"
        collection = client.get_or_create_collection(name=collection_name)
        
        # Adicionar documentos
        for i, chunk in enumerate(chunks):
            embedding = embeddings.embed_query(chunk.page_content)
            collection.add(
                ids=[f"{category}_doc_{i}"],
                embeddings=[embedding],
                documents=[chunk.page_content],
                metadatas=[{"source": chunk.metadata.get("source", "unknown"), "category": category}]
            )
        
        print_success(f"Coleção '{collection_name}' criada com {len(chunks)} chunks")
        return True
        
    except Exception as e:
        print_error(f"Erro ao processar {category}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print_header("REINDEXADOR MULTI-CATEGORIA - SAGGIRAG")
    
    docs_path = Path(DOCUMENTS_PATH)
    if not docs_path.exists():
        print_error(f"Diretório não encontrado: {DOCUMENTS_PATH}")
        print_info("Criando estrutura de pastas...")
        for category in CATEGORIES.keys():
            (docs_path / category).mkdir(parents=True, exist_ok=True)
        print_success("Estrutura criada. Coloque seus documentos nas pastas:")
        for cat, name in CATEGORIES.items():
            print(f"  • {DOCUMENTS_PATH}/{cat}/ - {name}")
        return False
    
    print_info("Deletando ChromaDB antigo...")
    chroma_path = Path(CHROMA_DB_PATH)
    if chroma_path.exists():
        try:
            shutil.rmtree(chroma_path)
            print_success("ChromaDB deletado")
        except Exception as e:
            print_error(f"Erro: {str(e)}")
            return False
    
    print_info("Testando conexão com Ollama...")
    try:
        embeddings = OllamaEmbeddings(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL)
        embeddings.embed_query("teste")
        print_success("Ollama conectado")
    except Exception as e:
        print_error(f"Erro ao conectar com Ollama: {str(e)}")
        return False
    
    # Processar cada categoria
    results = {}
    for category, name in CATEGORIES.items():
        print_header(f"CATEGORIA: {name}")
        results[category] = process_category(category, name)
    
    # Resumo final
    print_header("REINDEXAÇÃO CONCLUÍDA")
    for category, name in CATEGORIES.items():
        status = "✓" if results[category] else "✗"
        print(f"{status} {name}")
    
    print_info("Próximo passo: Reinicie o backend")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
