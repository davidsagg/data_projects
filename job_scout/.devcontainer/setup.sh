#!/bin/bash
set -e

echo "==> Inicializando banco de dados..."
python -c "from database import init_db; init_db()"

echo "==> job-scout devcontainer pronto."
echo "    Python: $(python --version)"
echo "    Para rodar: python main.py"
