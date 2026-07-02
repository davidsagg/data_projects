"""
scraper/receita_federal.py — Scraper do portal SLE da Receita Federal do Brasil.

O portal SLE é um SPA Angular; usa Playwright (Chromium headless) para renderizar
as páginas. Cada edital tem sub-páginas individuais por lote (/edital/.../lote/N)
que são visitadas para extrair a descrição completa.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "leiloes.db"
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("special_gear.scraper")

from config import SLE_BASE_URL, REGIOES  # noqa: E402

# Limite de lotes visitados por edital (editais grandes têm 300+ lotes)
MAX_LOTES_POR_EDITAL = 200

# ---------------------------------------------------------------------------
# Playwright — singleton de browser
# ---------------------------------------------------------------------------

_browser = None
_playwright_ctx = None


def _get_browser():
    global _browser, _playwright_ctx
    if _browser is not None:
        return _browser
    if _playwright_ctx is not None:
        try:
            _playwright_ctx.stop()
        except Exception:
            pass
        _playwright_ctx = None
    pw = sync_playwright().start()
    _playwright_ctx = pw
    _browser = pw.chromium.launch(headless=True)
    log.info("Chromium headless iniciado.")
    return _browser


def _fetch_page(url: str, wait_selector: str = "main, body", timeout: int = 20_000) -> str:
    """Carrega url com Playwright e retorna HTML renderizado."""
    browser = _get_browser()
    page = browser.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        try:
            page.wait_for_selector(wait_selector, timeout=timeout)
        except PWTimeoutError:
            pass
        # Aguarda estabilização do Angular
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except PWTimeoutError:
            pass
        return page.content()
    finally:
        page.close()


def _close_browser():
    global _browser, _playwright_ctx
    if _browser:
        _browser.close()
        _browser = None
    if _playwright_ctx:
        _playwright_ctx.stop()
        _playwright_ctx = None


# ---------------------------------------------------------------------------
# 1. Buscar todos os editais ativos
# ---------------------------------------------------------------------------

def _url_de_edital_id(edital_raw: str) -> str:
    """Converte '0900100/000005/2026' → URL do portal SLE."""
    partes = edital_raw.strip().split("/")
    if len(partes) != 3:
        return ""
    codigo = str(int(partes[0]))   # remove zeros à esquerda: 0900100 → 900100
    numero = str(int(partes[1]))   # 000005 → 5
    ano    = partes[2].strip()
    return f"{SLE_BASE_URL}/edital/{codigo}/{numero}/{ano}"


def _regiao_de_url(url: str) -> str:
    m = re.search(r"/edital/(\d+)/", url)
    if m:
        return REGIOES.get(m.group(1), m.group(1))
    return "desconhecida"


def buscar_todos_editais() -> list[dict]:
    """Carrega editais-disponiveis e retorna todos os editais ativos.

    Usa dois métodos em cascata:
    1. Links <a href="/edital/..."> no HTML renderizado
    2. Padrão de texto XXXXXXX/NNNNNN/YYYY na página (fallback quando o
       Angular usa roteamento sem <a> convencional)
    """
    url = f"{SLE_BASE_URL}/editais-disponiveis"
    log.info("Buscando editais disponíveis: %s", url)

    try:
        html = _fetch_page(url, wait_selector="table, tbody, tr", timeout=30_000)
    except Exception as exc:
        log.error("Falha ao carregar editais: %s", exc)
        return []

    soup = BeautifulSoup(html, "html.parser")
    editais: list[dict] = []
    vistos: set[str] = set()

    # ── Método 1: links <a href> ──────────────────────────────────────────
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/edital/" not in href or "/lote/" in href:
            continue
        url_edital = href if href.startswith("http") else f"https://www25.receita.fazenda.gov.br{href}"
        if url_edital in vistos:
            continue
        vistos.add(url_edital)
        row = a.find_parent("tr") or a.find_parent("li") or a.find_parent("div")
        data_leilao, prazo_proposta = _extrair_datas(row)
        num_lotes = _extrair_num_lotes(row)
        editais.append({
            "edital_id": _edital_id_de_url(url_edital),
            "titulo": a.get_text(strip=True) or url_edital,
            "url_edital": url_edital,
            "data_leilao": data_leilao,
            "prazo_proposta": prazo_proposta,
            "regiao": _regiao_de_url(url_edital),
            "num_lotes": num_lotes,
        })

    # ── Método 2: padrão de texto na tabela (fallback para Angular router) ─
    if not editais:
        log.info("Nenhum link <a> encontrado — usando fallback de padrão de texto.")
        for m in re.finditer(r"(\d{6,7}/\d{6}/\d{4})", soup.get_text()):
            edital_raw = m.group(1)
            url_edital = _url_de_edital_id(edital_raw)
            if not url_edital or url_edital in vistos:
                continue
            vistos.add(url_edital)

            # Tenta encontrar datas e nº de lotes pelo contexto na página
            celulas = _contexto_celulas(soup, edital_raw)
            data_leilao, prazo_proposta = _extrair_datas_de_textos(celulas)
            num_lotes = _extrair_num_lotes_de_textos(celulas)

            editais.append({
                "edital_id": _edital_id_de_url(url_edital),
                "titulo": edital_raw,
                "url_edital": url_edital,
                "data_leilao": data_leilao,
                "prazo_proposta": prazo_proposta,
                "regiao": _regiao_de_url(url_edital),
                "num_lotes": num_lotes,
            })

    log.info("%d editais encontrados.", len(editais))
    return editais


def _edital_id_de_url(url: str) -> str:
    """Extrai edital_id da URL: .../edital/900100/5/2026 → 900100__5__2026"""
    m = re.search(r"/edital/(\d+)/(\d+)/(\d{4})", url)
    if m:
        return f"{m.group(1)}__{m.group(2)}__{m.group(3)}"
    return url.split("/")[-1]


def _extrair_num_lotes(elemento) -> int:
    """Tenta ler quantidade de lotes de um elemento de linha da tabela."""
    if not elemento:
        return 0
    return _extrair_num_lotes_de_textos([elemento.get_text(" ", strip=True)])


def _extrair_num_lotes_de_textos(textos: list[str]) -> int:
    for t in textos:
        m = re.search(r"\b(\d{1,4})\b(?=\s*$|\s*lote)", t, re.IGNORECASE)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 5000:
                return v
    return 0


def _contexto_celulas(soup, texto_alvo: str) -> list[str]:
    """Retorna textos das células da linha que contém texto_alvo."""
    for tag in soup.find_all(string=re.compile(re.escape(texto_alvo))):
        row = tag.find_parent("tr")
        if row:
            return [td.get_text(" ", strip=True) for td in row.find_all("td")]
    return []


def _extrair_datas(elemento) -> tuple[str, str]:
    if not elemento:
        return "", ""
    return _extrair_datas_de_textos([elemento.get_text(" ", strip=True)])


def _extrair_datas_de_textos(textos: list[str]) -> tuple[str, str]:
    datas: list[str] = []
    for t in textos:
        for m in re.finditer(r"\d{2}/\d{2}/\d{4}(?:\s+às\s+\d{2}:\d{2})?", t):
            datas.append(m.group().replace(" às ", " "))
            if len(datas) == 2:
                break
        if len(datas) == 2:
            break
    return (datas[0] if datas else ""), (datas[1] if len(datas) > 1 else "")


# ---------------------------------------------------------------------------
# 2. Buscar lotes de um edital — visita cada sub-página /lote/N
# ---------------------------------------------------------------------------

def baixar_e_parsear_edital(url_edital: str, num_lotes: int = 0) -> list[dict]:
    """Coleta todos os lotes de um edital visitando cada página /lote/N.

    Estratégia:
    1. Carrega a página do edital e extrai links /lote/N já renderizados.
    2. Se não encontrar links, enumera de 1 até num_lotes (ou MAX_LOTES_POR_EDITAL).
    3. Para cada URL de lote, chama _parsear_pagina_lote().

    Args:
        url_edital: URL base do edital (sem /lote/).
        num_lotes: Quantidade de lotes informada na listagem (opcional).
    """
    log.info("Abrindo edital: %s", url_edital)

    urls_lote = _coletar_urls_lotes(url_edital, num_lotes)
    if not urls_lote:
        log.warning("  Nenhuma URL de lote encontrada para %s", url_edital)
        return []

    log.info("  %d lotes a visitar.", len(urls_lote))
    lotes: list[dict] = []
    for i, (url_lote, num) in enumerate(urls_lote, 1):
        lote = _parsear_pagina_lote(url_lote, str(num))
        if lote:
            lotes.append(lote)
        if i % 20 == 0:
            log.info("  Progresso: %d/%d lotes processados.", i, len(urls_lote))

    log.info("  %d lotes extraídos de %s", len(lotes), url_edital)
    return lotes


def _coletar_urls_lotes(url_edital: str, num_lotes_hint: int) -> list[tuple[str, int]]:
    """Retorna lista de (url_lote, numero_lote) para o edital."""
    try:
        html = _fetch_page(url_edital, wait_selector="a[href*='/lote/'], table, tbody", timeout=25_000)
    except Exception as exc:
        log.error("Erro ao carregar página do edital: %s", exc)
        return []

    soup = BeautifulSoup(html, "html.parser")
    base = "https://www25.receita.fazenda.gov.br"

    # Coleta links /lote/N já presentes no HTML renderizado
    encontrados: dict[int, str] = {}
    for a in soup.find_all("a", href=True):
        m = re.search(r"/lote/(\d+)", a["href"])
        if m:
            num = int(m.group(1))
            href = a["href"]
            encontrados[num] = href if href.startswith("http") else base + href

    if encontrados:
        return sorted([(url, num) for num, url in encontrados.items()], key=lambda x: x[1])

    # Fallback: enumera de 1 até num_lotes (ou MAX_LOTES_POR_EDITAL)
    total = min(num_lotes_hint or MAX_LOTES_POR_EDITAL, MAX_LOTES_POR_EDITAL)
    if total == 0:
        total = MAX_LOTES_POR_EDITAL
    log.info("  Enumerando %d lotes por URL direta.", total)
    return [(f"{url_edital}/lote/{n}", n) for n in range(1, total + 1)]


def _parsear_pagina_lote(url_lote: str, numero_lote: str) -> Optional[dict]:
    """Carrega a página de um lote individual e extrai seus dados."""
    try:
        html = _fetch_page(url_lote, wait_selector="h1, h2, p, .descricao, main", timeout=20_000)
    except Exception as exc:
        log.debug("Erro ao carregar lote %s: %s", url_lote, exc)
        return None

    soup = BeautifulSoup(html, "html.parser")
    texto_pagina = soup.get_text(" ", strip=True)

    # Se a página ainda está carregando ou é 404, descarta
    if len(texto_pagina) < 30 or "página não encontrada" in texto_pagina.lower():
        return None

    descricao = _extrair_descricao_lote(soup)
    if not descricao:
        return None

    fotos: list[str] = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src and any(ext in src.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
            fotos.append(src if src.startswith("http") else f"https://www25.receita.fazenda.gov.br{src}")

    return {
        "numero_lote": numero_lote,
        "descricao": descricao,
        "lance_minimo": _extrair_valor([texto_pagina]),
        "fotos_urls": fotos[:3],
        "localidade": _extrair_localidade([texto_pagina]),
        "url_lote": url_lote,
    }


def _extrair_descricao_lote(soup: BeautifulSoup) -> str:
    """Extrai a descrição principal de uma página de lote."""
    # Tenta campos semânticos comuns no SLE
    for seletor in ("h1", "h2", ".descricao", ".titulo-lote", "[class*='descri']", "[class*='titulo']"):
        el = soup.select_one(seletor)
        if el:
            texto = el.get_text(" ", strip=True)
            if len(texto) > 8:
                return texto

    # Fallback: maior parágrafo da página
    paragrafos = [(len(p.get_text()), p.get_text(" ", strip=True)) for p in soup.find_all("p")]
    paragrafos.sort(reverse=True)
    for _, texto in paragrafos[:3]:
        if len(texto) > 15:
            return texto

    return ""


# ---------------------------------------------------------------------------
# Helpers de extração
# ---------------------------------------------------------------------------

def _extrair_valor(texts: list[str]) -> Optional[float]:
    for t in texts:
        m = re.search(r"R?\$?\s*([\d.,]+)", t.replace(" ", ""))
        if m:
            raw = m.group(1).replace(".", "").replace(",", ".")
            try:
                v = float(raw)
                if v > 10:
                    return v
            except ValueError:
                continue
    return None


def _extrair_localidade(texts: list[str]) -> str:
    for t in texts:
        if re.search(r"\b(SP|RJ|PR|MG|RS|SC|BA|GO|DF|PE|CE|AM|PA)\b", t, re.IGNORECASE) and len(t) > 3:
            return t.strip()
    return ""


# ---------------------------------------------------------------------------
# 3. Filtrar lotes relevantes
# ---------------------------------------------------------------------------

def filtrar_lotes_relevantes(lotes: list[dict]) -> list[dict]:
    """Filtra lotes cujas descrições contêm keywords de nicho."""
    from config import KEYWORDS

    relevantes: list[dict] = []
    for lote in lotes:
        descricao = (lote.get("descricao") or "").lower()
        if not descricao:
            continue
        for nicho, palavras in KEYWORDS.items():
            encontradas = [kw for kw in palavras if kw.lower() in descricao]
            if encontradas:
                relevantes.append({**lote, "nicho": nicho, "keywords_encontradas": encontradas})
                log.info("  Lote relevante [%s] lote=%s — %s",
                         nicho, lote.get("numero_lote", "?"), encontradas)
                break
    return relevantes


# ---------------------------------------------------------------------------
# 4 e 5. SQLite
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lotes_processados (
            edital_id     TEXT NOT NULL,
            lote_numero   TEXT NOT NULL,
            processado_em TEXT NOT NULL,
            PRIMARY KEY (edital_id, lote_numero)
        )
    """)
    conn.commit()
    return conn


