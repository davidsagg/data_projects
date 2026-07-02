import re
from typing import Optional

USER_PROFILE = {
    "level": ["intermediário", "avançado"],
    "interests": ["jazz", "mpb", "improvisação", "harmonia"],
    "instruments": ["guitarra"],
    "goal": "aprimoramento",
}

# Mapas de palavras-chave para inferência
_CATEGORY_KEYWORDS = {
    "técnica": [
        "técnica", "postura", "mecânica", "dedilhado", "arpejos", "velocidade",
        "digitação", "articulação", "vibrato", "bending", "legato", "staccato",
        "aquecimento", "exercício técnico",
    ],
    "harmonia": [
        "harmonia", "acorde", "tensão", "substituição", "cadência", "progressão",
        "voicing", "reharmonização", "dominante", "tríade", "tétrade", "cifra",
        "campo harmônico",
    ],
    "improvisação": [
        "improv", "improvisação", "fraseologia", "linguagem", "vocabulário",
        "lick", "frase", "solo", "soloing",
    ],
    "escalas": [
        "escala", "modo", "pentatônica", "cromático", "dórico", "mixolídio",
        "lídio", "frígio", "lócrio", "alterado", "diminuta", "tons inteiros",
        "menor melódica", "menor harmônica", "drone",
    ],
    "ritmo": [
        "ritmo", "levada", "groove", "compasso", "clave", "batida", "strumming",
        "percussão", "pulsação", "tempo", "subdivisão",
    ],
    "repertório": [
        "repertório", "música", "tema", "standard", "canção", "letra",
        "cover", "backing track",
    ],
    "leitura": [
        "leitura", "partitura", "notação", "solfejo", "cifra musical",
        "tablatura", "grade",
    ],
    "composição": [
        "composição", "arranjo", "letra", "criação", "songwriting",
    ],
    "produção": [
        "produção", "gravação", "home studio", "mixagem", "masterização",
        "daw", "plugin",
    ],
    "carreira": [
        "carreira", "marketing", "networking", "mercado", "show",
        "profissional", "cachê",
    ],
    "teoria": [
        "teoria", "estrutura musical", "música", "fundamentos", "básico",
        "intervalos", "leitura",
    ],
    "trilha": [
        "trilha", "learning path", "caminho", "jornada",
    ],
    "intensivo": [
        "intensivo", "workshop", "masterclass", "imersão",
    ],
}

_LEVEL_KEYWORDS = {
    "Iniciante": [
        "iniciante", "básico", "começando", "primeiro passo", "introdução",
        "introduction", "fundamentos", "do zero",
    ],
    "Intermediário": [
        "intermediário", "intermediate", "médio",
    ],
    "Avançado": [
        "avançado", "advanced", "avancado", "master", "aprofundamento",
        "aprofundado", "complexo",
    ],
    "Todos os níveis": [
        "todos os níveis", "all levels", "qualquer nível",
    ],
}

_STYLE_KEYWORDS = {
    "jazz": [
        "jazz", "bebop", "swing", "blues jazz", "standard jazz",
        "ii v i", "ii-v-i",
    ],
    "mpb": [
        "mpb", "música popular brasileira", "brasileiro", "brasileira",
    ],
    "bossa nova": [
        "bossa nova", "bossa",
    ],
    "blues": [
        "blues",
    ],
    "rock": [
        "rock", "hard rock", "classic rock",
    ],
    "pop": [
        "pop",
    ],
    "samba": [
        "samba", "pagode",
    ],
    "forró": [
        "forró", "forro",
    ],
    "erudito": [
        "erudito", "clássico", "classico", "classical",
    ],
    "funk": [
        "funk",
    ],
    "soul": [
        "soul", "r&b",
    ],
}

_INSTRUMENT_KEYWORDS = {
    "guitarra": [
        "guitarra", "guitar", "elétrica", "eletrica",
    ],
    "violão": [
        "violão", "violao", "acústica", "acustica", "acoustic",
    ],
    "baixo": [
        "baixo", "bass",
    ],
    "piano": [
        "piano", "teclado", "keyboard",
    ],
    "bateria": [
        "bateria", "drums",
    ],
    "voz": [
        "voz", "vocal", "canto",
    ],
}


def _normalize(text: str) -> str:
    return text.lower()


def _duration_to_minutes(duration: str) -> int:
    """Converte 'HH:MM:SS' para minutos. Retorna 0 para 'Ilimitado' ou inválido."""
    if not duration or duration.lower() == "ilimitado":
        return 0
    parts = duration.strip().split(":")
    try:
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            return h * 60 + m + (1 if s >= 30 else 0)
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        pass
    return 0


