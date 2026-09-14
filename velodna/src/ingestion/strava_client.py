"""
Cliente da API v3 do Strava — atividades e streams.

Dois cuidados moldam esta classe:

**Rate limit.** O Strava permite 100 requisições a cada 15 minutos e 1.000 por
dia. Cada atividade custa uma chamada de streams, então um backfill estoura a
janela de 15 minutos muito antes da cota diária. Ao receber 429 o cliente dorme
até a virada da janela — que é fixa e alinhada ao relógio — em vez de repetir a
chamada de imediato e queimar a cota restante contra novos 429.

**Renovação de token.** O access token vale 6 horas. Em vez de recebê-lo pronto,
o cliente pede um a `StravaAuth` a cada requisição — que devolve o do cache ou
renova e persiste a rotação. Um 401 no meio de um backfill longo força uma
renovação e repete a chamada uma vez.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Iterator

import requests

from ingestion.strava_auth import StravaAuth

_BASE_URL = "https://www.strava.com/api/v3"

# Canais pedidos ao Strava. `watts` só vem em atividades com medidor de
# potência; `velocity_smooth` é a velocidade já suavizada pelo próprio Strava.
STREAM_KEYS = (
    "time",
    "watts",
    "heartrate",
    "cadence",
    "velocity_smooth",
    "altitude",
    "distance",
    "latlng",
    "temp",
)

MAX_PER_PAGE = 200
DEFAULT_TIMEOUT_S = 60

# Margem somada à espera do rate limit, para não reentrar exatamente na virada.
RATE_LIMIT_PADDING_S = 5


class StravaAPIError(RuntimeError):
    """Erro devolvido pela API do Strava."""


class StravaRateLimitError(StravaAPIError):
    """Cota do Strava esgotada — a diária, que não se resolve esperando."""


class StravaClient:
    """Acesso somente-leitura às atividades do atleta autenticado."""

    def __init__(
        self,
        auth: StravaAuth | None = None,
        access_token: str | None = None,
        session: requests.Session | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        """Args:
            auth: provedor de tokens; criado do ambiente se omitido.
            access_token: token fixo, para uso pontual sem renovação automática.
            session: sessão HTTP reaproveitável.
            sleep: função de espera, injetável para testes.
        """
        self._auth = auth
        self._static_token = access_token
        if auth is None and access_token is None:
            self._auth = StravaAuth()
        self._session = session or requests.Session()
        self._sleep = sleep

    # ------------------------------------------------------------------
    # Requisições
    # ------------------------------------------------------------------

    def _token(self, force_refresh: bool = False) -> str:
        if self._static_token is not None and not force_refresh:
            return self._static_token
        if self._auth is None:
            raise StravaAPIError("Cliente sem provedor de token para renovar.")
        return self._auth.access_token(force_refresh=force_refresh)

    def _get(self, path: str, params: dict | None = None, _retried: bool = False):
        """Faz um GET autenticado, respeitando rate limit e renovando o token."""
        response = self._session.get(
            f"{_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {self._token()}"},
            params=params,
            timeout=DEFAULT_TIMEOUT_S,
        )

        if response.status_code == 401 and not _retried:
            self._token(force_refresh=True)
            return self._get(path, params, _retried=True)

        if response.status_code == 429:
            self._wait_for_rate_limit(response)
            if _retried:
                raise StravaRateLimitError(
                    "Rate limit do Strava persistiu após a espera — provavelmente a "
                    "cota diária de 1.000 requisições. Retome amanhã."
                )
            return self._get(path, params, _retried=True)

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            raise StravaAPIError(
                f"GET {path} falhou (HTTP {response.status_code}): {response.text[:200]}"
            )

        return response.json()

    def _wait_for_rate_limit(self, response: requests.Response) -> None:
        """Dorme até a virada da janela de 15 minutos do Strava.

        O Strava não manda `Retry-After`; a janela é fixa e alinhada ao relógio
        (:00, :15, :30, :45), então dá para calcular quanto falta.
        """
        now = time.time()
        seconds_into_window = now % 900
        self._sleep(900 - seconds_into_window + RATE_LIMIT_PADDING_S)

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def get_activities(
        self,
        limit: int = MAX_PER_PAGE,
        page: int = 1,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[dict]:
        """Lista uma página de atividades resumidas.

        Args:
            limit: itens por página (máximo 200 no Strava).
            page: página, começando em 1.
            after: retorna apenas atividades iniciadas depois deste instante.
            before: retorna apenas atividades iniciadas antes deste instante.

        Returns:
            Lista de atividades resumidas, como devolvida pelo Strava.
        """
        params: dict[str, Any] = {"per_page": min(limit, MAX_PER_PAGE), "page": page}
        if after is not None:
            params["after"] = int(after.timestamp())
        if before is not None:
            params["before"] = int(before.timestamp())
        return self._get("/athlete/activities", params) or []

    def iter_activities(
        self,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> Iterator[dict]:
        """Percorre todas as atividades do período, paginando sozinho.

        Args:
            after: limite inferior de data de início.
            before: limite superior de data de início.

        Yields:
            Uma atividade resumida por vez, da mais recente para a mais antiga.
        """
        page = 1
        while True:
            batch = self.get_activities(page=page, after=after, before=before)
            if not batch:
                return
            yield from batch
            if len(batch) < MAX_PER_PAGE:
                return
            page += 1

    def get_activity_streams(self, activity_id: int) -> dict:
        """Busca os streams de uma atividade.

        Args:
            activity_id: id numérico da atividade no Strava.

        Returns:
            Dicionário {canal: {"data": [...]}}; vazio se a atividade não tem
            streams (o Strava devolve 404 para atividades inseridas à mão).
        """
        return (
            self._get(
                f"/activities/{activity_id}/streams",
                {"keys": ",".join(STREAM_KEYS), "key_by_type": "true"},
            )
            or {}
        )

    def get_athlete(self) -> dict:
        """Devolve o atleta autenticado — útil para validar a credencial."""
        return self._get("/athlete") or {}
