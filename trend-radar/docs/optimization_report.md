# Relatório de Otimização — Trend Radar Musical BR

Gerado em: 2026-04-23 10:49

## Performance — Antes vs Depois

| Métrica | Antes | Depois | Ganho |
|---------|------:|-------:|------:|
| gold_trend_scores (ms) | 18.5 | 0.4 | -97.8% |
| rising_artists JOIN (ms) | 22.7 | 0.6 | -97.4% |
| GenreHeatmap.compute() (ms) | 8.3 | 0.2 | -97.6% |
| AnomalyDetector.run() (ms) | 1180.4 | 239.9 | -79.7% |
| Tamanho DuckDB (MB) | 0.8 | 0.8 | -0.0% |

## Otimizações Aplicadas

- **DuckDB PRAGMAs**: `threads=8`, `memory_limit=8GB` via `get_optimized_connection()`
- **LIMIT 500** em `gold_rising_artists.sql` — evita scan completo na API
- **ORDER BY corrigido** em `gold_trend_scores` → `week_start DESC, artist_mbid`
- **Cache em memória** (TTL 1h) no endpoint `/api/v1/trending`
- **Paginação** com `OFFSET` no repositório — reduz payload por request

## Cobertura de Testes

- Total de testes: 43
- Status: todos GREEN ✅

## Qualidade de Dado

- Great Expectations: `bronze_lastfm` ✅ | `bronze_youtube` ✅
- dbt source freshness: dentro do prazo ✅
- dbt test: todos passando ✅

## Observabilidade

- Logging estruturado JSON via `setup_logging()` (python-json-logger 4.x)
- `ingestion_completed` emitido com `duration_ms`, `records_inserted`, `circuit_state`
- Circuit breakers: LastFM/Deezer (`fail_max=5`), YouTube (`fail_max=3`)
- Health check: `scripts/check_health.py` → `healthy | degraded | critical`
