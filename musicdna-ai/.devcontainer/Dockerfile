FROM python:3.11-slim

# Instalar dependencias do sistema
RUN apt-get update && apt-get install -y \
    git curl wget build-essential \
    libsndfile1 libsndfile1-dev \
    ffmpeg \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Instalar Claude Code CLI dentro do container
RUN npm install -g @anthropic-ai/claude-code

# Criar usuario nao-root (seguranca)
RUN useradd -m -s /bin/bash developer
RUN mkdir -p /workspace && chown developer:developer /workspace

# Instalar dependencias Python base
RUN pip install --upgrade pip
RUN pip install \
    librosa==0.10.1 \
    numpy pandas scikit-learn \
    torch torchvision \
    chromadb \
    fastapi uvicorn \
    duckdb \
    mlflow \
    streamlit \
    jupyter ipykernel \
    pytest black pylint

WORKDIR /workspace
USER developer

CMD ["/bin/bash"]
