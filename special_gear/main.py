"""
main.py
Orquestrador principal do Special Gear Monitor.

Uso:
    python main.py          # Roda imediatamente e agenda execução diária às 08:00
    python main.py --test   # Roda um único ciclo e encerra (sem agendamento)
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime

import schedule
from dotenv import load_dotenv

from config import SPREAD_MINIMO
from scraper.receita_federal import (
    buscar_todos_editais,
    baixar_e_parsear_edital,
    filtrar_lotes_relevantes,
    verificar_ja_processado,
    marcar_como_processado,
    _close_browser,
)
from scraper.precos import buscar_preco_referencia
from alertas.telegram_sender import enviar_alerta

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("special_gear")


# ── Pipeline principal ────────────────────────────────────────────────────────

def executar_ciclo() -> None:
    """Executa um ciclo completo: busca → parse → filtra → preço → alerta."""
    inicio = datetime.now()
    logger.info("=== Iniciando ciclo [%s] ===", inicio.strftime("%Y-%m-%d %H:%M:%S"))

    stats = {
        "editais_encontrados": 0,
        "lotes_totais": 0,
        "lotes_relevantes": 0,
        "lotes_novos": 0,
        "lotes_com_spread": 0,
    }

    alertas: list[dict] = []

    try:
        editais = buscar_todos_editais()
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro ao buscar editais: %s", exc)
        editais = []

    stats["editais_encontrados"] = len(editais)
    logger.info("Total de editais encontrados: %d", len(editais))

    for edital in editais:
        edital_id  = edital.get("edital_id", "")
        url_edital = edital.get("url_edital", "")
        regiao     = edital.get("regiao", "")

        try:
            lotes = baixar_e_parsear_edital(url_edital, edital.get("num_lotes", 0))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erro ao parsear edital %s: %s", edital_id, exc)
            continue

        stats["lotes_totais"] += len(lotes)

        lotes_relevantes = filtrar_lotes_relevantes(lotes)
        stats["lotes_relevantes"] += len(lotes_relevantes)

        for lote in lotes_relevantes:
            lote_numero = lote.get("numero_lote", "0")

            if verificar_ja_processado(edital_id, lote_numero):
                logger.debug("Lote já processado, pulando: edital=%s lote=%s", edital_id, lote_numero)
                continue

            stats["lotes_novos"] += 1

            lote["edital_id"]      = edital_id
            lote["url_edital"]     = url_edital
            lote["data_leilao"]    = edital.get("data_leilao")
            lote["prazo_proposta"] = edital.get("prazo_proposta")
            lote["regiao"]         = regiao

            nicho     = lote.get("nicho", "")
            descricao = lote.get("descricao", "")

            preco_info = buscar_preco_referencia(descricao, nicho)
            lote["preco_referencia"] = preco_info.get("preco_referencia")
            lote["confianca"]        = preco_info.get("confianca", "indisponível")
            lote["fonte_preco"]      = preco_info.get("fonte", "")
            lote["amostras_preco"]   = preco_info.get("amostras")

            lance = lote.get("lance_minimo")
            ref   = lote.get("preco_referencia")
            lote["spread"] = round(ref / lance, 2) if lance and ref and lance > 0 else None

            marcar_como_processado(edital_id, lote_numero)

            spread = lote.get("spread")
            if spread and spread >= SPREAD_MINIMO:
                stats["lotes_com_spread"] += 1
                alertas.append(lote)
                logger.info(
                    "✅ Oportunidade: %s | spread=%.1fx | lance=%.0f | ref=%.0f",
                    descricao, spread, lance or 0, ref or 0,
                )
            else:
                logger.debug("Lote sem spread mínimo: %s (spread=%s)", descricao, spread)

    # Enviar alerta se houver lotes com spread suficiente
    if alertas:
        logger.info("Enviando alerta Telegram com %d lotes...", len(alertas))
        enviado = enviar_alerta(alertas)
        if enviado:
            logger.info("Alerta Telegram enviado com sucesso.")
        else:
            logger.warning("Falha no envio do alerta Telegram.")
    else:
        logger.info("Nenhuma oportunidade com spread >= %.1fx encontrada.", SPREAD_MINIMO)

    _close_browser()
    duracao = (datetime.now() - inicio).total_seconds()
    logger.info(
        "=== Ciclo concluído em %.1fs | %s ===",
        duracao,
        " | ".join(f"{k}={v}" for k, v in stats.items()),
    )


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Special Gear Monitor — leilões da Receita Federal")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Roda um único ciclo e encerra sem agendar execuções futuras",
    )
    args = parser.parse_args()

    logger.info("Special Gear Monitor iniciado")

    # Executa imediatamente ao iniciar
    executar_ciclo()

    if args.test:
        logger.info("Modo --test: encerrando após um ciclo.")
        return

    # Agenda execução diária às 08:00
    schedule.every().day.at("08:00").do(executar_ciclo)
    logger.info("Próxima execução agendada para 08:00 (diária). Ctrl+C para encerrar.")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
