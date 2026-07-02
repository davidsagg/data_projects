"""
scraper/precos.py — Busca de preços de referência para instrumentos musicais.

Dado um lote (descrição + nicho), consulta múltiplas fontes e retorna
o preço de revenda estimado com nível de confiança.

Ordem de prioridade das fontes:
  1. Mercado Livre Brasil (usado, mediana de 5 resultados)
  2. Two Tone Guitars
  3. High Voltage Custom Shop
"""
from __future__ import annotations

import logging
import random
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Paths e configuração
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent   # data_projects/special_gear/
sys.path.insert(0, str(ROOT))

log = logging.getLogger("special_gear.precos")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 15
PRECO_MINIMO = 200.0

# Cache em memória: {query_normalizada: resultado}
_cache: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Palavras a remover para limpar a query
# ---------------------------------------------------------------------------
_STOPWORDS = {
    "usada", "usado", "usados", "usadas", "nacional", "importada", "importado",
    "original", "semi", "novo", "nova", "cor", "preta", "branca",
    "sunburst", "natural", "burst", "case", "bag", "capa", "completo",
    "completa", "série", "serie", "edição", "edicao", "limitada", "especial",
    "guitarra", "pedal", "amplificador", "amp", "combo",
    "elétrica", "eletrica", "valvulado", "valvulada",
}

# Marcas conhecidas por nicho — usadas para priorizar na extração
_MARCAS = {
    "guitarra": [
        "fender", "gibson", "prs", "paul reed smith", "epiphone", "gretsch",
        "rickenbacker", "g&l", "suhr", "tom anderson", "collings", "Taylor",
    ],
    "pedal": [
        "strymon", "wampler", "jhs", "empress", "walrus", "fulltone", "xotic",
        "boss", "tc electronic", "eventide", "source audio", "meris",
    ],
    "amp": [
        "marshall", "vox", "fender", "tone king", "matchless", "two rock",
        "carr", "dr z", "friedman", "blackstar", "mesa boogie", "orange",
        "divided by 13",
    ],
}


# ---------------------------------------------------------------------------
# 1. Construção da query
# ---------------------------------------------------------------------------

def construir_query(descricao: str, nicho: str) -> str:
    """Extrai marca + modelo da descrição e monta query de busca.

    Usa heurística baseada em marcas conhecidas e posição das palavras
    para extrair o par mais relevante.

    Args:
        descricao: Texto da descrição do lote (maiúsculas ou mistas).
        nicho: "guitarra", "pedal" ou "amp".

    Returns:
        Query limpa para uso em buscas. Ex.: "Fender Stratocaster American Professional usada"

    Examples:
        >>> construir_query("GUITARRA FENDER STRATOCASTER AMERICAN PROFESSIONAL", "guitarra")
        'Fender Stratocaster American Professional usada'
        >>> construir_query("PEDAL STRYMON TIMELINE V2", "pedal")
        'Strymon Timeline V2 usado'
    """
    texto = descricao.strip()

    # Remove palavras de nicho do início (GUITARRA, PEDAL, AMPLIFICADOR)
    texto = re.sub(
        r"(?i)^(guitarra\s+eletrica|guitarra|pedal\s+de\s+efeito|pedal|amplificador\s+valvulado|amplificador|combo\s+valvulado|combo|amp)\s*",
        "", texto
    ).strip()

    # Remove palavras genéricas e stopwords
    partes = [
        p for p in texto.split()
        if p.lower() not in _STOPWORDS and len(p) >= 2
    ]

    # Detecta marca conhecida para o nicho e reorganiza se necessário
    marcas_nicho = _MARCAS.get(nicho, [])
    marca_encontrada = ""
    for i, p in enumerate(partes):
        if p.lower() in marcas_nicho:
            marca_encontrada = partes.pop(i)
            partes.insert(0, marca_encontrada)
            break

    # Limita a 5 termos (marca + modelo + versão)
    # title() destrói siglas como JCM800, V2, SG — capitalizamos só palavras puramente alfabéticas
    def _cap(w: str) -> str:
        # Modelos alfanuméricos (JCM800, V2) e siglas curtas (II, SG) ficam como estão
        if any(c.isdigit() for c in w):  # tem dígito -> modelo/versão
            return w
        if w.isupper() and len(w) <= 2:  # sigla curta (SG, LP, II)
            return w
        return w.capitalize()

    query_base = " ".join(_cap(p) for p in partes[:5])

    # Sufixo por nicho
    sufixo = {
        "guitarra": "usada",
        "pedal":    "usado",
        "amp":      "valvulado usado",
    }.get(nicho, "usado")

    query = f"{query_base} {sufixo}".strip()
    log.debug("construir_query: '%s' → '%s'", descricao[:60], query)
    return query


