"""
Router: /routes — análise de rotas GPX.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from src.ingestion.gpx_loader import GPXLoader
from src.routes.gpx_analyzer import GPXAnalyzer

router = APIRouter()


@router.post("/analyze")
def analyze_route(file: UploadFile = File(...)):
    """Recebe arquivo GPX, analisa perfil de elevação e retorna métricas."""
    with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    route = GPXLoader().load(tmp_path)
    profile = GPXAnalyzer().analyze(route)
    tmp_path.unlink(missing_ok=True)

    return {
        "total_gain_m": profile.total_gain_m,
        "total_loss_m": profile.total_loss_m,
        "max_gradient_pct": profile.max_gradient_pct,
        "segment_count": len(profile.segments),
    }
