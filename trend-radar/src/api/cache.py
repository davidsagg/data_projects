# src/api/cache.py — Cache em memória com TTL e suporte a invalidação por prefixo

import time
from typing import Any


class InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> tuple[Any, bool]:
        """Retorna (value, is_hit). Expira entradas stale automaticamente."""
        if key in self._store:
            value, expires_at = self._store[key]
            if time.time() < expires_at:
                return value, True
            del self._store[key]
        return None, False

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        self._store[key] = (value, time.time() + ttl)

    def invalidate(self, prefix: str = "") -> int:
        """Remove todas as entradas cujo key começa com prefix.

        Retorna o número de entradas removidas.
        """
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            del self._store[k]
        return len(keys)

    def __len__(self) -> int:
        return len(self._store)


# Singleton reutilizado por toda a aplicação
cache = InMemoryCache()