def verificar_ja_processado(edital_id: str, lote_numero: str) -> bool:
    conn = _get_conn()
    try:
        return conn.execute(
            "SELECT 1 FROM lotes_processados WHERE edital_id=? AND lote_numero=?",
            (edital_id, lote_numero),
        ).fetchone() is not None
    finally:
        conn.close()


def marcar_como_processado(edital_id: str, lote_numero: str) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO lotes_processados (edital_id, lote_numero, processado_em) VALUES (?,?,?)",
            (edital_id, lote_numero, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _imprimir_resultado(regiao: str, edital: dict, lote: dict) -> None:
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  LOTE RELEVANTE ENCONTRADO")
    print(f"{sep}")
    print(f"  Região       : {regiao}")
    print(f"  Edital       : {edital['edital_id']} — {edital['titulo']}")
    print(f"  Data leilão  : {edital.get('data_leilao', 'N/A')}")
    print(f"  Lote nº      : {lote.get('numero_lote', 'N/A')}")
    print(f"  Descrição    : {lote.get('descricao', '')}")
    print(f"  Lance mínimo : R$ {lote.get('lance_minimo', 'N/A')}")
    print(f"  Localidade   : {lote.get('localidade', 'N/A')}")
    print(f"  Nicho        : {lote.get('nicho', '').upper()}")
    print(f"  Keywords     : {', '.join(lote.get('keywords_encontradas', []))}")
    print(f"  URL lote     : {lote.get('url_lote', edital.get('url_edital', ''))}")
    print(sep)


if __name__ == "__main__":
    print("\nSpecial Gear Monitor — Receita Federal")
    print(f"Rodando em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")

    total_novos = 0
    try:
        editais = buscar_todos_editais()
        print(f"Editais encontrados: {len(editais)}\n")
        for edital in editais:
            lotes = baixar_e_parsear_edital(edital["url_edital"], edital.get("num_lotes", 0))
            for lote in filtrar_lotes_relevantes(lotes):
                edital_id = edital["edital_id"]
                lote_num  = lote.get("numero_lote", "0")
                if verificar_ja_processado(edital_id, lote_num):
                    continue
                _imprimir_resultado(edital.get("regiao", ""), edital, lote)
                marcar_como_processado(edital_id, lote_num)
                total_novos += 1
    finally:
        _close_browser()

    print(f"\nVarredura concluída. {total_novos} lote(s) novo(s) encontrado(s).")
