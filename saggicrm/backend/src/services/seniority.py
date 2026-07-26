import re

C_LEVEL = "C-Level / Fundador"
DIRECTOR = "Diretoria"
MANAGER = "Gerência"
SPECIALIST = "Especialista / Analista"
ASSISTANT = "Estagiário / Assistente"
UNCLASSIFIED = "Não classificado"

SENIORITY_LEVELS = [C_LEVEL, DIRECTOR, MANAGER, SPECIALIST, ASSISTANT, UNCLASSIFIED]

# "Owner"/"Partner" are strong C-level signals on their own (business owner, law-firm
# partner) but also appear in common non-executive titles — "Product Owner" (Agile),
# "HR/Finance Business Partner" — where they mean something else entirely. Strip those
# specific phrases before testing the C-level pattern so they fall through to the
# tier their *other* words actually indicate (e.g. "Gerente de Produto" → Gerência).
_NON_EXECUTIVE_OWNER_OR_PARTNER = re.compile(
    r"\b(product|service|system|data|process|content)\s+owners?\b|\bbusiness\s+partners?\b",
    re.IGNORECASE,
)

# Checked in this order — most senior first, so e.g. "Assistant Director" lands on
# Diretoria (not Assistente) and "Manager, CFO Office" still lands on Gerência
# only if no C-level keyword also matches earlier.
_RULES = [
    (
        C_LEVEL,
        re.compile(
            r"\b(ceo|cfo|cto|coo|cio|cmo|chro|ciso|president[e]?|vice[\s-]?president[e]?|vp|"
            r"founder|co-founder|fundador[a]?|owner|propriet[áa]ri[oa]|s[óo]ci[oa]|partner|"
            r"chairman|chairwoman|chief\s+\w+\s+officer)\b",
            re.IGNORECASE,
        ),
    ),
    (
        DIRECTOR,
        re.compile(r"\b(director|diretor[a]?|head\s+of|superintendente)\b", re.IGNORECASE),
    ),
    (
        MANAGER,
        re.compile(
            r"\b(manager|gerente|gestor[a]?|supervisor[a]?|coordenador[a]?|coordinator|"
            r"team\s+lead|lead)\b",
            re.IGNORECASE,
        ),
    ),
    (
        SPECIALIST,
        re.compile(
            r"\b(specialist|especialista|analyst|analista|engineer|engenheir[oa]|"
            r"developer|desenvolvedor[a]?|consultant|consultor[a]?|architect|arquitet[oa]|"
            r"scientist|cientista|designer)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ASSISTANT,
        re.compile(r"\b(intern|estagi[áa]ri[oa]|trainee|assistant|assistente|junior|jr\.?)\b", re.IGNORECASE),
    ),
]


def classify_seniority(position: str | None) -> str:
    if not position:
        return UNCLASSIFIED

    c_level_pattern = _RULES[0][1]
    stripped = _NON_EXECUTIVE_OWNER_OR_PARTNER.sub(" ", position)
    if c_level_pattern.search(stripped):
        return C_LEVEL

    for level, pattern in _RULES[1:]:
        if pattern.search(position):
            return level
    return UNCLASSIFIED
