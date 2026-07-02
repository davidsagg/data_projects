# Prompt 03 — Parser e Estruturação dos Dados

## Como usar este prompt

Execute após o Prompt 02 ter gerado os HTMLs brutos em `data/raw/`. Cole no Claude Code.

## PROMPT PARA O CLAUDE CODE:

Crie o parser que normaliza os dados brutos do scraper e gera um catálogo estruturado dos cursos do Fica a Dica Premium.

### Arquivo `scraper/parser.py`

```python
class CourseParser:
    """
    Processa os dados brutos (JSON/HTML) do crawler e produz
    um catálogo normalizado e enriquecido.
    """

    def parse_all_courses(self, raw_data: list[dict]) -> list[dict]:
        """Recebe a lista bruta e retorna lista de cursos normalizados."""

    def normalize_course(self, raw: dict) -> dict:
        """
        Normaliza um curso com o schema final:
        {
            "id": str,              # slug do curso
            "title": str,
            "instructor": str,
            "description": str,
            "category": str,        # ver categorias abaixo
            "pillar": str,          # 7 pilares
            "level": str,           # Iniciante / Intermediário / Avançado
            "instrument_focus": list[str],  # ["guitarra", "violão", "piano", etc]
            "style_focus": list[str],       # ["jazz", "mpb", "blues", "pop", etc]
            "total_lessons": int,
            "total_duration_minutes": int,
            "modules": [
                {
                    "title": str,
                    "order": int,
                    "lessons": [
                        {
                            "title": str,
                            "order": int,
                            "duration_minutes": int,
                            "url": str,
                            "completed": bool
                        }
                    ]
                }
            ],
            "url": str,
            "thumbnail_url": str,
            "tags": list[str],      # tags inferidas do título/descrição
            "priority_for_user": int  # 1-5, calculado pelo ranker
        }
        """

    def infer_category(self, title: str, description: str) -> str:
        """
        Infere a categoria do curso com base em palavras-chave.

        Categorias:
        - "técnica"       → postura, mecânica, dedilhado, arpejos, velocidade
        - "harmonia"      → acordes, harmonia, tensões, substituições, cadências
        - "improvisação"  → improv, fraseologia, linguagem, vocabulário
        - "escalas"       → escala, modo, pentatônica, cromático
        - "ritmo"         → ritmo, levada, groove, compasso, clave
        - "repertório"    → música, tema, standard, repertório, canção
        - "leitura"       → leitura, partitura, cifra, notação
        - "composição"    → composição, arranjo, letra
        - "produção"      → produção, gravação, home studio
        - "carreira"      → carreira, marketing, networking
        - "teoria"        → teoria, estrutura musical
        - "trilha"        → trilha de conhecimento, learning path
        - "intensivo"     → intensivo, workshop
        - "outros"        → fallback
        """

    def infer_level(self, title: str, description: str) -> str:
        """
        Infere nível: Iniciante / Intermediário / Avançado / Todos os níveis
        Baseado em palavras-chave e contexto.
        """

    def infer_style_focus(self, title: str, description: str) -> list[str]:
        """
        Infere estilos musicais abordados no curso.
        Estilos: jazz, mpb, bossa nova, blues, rock, pop, erudito, brasileiro
        """

    def calculate_user_priority(self, course: dict, user_profile: dict) -> int:
        """
        Calcula prioridade 1-5 para o perfil do usuário:

        Perfil do usuário (vem de user_profile.json):
        - Nível: intermediário/avançado
        - Interesses: jazz, mpb, improvisação, harmonia
        - Instrumento: guitarra (foco em jazz e MPB)
        - Objetivo: aprimoramento, não iniciação

        Regras de pontuação:
        +2 se category in ["improvisação", "harmonia", "escalas"]
        +2 se "jazz" in style_focus or "mpb" in style_focus
        +1 se level in ["Intermediário", "Avançado", "Todos os níveis"]
        -1 se level == "Iniciante"
        -1 se category in ["carreira", "produção"]
        -2 se instrument_focus não inclui "guitarra"

        Retorna valor entre 1 e 5.
        """
```

### Arquivo `scraper/exporter.py`

```python
class DataExporter:
    """Exporta o catálogo em múltiplos formatos."""

    def to_json(self, courses: list[dict], path: str):
        """Salva JSON formatado em data/courses.json"""

    def to_csv(self, courses: list[dict], path: str):
        """
        Salva CSV flat em data/courses.csv com colunas:
        id, title, instructor, category, pillar, level,
        style_focus, total_lessons, total_duration_minutes,
        priority_for_user, url
        """

    def to_markdown_catalog(self, courses: list[dict], path: str):
        """
        Gera data/catalog.md — catálogo legível, agrupado por categoria,
        ordenado por prioridade do usuário.
        Inclui emoji de prioridade: ⭐⭐⭐⭐⭐ para prioridade 5.
        """

    def summary_report(self, courses: list[dict]) -> str:
        """
        Gera relatório resumido com rich.table:
        - Total de cursos por categoria
        - Total de horas de conteúdo
        - Top 10 cursos por prioridade do usuário
        - Professores mais presentes
        """
```

### Script `run_parser.py` na raiz:

Processa `data/courses_raw.json` → gera `data/courses.json`, `data/courses.csv`, `data/catalog.md` e imprime o summary report.

Execute ao final e mostre o output completo do summary report.
