"""
Auxiliar de consulta para os routers.

A implementação mora em `storage/query.py`, para que `planning/` e outras
camadas de domínio também possam usá-la sem depender de `api/`. Este módulo
permanece como ponto de importação dos routers.
"""
from __future__ import annotations

from storage.query import row, rows

__all__ = ["row", "rows"]
