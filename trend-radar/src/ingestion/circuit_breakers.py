# src/ingestion/circuit_breakers.py — Circuit breakers para os clientes de API

import logging
import pybreaker

logger = logging.getLogger(__name__)


class TrendRadarCircuitBreakerListener(pybreaker.CircuitBreakerListener):
    """Loga cada mudança de estado (CLOSED → OPEN → HALF_OPEN → CLOSED)."""

    def state_change(self, cb, old_state, new_state):
        logger.warning(
            "[CircuitBreaker] %s: %s → %s",
            cb.name, old_state.name, new_state.name,
        )


_listener = TrendRadarCircuitBreakerListener()

# Last.fm: tolerante (5 falhas, reset 5 min)
lastfm_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=300,
    name="lastfm",
    listeners=[_listener],
)

# YouTube: menos tolerante — quota é recurso escasso (3 falhas, reset 10 min)
youtube_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=600,
    name="youtube",
    listeners=[_listener],
)

# Deezer: configuração padrão (5 falhas, reset 5 min)
deezer_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=300,
    name="deezer",
    listeners=[_listener],
)
