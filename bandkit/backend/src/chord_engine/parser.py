import re
from dataclasses import dataclass
from typing import Literal

import pdfplumber

LineType = Literal["chord", "lyric", "section", "meta", "empty"]

CHORD_NAMES = r"[A-G][#b]?(?:m|maj|min|dim|aug|sus[24]?|add\d?|M)?\d*(?:\/[A-G][#b]?)?"

CHORD_LINE_RE = re.compile(r"^\s*(?:" + CHORD_NAMES + r"\s*)+$")

SECTION_RE = re.compile(
    r"^\s*(?:Intro|Verso|Pré-?Refrão|Refrão|Ponte|Solo|Coda|"
    r"Outro|Instrumental|Bridge|Chorus|Verse|Pre-?Chorus|"
    r"Primeira\s+Parte|Segunda\s+Parte|Terceira\s+Parte|"
    r"Parte\s+\d+|Seção)",
    re.IGNORECASE,
)

_KEY_RE       = re.compile(r"(?:tono|tom|key)\s*:\s*(" + CHORD_NAMES + r")", re.IGNORECASE)
_CHORD_SCAN_RE = re.compile(CHORD_NAMES)

# ── Filtros de ruído ──────────────────────────────────────────────────────────
# Linha de tablatura: corda de guitarra + pipe  (E|---, B|---, G|---)
_TAB_STRING_RE = re.compile(r"^[EBGDAe]\s*\|")

# Cabeçalho de bloco Tab: "[Tab - Riff 1]", "Tab:", "Tab Solo"
_TAB_LABEL_RE  = re.compile(r"^\[?Tab[\s\-:]", re.IGNORECASE)

# Linha de só dígitos/espaços/símbolos de diagrama  (1 2 3, x x o, 3 3)
_DIAGRAM_RE    = re.compile(r"^[\d\s\-xXoO×○●]+$")

# Separador horizontal  (--------, ========)
_HLINE_RE      = re.compile(r"^[-=]{5,}$")

# Linha de afinação  ("Afinação: E A D G B E")
_TUNING_RE     = re.compile(r"afina[çc][aã]o", re.IGNORECASE)

# Linha de nomes de corda soltos: "E A D G B E" (sem conteúdo harmônico real)
_STRING_NAMES_RE = re.compile(r"^(?:[EBGDAe]\s+){2,}[EBGDAe]$")


def _is_noise(line: str) -> bool:
    """True para linhas que devem ser descartadas (tab, diagrama, separadores)."""
    s = line.strip()
    if not s:
        return False
    return bool(
        _TAB_STRING_RE.match(s)
        or _TAB_LABEL_RE.match(s)
        or _DIAGRAM_RE.match(s)
        or _HLINE_RE.match(s)
        or _TUNING_RE.search(s)
        or _STRING_NAMES_RE.match(s)
    )


def _lyric_text(bkcp_line: str) -> str:
    """Extrai o conteúdo de letra de uma linha BKCP (remove marcadores [Acorde])."""
    return re.sub(r"\[[^\]]+\]", "", bkcp_line).strip()


# ── API pública ───────────────────────────────────────────────────────────────


@dataclass
class ParsedLine:
    raw: str
    line_type: LineType
    content: str


def classify_line(line: str) -> LineType:
    if not line.strip():
        return "empty"
    if SECTION_RE.match(line):
        return "section"
    if CHORD_LINE_RE.match(line):
        return "chord"
    return "lyric"


def merge_chord_lyric(chord_line: str, lyric_line: str) -> str:
    result = list(lyric_line)
    offset = 0
    for m in _CHORD_SCAN_RE.finditer(chord_line):
        chord = m.group()
        pos = min(m.start(), len(lyric_line))
        token = f"[{chord}]"
        result.insert(pos + offset, token)
        offset += len(token)
    return "".join(result)


def extract_metadata(lines: list[str]) -> dict:
    meta: dict = {"title": "", "artist": "", "key": ""}
    non_empty: list[str] = []
    for line in lines[:10]:
        stripped = line.strip()
        if not stripped:
            continue
        key_match = _KEY_RE.search(stripped)
        if key_match:
            meta["key"] = key_match.group(1)
        non_empty.append(stripped)

    if non_empty:
        meta["title"] = non_empty[0]
    if len(non_empty) > 1:
        meta["artist"] = non_empty[1]
    return meta


def pdf_to_bkcp(pdf_path: str) -> tuple[str, dict]:
    with pdfplumber.open(pdf_path) as pdf:
        raw_lines: list[str] = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            raw_lines.extend(text.splitlines())

    meta = extract_metadata(raw_lines)

    header_parts = []
    if meta["title"]:
        header_parts.append(f"{{title: {meta['title']}}}")
    if meta["artist"]:
        header_parts.append(f"{{artist: {meta['artist']}}}")
    if meta["key"]:
        header_parts.append(f"{{key: {meta['key']}}}")

    body_lines: list[str] = []
    i = 0

    while i < len(raw_lines):
        line = raw_lines[i]
        stripped = line.strip()

        # ── Descarta linhas de ruído antes de qualquer outra coisa ────────────
        if _is_noise(stripped):
            i += 1
            continue

        lt = classify_line(line)

        if lt == "empty":
            body_lines.append("")
            i += 1

        elif lt == "section":
            body_lines.append(f"[{stripped}]")
            i += 1

        elif lt == "chord":
            # Tenta fazer merge com a linha seguinte se for letra não-ruído
            next_available = None
            skip_next = False
            if i + 1 < len(raw_lines):
                nxt = raw_lines[i + 1]
                nxt_lt = classify_line(nxt)
                if nxt_lt == "lyric" and not _is_noise(nxt.strip()):
                    next_available = nxt
                elif nxt_lt == "lyric":
                    skip_next = True   # próxima linha é ruído, pula junto

            if next_available is not None:
                merged = merge_chord_lyric(line, next_available)
                lyric_only = _lyric_text(merged)
                # Se a letra resultante for só dígitos é um diagrama de acorde
                if lyric_only and re.match(r"^[\d\s]*$", lyric_only):
                    # Emite só os acordes como linha standalone
                    tokens = " ".join(
                        f"[{m.group()}]" for m in _CHORD_SCAN_RE.finditer(line)
                    )
                    body_lines.append(tokens)
                else:
                    body_lines.append(merged)
                i += 2
            elif skip_next:
                # Linha de acorde seguida de ruído: emite só os acordes
                tokens = " ".join(
                    f"[{m.group()}]" for m in _CHORD_SCAN_RE.finditer(line)
                )
                body_lines.append(tokens)
                i += 2
            else:
                # Acorde standalone
                tokens = " ".join(
                    f"[{m.group()}]" for m in _CHORD_SCAN_RE.finditer(line)
                )
                body_lines.append(tokens)
                i += 1

        else:  # lyric ou meta
            body_lines.append(line.rstrip())
            i += 1

    bkcp = "\n".join(header_parts + [""] + body_lines).strip()
    return bkcp, meta
