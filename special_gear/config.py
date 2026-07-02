"""
config.py — Configurações do Special Gear Monitor.

Constantes de regiões da Receita Federal, keywords de nicho e parâmetros de filtragem.
"""

# Mapeamento código → nome de região (usado só para display nos alertas).
# O scraper busca todos os editais disponíveis sem filtrar por região,
# então regiões novas são detectadas automaticamente.
REGIOES: dict[str, str] = {
    "100100":  "1RF_Norte",
    "200100":  "2RF_NE",
    "300100":  "3RF_CE",
    "400100":  "4RF_PR",
    "500100":  "5RF_BA",
    "600100":  "6RF_MG",
    "700100":  "7RF_RJ",
    "800100":  "8RF_SP",
    "900100":  "9RF_SP2",
    "1000100": "10RF_RS",
}

SLE_BASE_URL = "https://www25.receita.fazenda.gov.br/sle-sociedade/portal"

# Keywords por nicho — case-insensitive na busca.
# "instrumento" é o catch-all: captura qualquer lote rotulado como instrumento
# musical mesmo sem marca/modelo identificado.
KEYWORDS: dict[str, list[str]] = {
    "instrumento": [
        "instrumento musical", "instrumento de corda", "instrumento de sopro",
        "instrumento de percussão", "instrumento eletrico", "instrumento elétrico",
    ],
    "guitarra": [
        "fender", "gibson", "prs", "guitarra elétrica", "stratocaster",
        "telecaster", "les paul", "sg", "es-335", "american professional",
        "american ultra", "american original", "guitarra",
    ],
    "pedal": [
        "strymon", "wampler", "jhs", "empress", "walrus", "fulltone",
        "xotic", "pedal boutique", "reverb", "delay", "overdrive",
        "pedal de efeito", "timeline", "bigsky", "mobius",
    ],
    "amp": [
        "marshall", "vox", "tone king", "matchless", "two rock", "carr",
        "dr z", "divided by 13", "friedman", "amplificador valvulado",
        "combo valvulado", "amplificador guitarra", "blackstar",
    ],
}

# Spread mínimo esperado entre lance mínimo e valor de mercado (1.5 = 50% abaixo do mercado)
SPREAD_MINIMO: float = 1.5
