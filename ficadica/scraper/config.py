import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("FAD_EMAIL", "")
PASSWORD = os.getenv("FAD_PASSWORD", "")
BASE_URL = os.getenv("FAD_BASE_URL", "https://www.ficaadicapremium.com.br")
APP_URL = os.getenv("FAD_APP_URL", "https://www.ficaadicapremium.com.br/app")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./data")

def validate():
    if not EMAIL or EMAIL == "seu_email@exemplo.com":
        raise ValueError("FAD_EMAIL não configurado no .env")
    if not PASSWORD or PASSWORD == "sua_senha_aqui":
        raise ValueError("FAD_PASSWORD não configurado no .env")

def ensure_dirs():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_DIR, "raw").mkdir(parents=True, exist_ok=True)

ensure_dirs()