# ---------------------------------------------------------------------------
# Helper HTTP
# ---------------------------------------------------------------------------

def _get_safe(url: str, **kwargs) -> Optional[requests.Response]:
    """GET com delay aleatório, sem lançar exceção."""
    time.sleep(random.uniform(2.0, 3.0))
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        log.warning("GET falhou: %s — %s", url[:80], exc)
        return None


def _extrair_preco_texto(texto: str) -> Optional[float]:
    """Extrai valor numérico de string com moeda brasileira.

    Suporta: "R$ 3.500,00", "3500", "1.234,50", "899,00".

    Args:
        texto: String contendo valor monetário.

    Returns:
        Valor float ou None se não encontrado ou abaixo do mínimo.
    """
    t = texto.replace("\xa0", "").replace(" ", "")
    t = re.sub(r"R\$", "", t)
    # Padrão 1: 3.500,00 ou 1.234 (separadores de milhar)
    m = re.search(r"(\d{1,3}(?:\.\d{3})+(?:,\d{2})?)", t)
    if m:
        try:
            v = float(m.group(1).replace(".", "").replace(",", "."))
            return v if v >= PRECO_MINIMO else None
        except ValueError:
            pass
    # Padrão 2: 4+ dígitos sem separador (3500, 12000)
    m = re.search(r"(\d{4,})(?:[.,](\d{2}))?", t)
    if m:
        try:
            raw = m.group(1) + ("." + m.group(2) if m.group(2) else "")
            v = float(raw)
            return v if v >= PRECO_MINIMO else None
        except ValueError:
            pass
    # Padrão 3: até 3 dígitos com centavos (899,00)
    m = re.search(r"(\d{1,3}),(\d{2})", t)
    if m:
        try:
            v = float(f"{m.group(1)}.{m.group(2)}")
            return v if v >= PRECO_MINIMO else None
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Fonte 1: Mercado Livre
# ---------------------------------------------------------------------------

def _buscar_mercadolivre(query: str) -> dict:
    """Busca preços de itens usados no Mercado Livre Brasil.

    Acessa a listagem de resultados para a query e extrai os primeiros
    5 itens, calculando a mediana dos preços válidos (≥ R$ 200).

    Args:
        query: Termo de busca. Ex.: "Fender Stratocaster usada"

    Returns:
        Dict com preco_referencia, amostras, preco_min, preco_max,
        links_referencia e confianca. Precos em None se sem resultados.
    """
    slug = re.sub(r"\s+", "-", query.lower().strip())
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    url = f"https://lista.mercadolivre.com.br/{slug}?condition=used"

    log.info("  [ML] Buscando: %s", url)
    resp = _get_safe(url)
    if not resp:
        return {"fonte": "mercadolivre", "preco_referencia": None}

    soup = BeautifulSoup(resp.text, "html.parser")
    precos: list[float] = []
    links: list[str] = []

    # Seletores do layout atual do ML (maio 2025)
    items = soup.select("li.ui-search-layout__item")[:8]

    for item in items:
        # Preço: pode estar em diferentes elementos dependendo da versão do layout
        preco_el = (
            item.select_one("span.andes-money-amount__fraction") or
            item.select_one("span.price-tag-fraction") or
            item.select_one("[class*='price']")
        )
        if not preco_el:
            continue

        # Centavos
        cent_el = item.select_one("span.andes-money-amount__cents")
        texto_preco = preco_el.get_text(strip=True)
        if cent_el:
            texto_preco += f",{cent_el.get_text(strip=True)}"

        valor = _extrair_preco_texto(texto_preco)
        if valor is None:
            continue

        precos.append(valor)

        link_el = item.select_one("a.ui-search-link, a[href*='MLB']")
        if link_el:
            links.append(link_el.get("href", "").split("#")[0][:120])

        if len(precos) >= 5:
            break

    if not precos:
        log.info("  [ML] Nenhum preço extraído para '%s'", query)
        return {"fonte": "mercadolivre", "preco_referencia": None}

    mediana = statistics.median(precos)
    confianca = "alta" if len(precos) >= 4 else "média" if len(precos) >= 2 else "baixa"

    log.info("  [ML] %d amostras | mediana=R$%.0f | min=R$%.0f | max=R$%.0f",
             len(precos), mediana, min(precos), max(precos))

    return {
        "fonte": "Mercado Livre (usados)",
        "preco_referencia": round(mediana, 2),
        "amostras": len(precos),
        "preco_min": round(min(precos), 2),
        "preco_max": round(max(precos), 2),
        "links_referencia": links[:3],
        "confianca": confianca,
    }


