"""check_health.py — Verificação de saúde do sistema Trend Radar.

Execute:
    python scripts/check_health.py

Output: JSON com status geral 'healthy' | 'degraded' | 'critical'.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.environ.get(
    "TREND_RADAR_DB",
    str(Path(__file__).parent.parent / "data" / "trend_radar.duckdb"),
)
AIRFLOW_URL  = os.environ.get("AIRFLOW_URL",  "http://localhost:8080")
MLFLOW_URL   = os.environ.get("MLFLOW_URL",   "http://localhost:5000")
API_URL      = os.environ.get("TREND_RADAR_API", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------

def check_duckdb() -> dict:
    """Conecta ao DuckDB e conta registros por tabela relevante."""
    result: dict = {"status": "ok", "tables": {}}
    try:
        import duckdb
        conn = duckdb.connect(DB_PATH, read_only=True)
        tables = [
            "bronze_lastfm_artist_weekly",
            "bronze_youtube_channel_weekly",
            "bronze_deezer_artist_weekly",
            "silver_artists",
            "silver_weekly_plays",
            "gold_trend_scores",
            "gold_rising_artists",
            "gold_anomalies",
        ]
        for t in tables:
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                result["tables"][t] = n
            except Exception:
                result["tables"][t] = "missing"
        conn.close()
        result["db_size_mb"] = round(os.path.getsize(DB_PATH) / 1024**2, 1)
    except Exception as exc:
        result["status"] = "critical"
        result["error"] = str(exc)
    return result


def check_http(name: str, url: str, path: str = "/health") -> dict:
    """GET {url}{path} e retorna status."""
    try:
        import urllib.request
        t0 = time.perf_counter()
        with urllib.request.urlopen(f"{url}{path}", timeout=5) as resp:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            return {
                "status":      "ok",
                "http_code":   resp.status,
                "latency_ms":  elapsed_ms,
            }
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def check_circuit_breakers() -> dict:
    """Estado atual de cada circuit breaker."""
    try:
        from src.ingestion.circuit_breakers import (
            lastfm_breaker, youtube_breaker, deezer_breaker,
        )
        return {
            "lastfm":  lastfm_breaker.current_state,
            "youtube": youtube_breaker.current_state,
            "deezer":  deezer_breaker.current_state,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def check_last_pipeline_run() -> dict:
    """Timestamp da última modificação do arquivo DuckDB (proxy de último run)."""
    try:
        mtime = os.path.getmtime(DB_PATH)
        last_run = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        age_hours = round((time.time() - mtime) / 3600, 1)
        status = "ok" if age_hours < 24 * 8 else "stale"  # stale se > 8 dias
        return {"status": status, "last_modified": last_run, "age_hours": age_hours}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def check_reports() -> dict:
    """Número de relatórios MD/HTML gerados."""
    reports_dir = Path(DB_PATH).parent / "reports"
    md_files  = list(reports_dir.glob("*_report.md"))  if reports_dir.exists() else []
    html_files = list(reports_dir.glob("*_report.html")) if reports_dir.exists() else []
    return {
        "reports_md":   len(md_files),
        "reports_html": len(html_files),
        "latest": max((f.stem for f in md_files), default=None),
    }


# ---------------------------------------------------------------------------
# Agregador de status
# ---------------------------------------------------------------------------

def overall_status(checks: dict) -> str:
    db = checks.get("duckdb", {}).get("status", "unknown")
    if db == "critical":
        return "critical"

    unavailable = sum(
        1 for k in ("airflow", "mlflow", "api")
        if checks.get(k, {}).get("status") == "unavailable"
    )
    breakers = checks.get("circuit_breakers", {})
    open_breakers = sum(
        1 for v in breakers.values()
        if isinstance(v, str) and v == "open"
    )

    if unavailable >= 2 or open_breakers >= 2:
        return "degraded"
    return "healthy"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    report = {
        "checked_at": datetime.now(tz=timezone.utc).isoformat(),
        "duckdb":           check_duckdb(),
        "airflow":          check_http("airflow",  AIRFLOW_URL,  "/health"),
        "mlflow":           check_http("mlflow",   MLFLOW_URL,   "/health"),
        "api":              check_http("api",       API_URL,      "/health"),
        "circuit_breakers": check_circuit_breakers(),
        "last_pipeline_run": check_last_pipeline_run(),
        "reports":          check_reports(),
    }
    report["overall_status"] = overall_status(report)

    print(json.dumps(report, indent=2, default=str))

    # Exit code não-zero se crítico
    if report["overall_status"] == "critical":
        sys.exit(2)
    elif report["overall_status"] == "degraded":
        sys.exit(1)
