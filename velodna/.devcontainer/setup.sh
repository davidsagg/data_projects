# .devcontainer/setup.sh
#!/bin/bash
set -e
 
echo "==> Criando ambiente virtual..."
python -m venv /workspace/.venv
 
echo "==> Instalando dependências Python..."
pip install --upgrade pip
pip install \
  fitparse \
  gpxpy \
  stravalib \
  garminconnect \
  duckdb \
  fastapi uvicorn \
  pandas numpy scipy scikit-learn \
  mlflow \
  pytest pytest-asyncio httpx \
  python-dotenv
 
echo "==> Criando estrutura de diretórios..."
mkdir -p src/{ingestion,analytics,routes,health,ai,api}
mkdir -p data/{fit,gpx,exports,processed}
mkdir -p tests/{unit,integration}
mkdir -p dags dbt docs
 
echo "==> Setup completo! VeloDNA pronto para desenvolvimento."

