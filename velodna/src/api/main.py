"""
VeloDNA API — FastAPI application entrypoint.
"""
from __future__ import annotations

from fastapi import FastAPI

from src.api.routers import activities, analytics, health_router, routes_router, coach_router

app = FastAPI(title="VeloDNA API", version="1.0.0")

app.include_router(activities.router, prefix="/activities", tags=["activities"])
app.include_router(analytics.router, tags=["analytics"])
app.include_router(health_router.router, tags=["health"])
app.include_router(routes_router.router, prefix="/routes", tags=["routes"])
app.include_router(coach_router.router, prefix="/coach", tags=["coach"])


@app.get("/health")
def health_check():
    """Endpoint de healthcheck da API."""
    return {"status": "ok"}
