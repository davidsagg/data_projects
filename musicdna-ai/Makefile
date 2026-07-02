.PHONY: test coverage lint format clean mlflow test-all coverage-all ui api dev \
        airflow mlflow-ui dbt-run dbt-test compose-up compose-down status

test:
	pytest tests/ -v --tb=short

coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo 'Relatorio HTML em htmlcov/index.html'

lint:
	black --check src/ tests/
	pylint src/ --fail-under=7.0

format:
	black src/ tests/

mlflow:
	mlflow ui --backend-store-uri /workspace/mlflow/mlruns --port 5000 &
	@echo 'MLflow UI em http://localhost:5000'

test-all:
	pytest tests/ -v --tb=short
	cd /workspace/dbt && /home/developer/.local/bin/dbt compile

coverage-all:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo 'Relatorio em htmlcov/index.html'

ui:
	PYTHONPATH=. streamlit run src/ui/app.py --server.port 8502 --server.address 0.0.0.0

api:
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

dev:
	@echo 'Iniciando API em background...'
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
	@echo 'Iniciando Streamlit...'
	PYTHONPATH=. streamlit run src/ui/app.py --server.port 8502 --server.address 0.0.0.0

airflow:
	export AIRFLOW_HOME=/workspace/airflow && export PATH="/home/developer/.local/bin:$$PATH" && airflow standalone

mlflow-ui:
	mlflow ui --host 0.0.0.0 --port 5000 \
	  --backend-store-uri /workspace/mlflow/mlruns &
	@echo 'MLflow UI: http://localhost:5000'

dbt-run:
	cd /workspace/dbt && /home/developer/.local/bin/dbt run

dbt-test:
	cd /workspace/dbt && /home/developer/.local/bin/dbt test

compose-up:
	docker-compose up --build -d
	@echo 'Servicos: API :8000 | UI :8502 | MLflow :5000 | Airflow :8080'

compose-down:
	docker-compose down

status:
	@echo '=== MusicDNA AI - Status ==='
	@curl -s http://localhost:8000/health || echo 'API: offline'
	@curl -s http://localhost:5000/health || echo 'MLflow: offline'
	@echo '==========================='

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	@echo 'Limpeza concluida'