# ---------------------------------------------------------------------------
# Fonte 2: Two Tone Guitars
# ---------------------------------------------------------------------------

def _buscar_twotone(query: str) -> dict:
    """Busca preço na Two Tone Guitars (usados nacionais premium).

    Acessa a listagem de usados e verifica se algum item faz match
    com as principais keywords da query.

    Args:
        query: Termo de busca.

    Returns:
        Dict com preco_referencia ou None se não encontrado.
    """
    url = "https://www.twotoneguitars.com.br/usados"
    log.info("  [TwoTone] Buscando: %s", url)

    resp = _get_safe(url)
    if not resp:
        return {"fonte": "Two Tone Guitars", "preco_referencia": None}

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extrai keywords relevantes da query (remove stopwords e termos genéricos)
    keywords = [
        w for w in query.lower().split()
        if w not in _STOPWORDS and len(w) >= 3
    ]

    precos: list[float] = []
    links: list[str] = []

    # Layout genérico: procura cards de produto com título e preço
    cards = soup.select("[class*='product'], [class*='item'], article")
    for card in cards:
        titulo_el = card.select_one(
            "[class*='title'], [class*='name'], h2, h3, p"
        )
        if not titulo_el:
            continue

        titulo = titulo_el.get_text(strip=True).lower()
        match_count = sum(1 for kw in keywords if kw in titulo)
        if match_count < 1:
            continue

        preco_el = card.select_one(
            "[class*='price'], [class*='preco'], [class*='valor']"
        )
        if not preco_el:
            continue

        valor = _extrair_preco_texto(preco_el.get_text(strip=True))
        if valor:
            precos.append(valor)
            link = card.select_one("a")
            if link:
                href = link.get("href", "")
                links.append(href if href.startswith("http") else "https://www.twotoneguitars.com.br" + href)

    if not precos:
        log.info("  [TwoTone] Nenhum match para '%s'", query)
        return {"fonte": "Two Tone Guitars", "preco_referencia": None}

    mediana = statistics.median(precos)
    log.info("  [TwoTone] %d amostras | mediana=R$%.0f", len(precos), mediana)

    return {
        "fonte": "Two Tone Guitars",
        "preco_referencia": round(mediana, 2),
        "amostras": len(precos),
        "preco_min": round(min(precos), 2),
        "preco_max": round(max(precos), 2),
        "links_referencia": links[:2],
        "confianca": "média" if len(precos) >= 2 else "baixa",
    }


# ---------------------------------------------------------------------------
# Fonte 3: High Voltage Custom Shop
# ---------------------------------------------------------------------------

