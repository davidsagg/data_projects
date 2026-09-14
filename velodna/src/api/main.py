"""
VeloDNA API — FastAPI application entrypoint.
"""
from __future__ import annotations

from fastapi import FastAPI

from api.routers import (
    activities,
    analytics,
    coach_router,
    export_router,
    fitness_router,
    health_router,
    planning_router,
    routes_router,
    segments_router,
    training_router,
)

app = FastAPI(title="VeloDNA API", version="2.0.0")

app.include_router(activities.router, prefix="/activities", tags=["activities"])
app.include_router(analytics.router, tags=["analytics"])
app.include_router(fitness_router.router, tags=["fitness"])
app.include_router(planning_router.router, tags=["planning"])
app.include_router(health_router.router, tags=["health"])
app.include_router(routes_router.router, prefix="/routes", tags=["routes"])
app.include_router(segments_router.router, tags=["segments"])
app.include_router(training_router.router, tags=["training"])
app.include_router(export_router.router, tags=["export"])
app.include_router(coach_router.router, prefix="/coach", tags=["coach"])


@app.get("/health")
def health_check():
    """Endpoint de healthcheck da API."""
    return {"status": "ok"}
