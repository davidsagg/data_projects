SHELL := /bin/bash

.PHONY: setup dev build test lint clean help

PYTHON  := backend/.venv/bin/python
PYTEST  := $(PYTHON) -m pytest
UVICORN := $(PYTHON) -m uvicorn
ALEMBIC := $(PYTHON) -m alembic

API_PORT      ?= 8007
FRONTEND_PORT ?= 5177

setup: ## Primeira execução — instala tudo e cria o banco
	@echo 'SaggiCRM — Setup inicial...'
	cd backend && python3 -m venv .venv
	cd backend && .venv/bin/pip install -r requirements.txt -q
	cd backend && SAGGICRM_DATA=../data .venv/bin/python -m alembic upgrade head
	cd frontend && npm install --silent
	mkdir -p data
	@echo 'Setup completo. Importe seus contatos em Importar, ou rode: make dev'

dev: ## Hot reload — backend + frontend em paralelo
	(cd backend && SAGGICRM_DATA=../data $(UVICORN) main:app --reload --host 0.0.0.0 --port $(API_PORT) &)
	(cd frontend && npm run dev -- --host 0.0.0.0 --port $(FRONTEND_PORT) &)
	@echo 'API: http://localhost:$(API_PORT)/docs'
	@echo 'App: http://localhost:$(FRONTEND_PORT)'

build: ## Build do frontend para produção
	cd frontend && npm run build

test: ## Roda os testes do backend
	cd backend && SAGGICRM_DATA=../data $(PYTEST) -v

lint: ## Verifica tipos do frontend
	cd frontend && npx tsc -b

clean: ## Remove o banco local (mantém o export do LinkedIn)
	rm -f data/saggicrm.db
	@echo 'Banco removido. Execute: make setup'

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | \
	  awk 'BEGIN {FS=":.*?## "};{printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'
