"""
Ollama Client — interface HTTP com o servidor Ollama local.

Suporta geração de texto via /api/generate (non-streaming).
Lança OllamaUnavailableError se o servidor estiver offline.
"""
from __future__ import annotations

import os

import requests


class OllamaUnavailableError(Exception):
    """Levantada quando o Ollama não está acessível no host configurado."""


class OllamaClient:
    """Cliente HTTP para o servidor Ollama local."""

    def __init__(self, host: str | None = None) -> None:
        """Args:
            host: URL base do Ollama (padrão: OLLAMA_HOST env ou localhost:11434).
        """
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def generate(self, prompt: str, model: str = "llama3") -> str:
        """Envia prompt ao Ollama e retorna o texto gerado.

        Args:
            prompt: texto do prompt a ser enviado
            model: modelo a usar (padrão: llama3, fallback: mistral)

        Returns:
            Texto gerado pelo modelo.

        Raises:
            OllamaUnavailableError: se o servidor não estiver acessível.
        """
        try:
            r = requests.post(
                f"{self.host}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60,
            )
            r.raise_for_status()
            return r.json().get("response", "")
        except ConnectionError as e:
            raise OllamaUnavailableError(f"Ollama offline: {e}") from e
