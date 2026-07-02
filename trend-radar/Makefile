.PHONY: setup build up down logs test lint format \
        dbt-run dbt-test dbt-docs pipeline demo clean help

# ── Setup ──────────────────────────────────────────────
setup:  ## Primeira execução: copia .env e inicializa Airflow
	cp .env.example .env
	@echo 'Edite .env com suas API keys antes de continuar'
	docker compose run --rm airflow-webserver airflow db init
	docker compose run --rm airflow-webserver airflow users create \
	  --username admin --password admin --firstname Admin \
	  --lastname User --role Admin --email admin@trendradar.local

# ── Docker ─────────────────────────────────────────────
build:  ## Build das imagens Docker
	docker compose build

up:     ## Sobe todos os serviços
	docker compose up -d
	@echo 'Dashboard:  http://localhost:8501'
	@echo 'API:        http://localhost:8000/docs'
	@echo 'Airflow:    http://localhost:8080 (admin/admin)'
	@echo 'MLflow:     http://localhost:5001'

down:   ## Para todos os serviços
	docker compose down

logs:   ## Mostra logs de todos os serviços
	docker compose logs -f

# ── Qualidade ───────────────────────────────────────────
test:   ## Roda suite de testes completa
	pytest --cov=src --cov-report=term-missing -v

lint:   ## Verifica estilo de código
	ruff check src/ dags/
	black --check src/ dags/

format: ## Formata código automaticamente
	black src/ dags/
	ruff check --fix src/ dags/

# ── Pipeline ────────────────────────────────────────────
dbt-run:    ## Roda todos os modelos dbt
	dbt run --project-dir dbt/

dbt-test:   ## Roda testes dbt
	dbt test --project-dir dbt/

dbt-docs:   ## Gera e serve docs dbt
	dbt docs generate --project-dir dbt/
	dbt docs serve --project-dir dbt/ --port 8888

pipeline:   ## Roda pipeline completo manualmente
	@echo 'Triggering Airflow DAG: run_dbt_pipeline'
	curl -X POST http://localhost:8080/api/v1/dags/run_dbt_pipeline/dagRuns \
	  -H 'Content-Type: application/json' \
	  -u admin:admin \
	  -d '{"conf": {}}'

# ── Demo ────────────────────────────────────────────────
demo:   ## Roda demo completa: dados sintéticos + pipeline + abre browser
	python scripts/generate_demo_data.py
	make dbt-run dbt-test
	open http://localhost:8501

# ── Limpeza ─────────────────────────────────────────────
clean:  ## Remove dados de desenvolvimento
	rm -f data/trend_radar.duckdb
	rm -rf data/reports/* data/alerts/*
	@echo 'Dados removidos. Execute make demo para recriar.'

help:   ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
