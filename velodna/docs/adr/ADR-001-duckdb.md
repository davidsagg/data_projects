# ADR-001 — DuckDB como banco de dados analítico

**Status:** Aceito  
**Data:** 2026-04-26  
**Decisores:** Time VeloDNA

---

## Contexto

VeloDNA é uma plataforma local de performance ciclística. O volume de dados cresce linearmente com o uso: uma atividade de 3 horas gera ~10 800 linhas em `activity_streams`. Um atleta ativo com 300 atividades/ano acumula ~3,2 M de linhas de streams. As queries dominantes são analíticas: agregações por período, cálculos de médias móveis (CTL/ATL), distribuições de zonas, correlações entre métricas.

Alternativas consideradas:
1. **SQLite** — zero infra, mas sem suporte real a OLAP, sem tipos DOUBLE/FLOAT nativos eficientes, sem funções de janela completas.
2. **PostgreSQL** — robusto, mas requer servidor separado, contradiz o requisito de stack 100% local sem Docker compose adicional.
3. **TimescaleDB** — excelente para time-series, mas extensão PostgreSQL → mesma dependência de infra.
4. **DuckDB** — OLAP embarcado, zero infra, arquivo único, Python-native, suporte completo a SQL analítico.

---

## Decisão

Usar **DuckDB** como único banco de dados do VeloDNA.

---

## Consequências

**Positivas:**
- Zero infraestrutura: banco é um único arquivo `velodna.db` no diretório de dados.
- Performance analítica: queries com `GROUP BY`, `WINDOW FUNCTIONS`, `MEDIAN`, `PERCENTILE_CONT` rodam em memória colunar — 10–100× mais rápido que SQLite para este workload.
- Integração nativa com pandas/numpy: `duckdb.query().df()` sem serialização.
- dbt-duckdb disponível para transformações SQL versionadas.
- Backup trivial: `cp velodna.db velodna.db.bak`.

**Negativas / Riscos:**
- Sem suporte a writes concorrentes de múltiplos processos (single-writer). Mitigação: API FastAPI garante acesso serializado; DAGs Airflow usam conexão única por task.
- Não adequado para uso em produção multi-tenant (fora do escopo).
- Sem replicação nativa. Mitigação: backup diário via DAG para `data/exports/`.
