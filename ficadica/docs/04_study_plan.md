# Prompt 04 — Geração do Plano de Estudos Personalizado

## Como usar este prompt

Execute após o Prompt 03 ter gerado `data/courses.json`. Cole no Claude Code.

## PROMPT PARA O CLAUDE CODE:

Crie o módulo de geração de plano de estudos personalizado para o Fica a Dica Premium. O plano deve ser baseado no catálogo mapeado e no perfil do usuário.

### Arquivo `study_plan/user_profile.json`

Crie o perfil do usuário como arquivo JSON configurável:

```json
{
  "name": "Dave",
  "level": "intermediário-avançado",
  "instruments": ["guitarra"],
  "styles": ["jazz", "mpb", "bossa nova", "blues"],
  "goals": [
    "aprimorar improvisação em jazz",
    "expandir vocabulário harmônico",
    "dominar escalas para contextos modais",
    "desenvolver fraseologia MPB/jazz"
  ],
  "available_hours_per_week": 5,
  "study_session_minutes": 45,
  "priorities": {
    "high": ["improvisação", "harmonia", "escalas"],
    "medium": ["técnica", "repertório", "ritmo"],
    "low": ["leitura", "composição", "produção", "carreira"]
  },
  "exclude_categories": ["piano", "canto", "bateria", "baixo"],
  "preferred_instructors": ["Nelson Faria", "Alexandre Carvalho"],
  "skip_beginner": true
}
```

### Arquivo `study_plan/planner.py`

```python
class StudyPlanner:
    """
    Gera plano de estudos personalizado com base no catálogo e perfil do usuário.
    """

    def generate_plan(self, courses: list[dict], profile: dict, plan_weeks: int = 24) -> dict:
        """
        Gera plano de estudos para N semanas.

        Retorna:
        {
            "profile_summary": str,
            "total_weeks": int,
            "total_hours": float,
            "weekly_hours": float,
            "phases": [
                {
                    "phase": int,
                    "title": str,
                    "weeks": str,          # ex: "1-6"
                    "focus": str,
                    "description": str,
                    "courses": [
                        {
                            "course_id": str,
                            "title": str,
                            "instructor": str,
                            "why": str,    # justificativa personalizada
                            "priority": str,  # "principal" ou "complementar"
                            "suggested_start_week": int,
                            "estimated_weeks": int,
                            "sessions_per_week": int,
                            "session_focus": str   # dica de como estudar
                        }
                    ],
                    "weekly_practice_tips": list[str],
                    "milestone": str       # o que o usuário deve conseguir fazer
                }
            ],
            "parallel_practices": list[str],  # o que praticar em paralelo sempre
            "recommended_order_rationale": str
        }
        """

    def _select_courses_for_phase(self, courses, phase_focus, profile, already_scheduled) -> list[dict]:
        """
        Seleciona cursos para uma fase considerando:
        - Foco da fase (categorias prioritárias)
        - Perfil do usuário (estilos, objetivos)
        - Cursos já agendados (sem repetição)
        - Pré-requisitos lógicos (ex: escalas antes de improvisação)
        """

    def _estimate_course_weeks(self, course: dict, sessions_per_week: int = 3) -> int:
        """
        Estima semanas necessárias para completar um curso.
        Considera: total_duration_minutes / (sessions_per_week * session_minutes)
        Adiciona 30% de buffer para prática e revisão.
        """

    def _generate_session_focus(self, course: dict, phase: str) -> str:
        """
        Gera dica específica de como abordar o curso nesta fase.
        Ex: "Foque nas escalas menores e modos primeiro, depois integre com backing tracks"
        """

    def _build_parallel_practices(self, profile: dict) -> list[str]:
        """
        Lista de práticas paralelas para fazer sempre, independente do curso:
        - Improv diário sobre backing tracks (15 min)
        - Transcrição de solos (1x semana)
        - Repertório: tocar músicas completas (2x semana)
        """
```

### Arquivo `study_plan/report_generator.py`

```python
class PlanReportGenerator:
    """Gera relatórios do plano de estudos em múltiplos formatos."""

    def to_json(self, plan: dict, path: str):
        """Salva em data/study_plan.json"""

    def to_markdown(self, plan: dict, path: str):
        """
        Gera data/study_plan.md — documento completo e formatado.

        Estrutura:
        # Plano de Estudos — Fica a Dica Premium
        ## Resumo do Perfil
        ## Visão Geral (tabela de fases)
        ## Fase 1: [título]
        ### Cursos Principais
        ### Cursos Complementares
        ### Dicas de Prática Semanal
        ### Marco: o que você vai conseguir fazer
        ## Práticas Paralelas (sempre ativas)
        ## Racional da Sequência
        """

    def to_rich_terminal(self, plan: dict):
        """
        Exibe plano formatado no terminal usando rich:
        - Painel de resumo
        - Tabela de fases com cores
        - Lista de cursos por fase
        """
```

### Script `run_planner.py` na raiz:

```python
"""
Gera plano de estudos personalizado.
Uso: python run_planner.py [--weeks N] [--profile PATH]
"""
```

- Carrega `data/courses.json`
- Carrega `study_plan/user_profile.json`
- Gera plano para 24 semanas (padrão)
- Salva `data/study_plan.json` e `data/study_plan.md`
- Exibe resumo no terminal

**Estrutura de fases sugerida para o perfil do usuário:**

```
Fase 1 (semanas 1-6):   FUNDAMENTOS AVANÇADOS
  Foco: Harmonia + Escalas (bases sólidas para improv)
  Cursos: Harmonia, Escalas, Acordes

Fase 2 (semanas 7-14):  LINGUAGEM E IMPROVISAÇÃO
  Foco: Improvisação + Fraseologia Jazz/MPB
  Cursos: Improvisação, Guitarra Jazz, Blue Bossa trilha

Fase 3 (semanas 15-20): REPERTÓRIO E APLICAÇÃO
  Foco: Repertório + Standards + Chord Melody
  Cursos: A Arte do Chord Melody, Aprenda com o Compositor, Standards

Fase 4 (semanas 21-24): APROFUNDAMENTO E ESTILO
  Foco: Cursos específicos de alto interesse (jazz avançado, modal)
  Cursos: selecionados por prioridade máxima do usuário
```

Execute ao final e mostre o plano completo no terminal.