class CourseParser:
    """
    Processa os dados brutos do crawler e produz um catálogo normalizado.
    """

    def parse_all_courses(self, raw_data: list[dict]) -> list[dict]:
        """Recebe lista bruta e retorna lista de cursos normalizados."""
        result = []
        for raw in raw_data:
            if raw.get("error"):
                continue
            normalized = self.normalize_course(raw)
            normalized["priority_for_user"] = self.calculate_user_priority(normalized, USER_PROFILE)
            result.append(normalized)
        return result

    def normalize_course(self, raw: dict) -> dict:
        """Normaliza um curso com o schema final."""
        title = raw.get("title", "").strip()
        description = raw.get("description", "").strip()
        text = f"{title} {description}"

        # Normalizar módulos e calcular duração total
        modules = []
        total_duration = 0
        total_lessons = 0

        for mod_order, mod in enumerate(raw.get("modules", []), start=1):
            lessons = []
            for lesson_order, lesson in enumerate(mod.get("lessons", []), start=1):
                dur_min = _duration_to_minutes(lesson.get("duration", ""))
                total_duration += dur_min
                total_lessons += 1
                lessons.append({
                    "title": lesson.get("title", "").strip(),
                    "order": lesson_order,
                    "duration_minutes": dur_min,
                    "url": lesson.get("url", ""),
                    "completed": lesson.get("completed", False),
                })
            modules.append({
                "title": mod.get("title", "").strip(),
                "order": mod_order,
                "lessons": lessons,
            })

        category = self.infer_category(title, description)
        level = raw.get("level") or self.infer_level(title, description)
        style_focus = self.infer_style_focus(title, description)
        instrument_focus = self._infer_instrument_focus(text)
        tags = self._infer_tags(title, description, category, style_focus)

        return {
            "id": raw.get("slug", ""),
            "title": title,
            "instructor": raw.get("instructor", "").strip(),
            "description": description,
            "category": category,
            "pillar": self._category_to_pillar(category),
            "level": level,
            "instrument_focus": instrument_focus,
            "style_focus": style_focus,
            "total_lessons": total_lessons,
            "total_duration_minutes": total_duration,
            "modules": modules,
            "url": raw.get("url", ""),
            "thumbnail_url": raw.get("thumbnail_url", ""),
            "tags": tags,
            "priority_for_user": 3,  # calculado depois por parse_all_courses
        }

    def infer_category(self, title: str, description: str) -> str:
        """Infere a categoria do curso com base em palavras-chave."""
        text = _normalize(f"{title} {description}")
        scores = {}
        for category, keywords in _CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score:
                scores[category] = score
        if scores:
            return max(scores, key=scores.get)
        return "outros"

    def infer_level(self, title: str, description: str) -> str:
        """Infere nível: Iniciante / Intermediário / Avançado / Todos os níveis."""
        text = _normalize(f"{title} {description}")
        for level, keywords in _LEVEL_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return level
        return "Todos os níveis"

    def infer_style_focus(self, title: str, description: str) -> list[str]:
        """Infere estilos musicais abordados no curso."""
        text = _normalize(f"{title} {description}")
        return [style for style, keywords in _STYLE_KEYWORDS.items()
                if any(kw in text for kw in keywords)]

    def _infer_instrument_focus(self, text: str) -> list[str]:
        text = _normalize(text)
        found = [inst for inst, keywords in _INSTRUMENT_KEYWORDS.items()
                 if any(kw in text for kw in keywords)]
        # Default: guitarra/violão se nenhum instrumento mencionado explicitamente
        return found if found else ["guitarra", "violão"]

    def _infer_tags(self, title: str, description: str, category: str, styles: list[str]) -> list[str]:
        text = _normalize(f"{title} {description}")
        tags = set()
        tags.add(category)
        tags.update(styles)
        extra_kws = [
            "backing track", "drone", "modo", "pentatônica", "improvisação",
            "harmonia", "jazz", "mpb", "escalas", "técnica",
        ]
        for kw in extra_kws:
            if kw in text:
                tags.add(kw)
        return sorted(tags)

    def _category_to_pillar(self, category: str) -> str:
        mapping = {
            "técnica": "Técnica Instrumental",
            "harmonia": "Harmonia",
            "improvisação": "Improvisação",
            "escalas": "Escalas",
            "ritmo": "Ritmo / Levadas",
            "repertório": "Repertório / Músicas",
            "leitura": "Leitura Musical",
            "composição": "Composição",
            "produção": "Produção",
            "carreira": "Carreira",
            "teoria": "Teoria",
            "trilha": "Trilha de Conhecimento",
            "intensivo": "Intensivo",
            "outros": "Outros",
        }
        return mapping.get(category, "Outros")

    def calculate_user_priority(self, course: dict, user_profile: dict) -> int:
        """Calcula prioridade 1-5 para o perfil do usuário."""
        score = 3  # base

        category = course.get("category", "")
        level = course.get("level", "")
        style_focus = course.get("style_focus", [])
        instrument_focus = course.get("instrument_focus", [])

        if category in ("improvisação", "harmonia", "escalas"):
            score += 2
        if "jazz" in style_focus or "mpb" in style_focus or "bossa nova" in style_focus:
            score += 2
        if level in ("Intermediário", "Avançado", "Todos os níveis"):
            score += 1
        if level == "Iniciante":
            score -= 1
        if category in ("carreira", "produção"):
            score -= 1
        if instrument_focus and "guitarra" not in instrument_focus:
            score -= 2

        return max(1, min(5, score))
