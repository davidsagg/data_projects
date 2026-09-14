"""
Autorização inicial do Strava — o passo único que só pode ser feito no navegador.

O `sync_strava.py` renova tokens sozinho, mas essa renovação precisa de um
`refresh_token` que só nasce de uma autorização explícita do atleta. Este script
conduz esse handshake: abre a tela de consentimento do Strava, recebe o código
de volta num servidor local efêmero e o troca pelo par de tokens, gravando o
resultado em `~/.velodna/strava_token.json`.

Antes de rodar, crie a aplicação em https://www.strava.com/settings/api
(qualquer nome; "Authorization Callback Domain" precisa ser exatamente
`localhost`) e coloque no `.env`:

    STRAVA_CLIENT_ID=<número mostrado na página>
    STRAVA_CLIENT_SECRET=<segredo mostrado na página>

O escopo pedido é `activity:read_all`, que inclui as atividades privadas. Sem o
`_all` o Strava devolve só as públicas, e o histórico fica com buracos.

Uso:
    .venv/bin/python scripts/authorize_strava.py
"""
from __future__ import annotations

import os
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from ingestion.strava_auth import (  # noqa: E402
    TOKEN_URL,
    StravaTokens,
    StravaTokenStore,
)

CALLBACK_PORT = 8099
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/exchange_token"
SCOPE = "activity:read_all,profile:read_all"

_PAGE = """<!doctype html><meta charset="utf-8">
<body style="font-family:system-ui;padding:3rem;text-align:center">
<h2>{title}</h2><p>{message}</p><p>Pode fechar esta aba.</p></body>"""


class _CallbackHandler(BaseHTTPRequestHandler):
    """Captura o `code` que o Strava devolve no redirect."""

    code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:  # noqa: N802 — assinatura da stdlib
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _CallbackHandler.code = (params.get("code") or [None])[0]
        _CallbackHandler.error = (params.get("error") or [None])[0]

        ok = _CallbackHandler.code is not None
        body = _PAGE.format(
            title="✓ Autorizado" if ok else "✗ Falhou",
            message=(
                "Volte ao terminal — os tokens foram gravados."
                if ok
                else f"O Strava respondeu: {_CallbackHandler.error}"
            ),
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args) -> None:
        """Silencia o log de acesso da stdlib."""


def authorize_url(client_id: str) -> str:
    """Monta a URL da tela de consentimento do Strava."""
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "approval_prompt": "force",
            "scope": SCOPE,
        }
    )
    return f"https://www.strava.com/oauth/authorize?{query}"


def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    """Troca o código de autorização pelo primeiro par de tokens."""
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Troca do código falhou (HTTP {response.status_code}): {response.text[:300]}"
        )
    return response.json()


def main() -> int:
    client_id = os.getenv("STRAVA_CLIENT_ID", "")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET", "")

    if not client_id or not client_secret or client_id.startswith("your"):
        print(
            "✗ STRAVA_CLIENT_ID e STRAVA_CLIENT_SECRET não estão configurados no .env.\n"
            "  Crie a aplicação em https://www.strava.com/settings/api\n"
            "  (Authorization Callback Domain = localhost) e copie os dois valores.",
            file=sys.stderr,
        )
        return 1

    url = authorize_url(client_id)
    print("Abrindo o Strava no navegador para autorizar…")
    print(f"Se não abrir sozinho, acesse:\n  {url}\n")
    webbrowser.open(url)

    server = HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    print(f"Aguardando o retorno em {REDIRECT_URI} …")
    server.handle_request()
    server.server_close()

    if not _CallbackHandler.code:
        print(f"✗ Autorização não concluída: {_CallbackHandler.error}", file=sys.stderr)
        return 1

    payload = exchange_code(client_id, client_secret, _CallbackHandler.code)

    store = StravaTokenStore()
    store.save(
        StravaTokens(
            refresh_token=payload["refresh_token"],
            access_token=payload["access_token"],
            expires_at=int(payload.get("expires_at") or 0),
        )
    )

    athlete = payload.get("athlete") or {}
    name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
    print(f"\n✓ Autorizado como {name or athlete.get('id')}")
    print(f"  Tokens gravados em {store.path}")
    print(
        "\nO .env não precisa mais do STRAVA_REFRESH_TOKEN — a partir daqui a\n"
        "rotação é gerenciada nesse arquivo. Próximo passo:\n"
        "  .venv/bin/python scripts/sync_strava.py --days 90"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
