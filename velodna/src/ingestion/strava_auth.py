"""
Autenticação OAuth do Strava — obtenção e renovação do access token.

O ponto delicado é a **rotação**: cada chamada ao endpoint de refresh devolve um
`refresh_token` novo e invalida o anterior. Se o token novo não for gravado, a
credencial guardada vira lixo e a próxima sincronização falha com 400 — um erro
que parece de configuração e na verdade é de persistência.

Por isso os tokens vivem num arquivo próprio (`~/.velodna/strava_token.json`,
mesmo espírito do `~/.garminconnect` usado pelo cliente do Garmin), gravado de
forma atômica antes de o access token ser devolvido a quem pediu. O `.env` serve
apenas de semente na primeira execução e nunca é reescrito.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

TOKEN_URL = "https://www.strava.com/oauth/token"

# Renova um pouco antes de expirar: um token que vence no meio de um backfill
# longo derrubaria o lote inteiro.
EXPIRY_MARGIN_S = 300

DEFAULT_TOKEN_PATH = Path.home() / ".velodna" / "strava_token.json"


class StravaAuthError(RuntimeError):
    """Falha de autenticação — credencial ausente, inválida ou revogada."""


@dataclass
class StravaTokens:
    """Conjunto de credenciais do Strava, como persistido em disco."""

    refresh_token: str
    access_token: str | None = None
    expires_at: int = 0

    @property
    def is_fresh(self) -> bool:
        """Indica se o access token ainda vale pela margem de segurança."""
        return bool(self.access_token) and self.expires_at - EXPIRY_MARGIN_S > time.time()

    def to_dict(self) -> dict:
        return {
            "refresh_token": self.refresh_token,
            "access_token": self.access_token,
            "expires_at": self.expires_at,
        }


class StravaTokenStore:
    """Lê e grava os tokens do Strava em disco, preservando a rotação."""

    def __init__(self, path: Path | None = None) -> None:
        """Args:
            path: arquivo de tokens; usa `~/.velodna/strava_token.json` se omitido.
        """
        env_path = os.getenv("VELODNA_STRAVA_TOKEN_FILE")
        self._path = Path(path or env_path or DEFAULT_TOKEN_PATH)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> StravaTokens | None:
        """Carrega os tokens do disco, ou do `.env` na primeira execução.

        Returns:
            StravaTokens, ou None se não houver nenhuma credencial disponível.
        """
        if self._path.exists():
            data = json.loads(self._path.read_text())
            if data.get("refresh_token"):
                return StravaTokens(
                    refresh_token=data["refresh_token"],
                    access_token=data.get("access_token"),
                    expires_at=int(data.get("expires_at") or 0),
                )

        seed = os.getenv("STRAVA_REFRESH_TOKEN")
        return StravaTokens(refresh_token=seed) if seed else None

    def save(self, tokens: StravaTokens) -> None:
        """Grava os tokens de forma atômica.

        A escrita passa por um arquivo temporário no mesmo diretório seguido de
        `os.replace`: se o processo morrer no meio, o arquivo antigo continua
        íntegro em vez de virar um JSON truncado que ninguém consegue ler.

        Args:
            tokens: credenciais a persistir.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(".tmp")
        temp.write_text(json.dumps(tokens.to_dict(), indent=2))
        os.replace(temp, self._path)
        self._path.chmod(0o600)


class StravaAuth:
    """Fornece um access token válido, renovando e persistindo quando preciso."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        store: StravaTokenStore | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """Args:
            client_id: id da aplicação; lido de `STRAVA_CLIENT_ID` se omitido.
            client_secret: segredo; lido de `STRAVA_CLIENT_SECRET` se omitido.
            store: repositório de tokens; usa o padrão em disco se omitido.
            session: sessão HTTP reaproveitável.
        """
        self._client_id = client_id or os.getenv("STRAVA_CLIENT_ID")
        self._client_secret = client_secret or os.getenv("STRAVA_CLIENT_SECRET")
        self._store = store or StravaTokenStore()
        self._session = session or requests.Session()

    def access_token(self, force_refresh: bool = False) -> str:
        """Devolve um access token válido.

        Args:
            force_refresh: renova mesmo que o token em cache pareça válido.

        Returns:
            Access token pronto para o header `Authorization`.

        Raises:
            StravaAuthError: se faltar credencial ou o Strava recusar a renovação.
        """
        tokens = self._store.load()
        if tokens is None:
            raise StravaAuthError(
                "Nenhum refresh token do Strava encontrado. Defina STRAVA_REFRESH_TOKEN "
                f"no .env ou crie {self._store.path}."
            )

        if tokens.is_fresh and not force_refresh:
            return tokens.access_token  # type: ignore[return-value]

        return self._refresh(tokens)

    def _refresh(self, tokens: StravaTokens) -> str:
        """Troca o refresh token por um access token novo e persiste a rotação."""
        if not self._client_id or not self._client_secret:
            raise StravaAuthError(
                "STRAVA_CLIENT_ID e STRAVA_CLIENT_SECRET precisam estar definidos."
            )

        response = self._session.post(
            TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
                "refresh_token": tokens.refresh_token,
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise StravaAuthError(
                f"Strava recusou a renovação do token (HTTP {response.status_code}): "
                f"{response.text[:200]}"
            )

        payload = response.json()

        # Persistir ANTES de devolver. O refresh token antigo já foi invalidado
        # pelo Strava neste ponto; perder o novo aqui significa perder o acesso.
        rotated = StravaTokens(
            refresh_token=payload.get("refresh_token") or tokens.refresh_token,
            access_token=payload["access_token"],
            expires_at=int(payload.get("expires_at") or 0),
        )
        self._store.save(rotated)
        return rotated.access_token  # type: ignore[return-value]
