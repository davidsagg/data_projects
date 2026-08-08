SHELL := /bin/bash

.PHONY: setup dev api front test lint fmt dbt mlflow ports clean help

PY   := .venv/bin/python
PIP  := .venv/bin/pip

# A API precisa do DuckDB e sobe a partir de src/ — sem --app-dir o import
# `api.main` não resolve.
DB_PATH       ?= data/velodna.duckdb
API_PORT      ?= 8006
FRONTEND_PORT ?= 5176
#: 5002 por convenção do monorepo. 5000 está ocupada pelo AirPlay Receiver do
#: macOS, então nunca usar aquela aqui.
MLFLOW_PORT   ?= 5002

setup: ## Primeira execução — venv, dependências (com dev) e frontend
	uv venv --python 3.11 .venv
	uv pip install --python $(PY) -e ".[dev]"
	cd frontend && npm install --silent
	@test -f .env || cp .env.example .env 2>/dev/null || true
	@echo '✓ Pronto. "make dev" sobe API e frontend.'

dev: ## Hot reload — API + frontend em paralelo
	(DB_PATH=$(DB_PATH) .venv/bin/uvicorn api.main:app --app-dir src --port $(API_PORT) --reload &)
	(cd frontend && npm run dev -- --port $(FRONTEND_PORT) &)
	@echo 'API: http://localhost:$(API_PORT)/docs'
	@echo 'App: http://localhost:$(FRONTEND_PORT)'

api: ## Só a API
	DB_PATH=$(DB_PATH) .venv/bin/uvicorn api.main:app --app-dir src --port $(API_PORT) --reload

front: ## Só o frontend
	cd frontend && npm run dev -- --port $(FRONTEND_PORT)

test: ## Testes
	DB_PATH=$(DB_PATH) $(PY) -m pytest -q

lint: ## Ruff + mypy no backend, eslint no frontend
	$(PY) -m ruff check src tests
	$(PY) -m mypy src || true
	cd frontend && npm run lint

fmt: ## Formata com ruff
	$(PY) -m ruff format src tests
	$(PY) -m ruff check --fix src tests

dbt: ## Roda os modelos dbt sobre o DuckDB
	cd dbt && ../$(PY) -m dbt.cli.main run

mlflow: ## UI do MLflow (backend SQLite local)
	.venv/bin/mlflow ui \
	  --backend-store-uri sqlite:///mlflow/mlflow.db \
	  --port $(MLFLOW_PORT)
	@echo 'MLflow: http://localhost:$(MLFLOW_PORT)'

ports: ## Mostra as portas deste projeto e se estão livres
	@for p in $(API_PORT) $(FRONTEND_PORT) $(MLFLOW_PORT); do \
	  if lsof -nP -iTCP:$$p -sTCP:LISTEN >/dev/null 2>&1; then \
	    echo "  $$p — EM USO por $$(lsof -nP -iTCP:$$p -sTCP:LISTEN -t | head -1 | xargs ps -o comm= -p)"; \
	  else echo "  $$p — livre"; fi; \
	done

clean: ## Remove caches de build e teste
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache frontend/dist frontend/.vite
	@echo 'Caches removidos. O DuckDB e os dados em data/ ficam intactos.'

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | \
	  awk 'BEGIN {FS=":.*?## "};{printf "\033[36m%-10s\033[0m %s\n", $$1, $$2}'
