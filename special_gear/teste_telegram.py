from alertas.telegram_sender import enviar_alerta

lote_teste = {
    "descricao": "GUITARRA FENDER STRATOCASTER AMERICAN PROFESSIONAL II",
    "nicho": "guitarra",
    "lance_minimo": 1500.0,
    "preco_referencia": 4200.0,
    "spread": 2.8,
    "confianca": "alta",
    "fonte_preco": "Mercado Livre (usados)",
    "amostras_preco": 5,
    "data_leilao": "2026-05-20",
    "prazo_proposta": "2026-05-18T17:00:00",
    "url_edital": "https://www.rfb.gov.br/exemplo",
    "regiao": "8RF_SP",
}

enviar_alerta([lote_teste])
