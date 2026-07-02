"""
alertas/telegram_sender.py
Envia alertas de leilões para um chat/canal Telegram via Bot API.

Variáveis de ambiente necessárias (.env):
    TELEGRAM_BOT_TOKEN  — token gerado pelo @BotFather
    TELEGRAM_CHAT_ID    — ID do chat/canal que receberá as mensagens
                          (pode ser negativo para grupos/canais)

Como obter o chat_id:
    1. Mande uma mensagem para o bot
    2. Acesse: https://api.telegram.org/bot<TOKEN>/getUpdates
    3. Procure "chat": {"id": <número>}
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}/{method}"

# ────────────────────────────────────────────────
# Score
# ────────────────────────────────────────────────

_DESCRICOES_VAGAS = {"instrumento", "equipamento", "material", "objeto", "outros"}

def _calcular_score(lote: dict) -> str:
    spread    = lote.get("spread", 0.0) or 0.0
    nicho     = lote.get("nicho", "")
    descricao = lote.get("descricao", "").lower()
    lote_misto   = descricao.count(",") >= 2 or "+" in descricao
    descricao_vaga = bool(set(descricao.split()) & _DESCRICOES_VAGAS) or len(descricao.split()) < 4

    if spread >= 2.5 and nicho and not lote_misto:
        return "ALTO"
    elif spread >= 1.5 and not (descricao_vaga or lote_misto):
        return "MÉDIO"
    else:
        return "BAIXO"


_SCORE_EMOJI = {"ALTO": "🟢", "MÉDIO": "🟡", "BAIXO": "🔴"}

# ────────────────────────────────────────────────
# Formatação de mensagens
# ────────────────────────────────────────────────

def _fmt_brl(valor: float | None) -> str:
    if valor is None:
        return "—"
    return f"R$ {valor:_.2f}".replace("_", ".")


def _fmt_data(iso: str | None, hora: bool = False) -> str:
    if not iso:
        return "—"
    try:
        fmt = "%d/%m/%Y %H:%M" if hora else "%d/%m/%Y"
        return datetime.fromisoformat(iso).strftime(fmt)
    except ValueError:
        return iso


def _card_telegram(lote: dict, score: str) -> str:
    """Formata um lote como mensagem Telegram (HTML, max ~4096 chars)."""
    emoji = _SCORE_EMOJI.get(score, "⚪")
    spread = lote.get("spread")
    spread_txt = f"{spread:.1f}x" if spread else "—"

    lance    = _fmt_brl(lote.get("lance_minimo"))
    preco_ref = _fmt_brl(lote.get("preco_referencia"))
    fonte    = lote.get("fonte_preco", "")
    amostras = lote.get("amostras_preco")
    fonte_txt = f" <i>({fonte}, {amostras} amostras)</i>" if amostras else (f" <i>({fonte})</i>" if fonte else "")

    nicho       = lote.get("nicho", "").capitalize()
    descricao   = lote.get("descricao", "")
    data_leilao = _fmt_data(lote.get("data_leilao"))
    prazo       = _fmt_data(lote.get("prazo_proposta"), hora=True)
    url_edital  = lote.get("url_edital", "")
    regiao      = lote.get("regiao", "")

    edital_link = f'<a href="{url_edital}">📄 Ver Edital</a>' if url_edital else ""
    fotos_link  = ""
    if lote.get("url_fotos"):
        fotos_link = f' · <a href="{lote["url_fotos"]}">📷 Fotos</a>'

    return (
        f"{emoji} <b>Score {score}</b>  ·  <i>{nicho}</i>  ·  {regiao}\n"
        f"\n"
        f"📦 <b>{descricao}</b>\n"
        f"\n"
        f"💰 Lance mínimo:    <b>{lance}</b>\n"
        f"🏷️ Preço referência: <b>{preco_ref}</b>{fonte_txt}\n"
        f"📈 Spread:          <b>{spread_txt}</b>\n"
        f"\n"
        f"📅 Leilão:          {data_leilao}\n"
        f"⏰ Prazo proposta:  {prazo}\n"
        f"\n"
        f"{edital_link}{fotos_link}"
    )


def _header_telegram(lotes: list[dict]) -> str:
    """Mensagem de resumo enviada antes dos cards individuais."""
    hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
    scores = [_calcular_score(l) for l in lotes]
    altos  = scores.count("ALTO")
    medios = scores.count("MÉDIO")
    baixos = scores.count("BAIXO")

    return (
        f"🎸 <b>Special Gear Monitor</b> · {hoje}\n"
        f"\n"
        f"{len(lotes)} oportunidades encontradas:\n"
        f"🟢 {altos} ALTO  ·  🟡 {medios} MÉDIO  ·  🔴 {baixos} BAIXO\n"
        f"\n"
        f"<i>Verifique os editais antes de dar lances.</i>"
    )


# ────────────────────────────────────────────────
# Envio via Bot API
# ────────────────────────────────────────────────

def _send_message(token: str, chat_id: str, text: str) -> bool:
    """Chama sendMessage na Bot API. Retorna True se bem-sucedido."""
    url = _API_BASE.format(token=token, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if not data.get("ok"):
            logger.error("Telegram API erro: %s", data.get("description", data))
            return False
        return True
    except requests.RequestException as exc:
        logger.error("Erro de rede ao enviar para Telegram: %s", exc)
        return False


def enviar_alerta(lotes: list[dict], config: dict | None = None) -> bool:
    """Envia os lotes como mensagens Telegram.

    Args:
        lotes: Lista de lotes enriquecidos com spread >= SPREAD_MINIMO.
        config: Dict opcional com chaves telegram_bot_token e telegram_chat_id.
                Se None, lê de TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID do .env.

    Returns:
        True se ao menos uma mensagem foi enviada com sucesso.
    """
    if not lotes:
        logger.info("Nenhum lote para alertar — Telegram não acionado.")
        return False

    cfg       = config or {}
    token     = cfg.get("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id   = cfg.get("telegram_chat_id")   or os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.error(
            "Credenciais Telegram ausentes. "
            "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env"
        )
        return False

    # Ordena: ALTO → MÉDIO → BAIXO
    ordenados = sorted(
        lotes,
        key=lambda l: {"ALTO": 0, "MÉDIO": 1, "BAIXO": 2}.get(_calcular_score(l), 3),
    )

    enviados = 0

    # 1. Mensagem de cabeçalho / resumo
    header = _header_telegram(ordenados)
    if _send_message(token, chat_id, header):
        enviados += 1
        time.sleep(0.5)  # respeita rate limit da API (30 msg/s por bot)

    # 2. Um card por lote
    for lote in ordenados:
        score = _calcular_score(lote)
        card  = _card_telegram(lote, score)
        if _send_message(token, chat_id, card):
            enviados += 1
        time.sleep(0.5)

    ts = datetime.now().isoformat(timespec="seconds")
    logger.info(
        "[%s] Telegram: %d/%d mensagens enviadas para chat %s",
        ts, enviados, len(ordenados) + 1, chat_id,
    )
    return enviados > 0
