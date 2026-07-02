FROM python:3.11-slim

# Metadados
LABEL maintainer='Dave' \
      project='Trend Radar Musical BR' \
      version='1.0.0'

# Dependências de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar dependências Python ANTES do código
# (melhor uso do cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY src/ ./src/
COPY dbt/ ./dbt/
COPY dags/ ./dags/
COPY scripts/ ./scripts/

# Criar diretórios de dados
RUN mkdir -p /app/data/reports /app/data/alerts /app/data/tmp

# Variáveis de ambiente padrão (sobrescritas pelo docker-compose)
ENV PYTHONPATH=/app
ENV OLLAMA_URL=http://host.docker.internal:11434
ENV DUCKDB_PATH=/app/data/trend_radar.duckdb

# Healthcheck da API
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000 8501

# Entrypoint padrão — sobrescrito no docker-compose por serviço
CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