def _buscar_highvoltage(query: str) -> dict:
    """Busca preço na High Voltage Custom Shop (pedais e guitarras boutique).

    Args:
        query: Termo de busca.

    Returns:
        Dict com preco_referencia ou None se não encontrado.
    """
    url = "https://www.highvoltagecustomshop.com.br"
    log.info("  [HighVoltage] Buscando: %s", url)

    resp = _get_safe(url)
    if not resp:
        return {"fonte": "High Voltage Custom Shop", "preco_referencia": None}

    soup = BeautifulSoup(resp.text, "html.parser")

    keywords = [
        w for w in query.lower().split()
        if w not in _STOPWORDS and len(w) >= 3
    ]

    precos: list[float] = []
    links: list[str] = []

    cards = soup.select("[class*='product'], [class*='item'], article, li")
    for card in cards:
        titulo_el = card.select_one(
            "[class*='title'], [class*='name'], [class*='produto'], h2, h3"
        )
        if not titulo_el:
            continue

        titulo = titulo_el.get_text(strip=True).lower()
        if not any(kw in titulo for kw in keywords):
            continue

        preco_el = card.select_one(
            "[class*='price'], [class*='preco'], [class*='valor'], strong, b"
        )
        if not preco_el:
            continue

        valor = _extrair_preco_texto(preco_el.get_text(strip=True))
        if valor:
            precos.append(valor)
            link = card.select_one("a")
            if link:
                href = link.get("href", "")
                links.append(href if href.startswith("http") else "https://www.highvoltagecustomshop.com.br" + href)

    if not precos:
        log.info("  [HighVoltage] Nenhum match para '%s'", query)
        return {"fonte": "High Voltage Custom Shop", "preco_referencia": None}

    mediana = statistics.median(precos)
    log.info("  [HighVoltage] %d amostras | mediana=R$%.0f", len(precos), mediana)

    return {
        "fonte": "High Voltage Custom Shop",
        "preco_referencia": round(mediana, 2),
        "amostras": len(precos),
        "preco_min": round(min(precos), 2),
        "preco_max": round(max(precos), 2),
        "links_referencia": links[:2],
        "confianca": "média" if len(precos) >= 2 else "baixa",
    }


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def buscar_preco_referencia(descricao: str, nicho: str) -> dict:
    """Busca o preço de revenda de referência para um instrumento musical.

    Consulta Mercado Livre, Two Tone Guitars e High Voltage Custom Shop
    em ordem de prioridade. Usa cache em memória para evitar buscas
    repetidas na mesma execução.

    Args:
        descricao: Descrição do lote. Ex.: "GUITARRA FENDER STRATOCASTER"
        nicho: Nicho do instrumento: "guitarra", "pedal" ou "amp".

    Returns:
        Dict com chaves:
        - preco_referencia (float | None): Melhor preço de referência encontrado.
        - fonte (str): Nome da fonte utilizada.
        - amostras (int): Número de amostras coletadas.
        - preco_min (float | None): Menor preço encontrado nas amostras.
        - preco_max (float | None): Maior preço encontrado nas amostras.
        - links_referencia (list[str]): Links dos anúncios encontrados.
        - confianca (str): "alta" | "média" | "baixa" | "indisponível"
    """
    query = construir_query(descricao, nicho)
    cache_key = query.lower().strip()

    if cache_key in _cache:
        log.info("Cache hit para '%s'", query)
        return _cache[cache_key]

    log.info("Buscando preço de referência para: '%s' [nicho=%s]", query, nicho)
    log.info("  Query construída: '%s'", query)

    resultado_vazio: dict = {
        "preco_referencia": None,
        "fonte": "indisponível",
        "amostras": 0,
        "preco_min": None,
        "preco_max": None,
        "links_referencia": [],
        "confianca": "indisponível",
    }

    fontes = [
        ("Mercado Livre", _buscar_mercadolivre),
        ("Two Tone Guitars", _buscar_twotone),
        ("High Voltage Custom Shop", _buscar_highvoltage),
    ]

    for nome_fonte, fn_busca in fontes:
        try:
            resultado = fn_busca(query)
            if resultado.get("preco_referencia") is not None:
                resultado.setdefault("amostras", 1)
                resultado.setdefault("preco_min", resultado["preco_referencia"])
                resultado.setdefault("preco_max", resultado["preco_referencia"])
                resultado.setdefault("links_referencia", [])
                resultado.setdefault("confianca", "baixa")
                _cache[cache_key] = resultado
                log.info("✅ Preço encontrado via %s: R$ %.0f (%s confiança)",
                         nome_fonte, resultado["preco_referencia"], resultado["confianca"])
                return resultado
        except Exception as exc:
            log.error("Erro inesperado em %s: %s", nome_fonte, exc)

    log.warning("❌ Nenhuma fonte retornou preço para '%s'", query)
    _cache[cache_key] = resultado_vazio
    return resultado_vazio


# ---------------------------------------------------------------------------
# Main — teste com 3 casos
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    casos = [
        ("GUITARRA FENDER STRATOCASTER AMERICAN PROFESSIONAL II USADA", "guitarra"),
        ("PEDAL STRYMON TIMELINE V2",                                   "pedal"),
        ("AMPLIFICADOR MARSHALL JCM800 VALVULADO",                      "amp"),
    ]

    sep = "═" * 65
    print(f"\n{sep}")
    print("  🎸 Special Gear — Pesquisa de Preços de Referência")
    print(sep)

    for descricao, nicho in casos:
        print(f"\n📦 Instrumento : {descricao}")
        print(f"   Nicho       : {nicho.upper()}")

        query = construir_query(descricao, nicho)
        print(f"   Query       : {query}")

        resultado = buscar_preco_referencia(descricao, nicho)

        preco = resultado.get("preco_referencia")
        if preco is not None:
            print(f"   💰 Preço ref : R$ {preco:,.0f}")
            print(f"   Fonte       : {resultado.get('fonte')}")
            print(f"   Amostras    : {resultado.get('amostras')}")
            mn = resultado.get("preco_min")
            mx = resultado.get("preco_max")
            if mn and mx:
                print(f"   Faixa       : R$ {mn:,.0f} — R$ {mx:,.0f}")
            print(f"   Confiança   : {resultado.get('confianca')}")
            links = resultado.get("links_referencia", [])
            if links:
                print(f"   Links ({len(links)})   : {links[0]}")
        else:
            print("   ⚠️  Preço indisponível (fontes fora do ar ou sem resultados)")

        print(f"   {'─'*55}")

    print(f"\n{sep}")
    print("  Busca concluída.")
    print(sep)
