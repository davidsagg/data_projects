# src/api/main.py — FastAPI Trend Radar API

import logging
import math
from datetime import datetime, timezone
from typing import Any

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .cache import cache
from .repository import TrendRepository
from src.db.connection import get_optimized_connection
from src.utils.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Trend Radar Musical BR",
    description="""
API de inteligência de tendências do mercado musical brasileiro.

Dados coletados semanalmente de **Last.fm**, **YouTube** e **Deezer**.
Pipeline processado com **dbt + DuckDB**. Score calculado por modelo
estatístico com janela de 4 semanas.

## Endpoints

- **`/api/v1/trending`** — ranking semanal de artistas em ascensão, com cache e paginação
- **`/api/v1/artists/{mbid}/history`** — histórico de trend_score de um artista (até 52 semanas)
- **`/health`** — status da API e conectividade com DuckDB

## Cabeçalhos de resposta

- `X-Cache: HIT` — resposta servida do cache em memória (TTL 1h)
- `X-Cache: MISS` — resposta calculada em tempo real e armazenada no cache
    """,
    version="1.0.0",
    contact={"name": "Dave", "email": "trend-radar@portfolio.dev"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "Tendências", "description": "Ranking e histórico de artistas em ascensão."},
        {"name": "Sistema",    "description": "Health check e status da infraestrutura."},
    ],
)


# ---------------------------------------------------------------------------
# Modelos Pydantic — documentação e validação
# ---------------------------------------------------------------------------

class ArtistTrend(BaseModel):
    artist_mbid: str = Field(examples=["f59c5520-5f46-4d2c-b2c4-822eabf53419"])
    artist_name: str = Field(examples=["Emicida"])
    genre:       str | None = Field(default=None, examples=["hip-hop"])
    country:     str | None = Field(default=None, examples=["BR"])
    trend_score: float | None = Field(default=None, examples=[78.5], ge=0, le=100)
    trending_direction: str | None = Field(default=None, examples=["up"])
    week_start:  str | None = Field(default=None, examples=["2026-04-14"])


class TrendingResponse(BaseModel):
    results:       list[ArtistTrend]
    total_results: int  = Field(examples=[20])
    week_start:    str | None = Field(default=None, examples=["2026-04-14"])
    current_page:  int  = Field(examples=[1])
    total_pages:   int  = Field(examples=[3])
    has_next:      bool = Field(examples=[True])
    generated_at:  str  = Field(examples=["2026-04-14T06:00:00+00:00"])


class WeekHistoryItem(BaseModel):
    week_start:    str   = Field(examples=["2026-04-14"])
    trend_score:   float | None = Field(default=None, examples=[78.5])
    score_lastfm:  float | None = Field(default=None, examples=[31.4])
    score_youtube: float | None = Field(default=None, examples=[27.5])
    score_deezer:  float | None = Field(default=None, examples=[19.6])


class ArtistHistoryResponse(BaseModel):
    artist_mbid:        str  = Field(examples=["f59c5520-5f46-4d2c-b2c4-822eabf53419"])
    artist_name:        str  = Field(examples=["Emicida"])
    history:            list[WeekHistoryItem]
    forecast_available: bool = Field(examples=[True])


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    duckdb: str = Field(examples=["ok"])


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_db() -> duckdb.DuckDBPyConnection:
    conn = get_optimized_connection("/workspace/data/trend_radar.duckdb", read_only=True)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Verifica conectividade com DuckDB e retorna status da API.",
    tags=["Sistema"],
)
def health(conn: duckdb.DuckDBPyConnection = Depends(get_db)) -> HealthResponse:
    conn.execute("SELECT 1")
    return HealthResponse(status="ok", duckdb="ok")


@app.get(
    "/api/v1/trending",
    response_model=TrendingResponse,
    summary="Ranking semanal de artistas em ascensão",
    description="""
Retorna os artistas com maior **trend_score** da semana mais recente.

O trend_score é calculado como a média ponderada do crescimento relativo
nas três plataformas (Last.fm 40%, YouTube 35%, Deezer 25%), normalizado
entre 0 e 100. Apenas artistas com score > 65 por 2+ semanas aparecem.

Respostas são cacheadas por 1 hora. O header `X-Cache` indica a origem.
    """,
    tags=["Tendências"],
    responses={
        200: {"description": "Lista paginada de artistas em ascensão."},
        404: {"description": "Nenhum artista encontrado para os filtros informados."},
    },
)
def get_trending(
    genre: str | None = Query(
        default=None,
        description="Filtro por gênero musical (ex: `mpb`, `funk`, `samba`).",
        examples={"mpb": {"value": "mpb"}, "funk": {"value": "funk"}},
    ),
    country: str | None = Query(
        default=None,
        description="Filtro por país (ISO 3166-1 alpha-2). Ex: `BR`.",
        examples={"brasil": {"value": "BR"}},
    ),
    limit: int = Query(
        default=20, ge=1, le=100,
        description="Número de artistas por página (1–100).",
    ),
    page: int = Query(
        default=1, ge=1,
        description="Número da página (começa em 1).",
    ),
    week: str | None = Query(
        default=None,
        description="Filtro por semana específica no formato `YYYY-MM-DD`.",
        examples={"semana": {"value": "2026-04-14"}},
    ),
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> JSONResponse:
    cache_key = f"trending:{genre}:{country}:{limit}:{page}:{week}"
    cached, is_hit = cache.get(cache_key)

    if is_hit:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})

    offset = (page - 1) * limit
    repo = TrendRepository(conn)
    results, total_count = repo.get_trending(
        genre=genre, country=country, limit=limit, week=week, offset=offset
    )

    if not results:
        raise HTTPException(
            status_code=404,
            detail="Nenhum artista encontrado para os filtros informados.",
        )

    for r in results:
        if r.get("week_start") is not None:
            r["week_start"] = str(r["week_start"])

    total_pages = max(1, math.ceil(total_count / limit))
    week_start = results[0]["week_start"] if results else None

    data: dict[str, Any] = {
        "results":       results,
        "total_results": total_count,
        "week_start":    week_start,
        "current_page":  page,
        "total_pages":   total_pages,
        "has_next":      page < total_pages,
        "generated_at":  datetime.now(tz=timezone.utc).isoformat(),
    }

    cache.set(cache_key, data, ttl=3600)
    return JSONResponse(content=data, headers={"X-Cache": "MISS"})


@app.get(
    "/api/v1/artists/{mbid}/history",
    response_model=ArtistHistoryResponse,
    summary="Histórico de trend_score de um artista",
    description="""
Retorna o histórico semanal de **trend_score** e scores por plataforma
(Last.fm, YouTube, Deezer) do artista identificado pelo MusicBrainz ID.

O campo `forecast_available` indica se há dados suficientes (≥ 12 semanas)
para geração de previsão com Prophet.
    """,
    tags=["Tendências"],
    responses={
        200: {"description": "Histórico do artista com scores por plataforma."},
        404: {"description": "Artista não encontrado na base de dados."},
    },
)
def get_history(
    mbid: str,
    weeks: int = Query(
        default=12, ge=1, le=52,
        description="Número de semanas de histórico a retornar (1–52).",
    ),
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> ArtistHistoryResponse:
    repo = TrendRepository(conn)
    result = repo.get_artist_history(mbid=mbid, weeks=weeks)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Artista '{mbid}' não encontrado.",
        )

    for item in result.get("history", []):
        if item.get("week_start") is not None:
            item["week_start"] = str(item["week_start"])

    return ArtistHistoryResponse(**result)
