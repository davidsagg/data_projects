#!/bin/bash
set -e

echo "==> Baixando modelo spaCy pt_core_news_sm..."
python -m spacy download pt_core_news_sm -q

echo "==> Trend Radar devcontainer pronto."
echo "    Python:  $(python --version)"
echo "    DuckDB:  $(python -c 'import duckdb; print(duckdb.__version__)')"
