SHELL := /bin/bash

.PHONY: setup dev start build test test-cov lint clean docker-up docker-down help

# Usa o python do sistema (container) — .venv tem shebangs de macOS
PYTHON  := python3
PYTEST  := $(PYTHON) -m pytest
UVICORN := $(PYTHON) -m uvicorn
ALEMBIC := $(PYTHON) -m alembic

setup: ## Primeira execução — instala tudo
	@echo 'BandKit — Setup inicial...'
	rm -rf backend/.venv
	cd backend && $(PYTHON) -m venv .venv
	cd backend && .venv/bin/pip install -r requirements.txt -q
	cd backend && $(ALEMBIC) upgrade head
	cd frontend && npm install --silent
	mkdir -p bandkit-data/songs
	@echo 'Setup completo. Execute: make dev'

FRONTEND_PORT ?= 5174
API_PORT      ?= 8000

dev: ## Hot reload — backend + frontend em paralelo (FRONTEND_PORT=5174 API_PORT=8000)
	(cd backend && $(UVICORN) main:app --reload --host 0.0.0.0 --port $(API_PORT) &)
	(cd frontend && npm run dev -- --host 0.0.0.0 --port $(FRONTEND_PORT) &)
	@echo 'API: http://localhost:$(API_PORT)/docs'
	@echo 'App: http://localhost:$(FRONTEND_PORT)'

start: build ## Build + serve (demo sem hot reload)
	(cd backend && $(UVICORN) main:app --port 8000 &)
	(cd frontend && npm run preview -- --port 5173 &)
	@echo 'App: http://localhost:5173'

build: ## Build do frontend para produção
	cd frontend && npm run build

test: ## Roda todos os testes
	cd backend && $(PYTEST) --cov=src -v
	cd frontend && npm run test

test-cov: ## Testes com relatório HTML
	cd backend && $(PYTEST) --cov=src --cov-report=html
	@echo 'Relatório: backend/htmlcov/index.html'

lint: ## Verifica estilo de código
	cd backend && $(PYTHON) -m ruff check src/ || true
	cd frontend && npx eslint src/ --ext .ts,.tsx || true

clean: ## Remove dados de dev
	rm -f bandkit-data/bandkit.db
	@echo 'Dados removidos. Execute: make setup'

docker-up: ## Sobe com Docker Compose
	cp -n .env.example .env 2>/dev/null || true
	docker compose up --build -d
	@echo 'App: http://localhost:5173'

docker-down: ## Para os containers
	docker compose down

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | \
	  awk 'BEGIN {FS=":.*?## "};{printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'
