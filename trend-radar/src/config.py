# src/config.py — Configurações centralizadas via pydantic-settings
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    lastfm_api_key: str = ""
    youtube_api_key: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b"
    duckdb_path: str = "/workspace/data/trend_radar.duckdb"
    anomaly_zscore_threshold: float = 2.5
    trend_threshold: int = 65
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
