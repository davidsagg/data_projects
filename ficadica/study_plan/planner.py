import math

# Fases do plano com foco, título e descrição
PLAN_PHASES = [
    {
        "phase": 1,
        "title": "Fundamentos Avançados",
        "weeks_range": (1, 6),
        "focus_categories": ["harmonia", "escalas", "teoria"],
        "focus_label": "Harmonia + Escalas",
        "description": (
            "Construir base sólida de teoria aplicada: escalas modais, "
            "campo harmônico avançado e tensões. Fundação para tudo que vem depois."
        ),
        "milestone": (
            "Conseguir identificar e tocar as 5 digitações das escalas modais "
            "e construir acordes com tensões sobre qualquer grau do campo harmônico."
        ),
        "tips": [
            "Pratique as 5 digitações de cada escala em todos os tons (use o metrônomo).",
            "Analise harmonicamente 1 música por semana que você já conhece.",
            "Toque as escalas sobre backing tracks simples, sem se preocupar com 'soar bem' ainda.",
            "Mantenha um caderno de anotações dos modos e suas aplicações.",
        ],
    },
    {
        "phase": 2,
        "title": "Linguagem e Improvisação",
        "weeks_range": (7, 14),
        "focus_categories": ["improvisação", "escalas", "harmonia"],
        "focus_label": "Improvisação + Fraseologia Jazz/MPB",
        "description": (
            "Transformar conhecimento técnico em linguagem musical. "
            "Desenvolver vocabulário de frases jazz e MPB, aprender a improvisar "
            "sobre II-V-I e progressões modais."
        ),
        "milestone": (
            "Conseguir improvisar com fluidez sobre um II-V-I em 3 tonalidades, "
            "usando pelo menos 2 modos diferentes por progressão."
        ),
        "tips": [
            "Transcreva 1 frase por semana de um solo de referência (Wes Montgomery, Pat Metheny).",
            "Improvise 15 min/dia sobre backing tracks de jazz (iReal Pro ou YouTube).",
            "Aprenda 2 standards completos: tema + improv + reharmonização simples.",
            "Grave suas improvisações e ouça criticamente depois.",
        ],
    },
    {
        "phase": 3,
        "title": "Repertório e Aplicação",
        "weeks_range": (15, 20),
        "focus_categories": ["repertório", "técnica", "ritmo"],
        "focus_label": "Repertório + Standards + Chord Melody",
        "description": (
            "Aplicar o conhecimento acumulado em músicas reais. "
            "Montar repertório de jazz e MPB, desenvolver chord melody "
            "e aprofundar levadas e grooves brasileiros."
        ),
        "milestone": (
            "Ter 5 músicas completas no repertório (com arranjo próprio), "
            "incluindo pelo menos 2 standards de jazz e 2 músicas de MPB."
        ),
        "tips": [
            "Escolha 1 standard por quinzena e prepare versão completa: tema + improv + chord melody.",
            "Grave um vídeo curto de cada música finalizada — isso exige qualidade real.",
            "Trabalhe as levadas específicas de cada estilo (samba, bossa, shuffle de jazz).",
            "Toque com outros músicos sempre que possível — o repertório precisa de contexto real.",
        ],
    },
    {
        "phase": 4,
        "title": "Aprofundamento e Estilo",
        "weeks_range": (21, 24),
        "focus_categories": ["improvisação", "harmonia", "composição"],
        "focus_label": "Jazz Avançado + Modal + Estilo Próprio",
        "description": (
            "Aprofundar nos tópicos de maior afinidade e desenvolver identidade musical. "
            "Explorar reharmonização, escala alterada, linguagem modal avançada "
            "e começar a compor/arranjar no estilo próprio."
        ),
        "milestone": (
            "Conseguir reharmonizar uma música conhecida, usar a escala alterada "
            "sobre dominantes e demonstrar um estilo pessoal reconhecível na improvisação."
        ),
        "tips": [
            "Mergulhe em 1 álbum de referência: transcreva, analise, imite e depois subverta.",
            "Componha pelo menos 1 música curta no estilo jazz/MPB com harmonia própria.",
            "Revise os módulos mais desafiadores das fases anteriores.",
            "Defina seus próximos objetivos musicais — o plano de 24 semanas é um começo.",
        ],
    },
]

PARALLEL_PRACTICES = [
    "Improv diário sobre backing tracks (15 min) — mantenha isso em TODAS as fases.",
    "Transcrição de solos: 1 frase por semana de um guitarrista de referência.",
    "Repertório ativo: toque músicas completas pelo menos 2x por semana.",
    "Ear training: cante os intervalos e arpeje os acordes que estuda.",
    "Metrônomo: toda prática técnica com metrônomo, começando lento.",
]

RECOMMENDED_ORDER_RATIONALE = (
    "A sequência foi desenhada seguindo a lógica teoria → linguagem → aplicação → estilo. "
    "Escala e harmonia primeiro porque são o vocabulário: sem saber o que as notas significam "
    "harmonicamente, a improvisação é aleatória. Com essa base, a Fase 2 desenvolve fraseologia "
    "real — não apenas 'tocar as escalas certas', mas usá-las com intenção musical. "
    "A Fase 3 ancora tudo em músicas reais, que é onde o conhecimento se consolida de verdade. "
    "Por fim, a Fase 4 é o espaço para aprofundamento pessoal e desenvolvimento de estilo."
)


class StudyPlanner:
    """
    Gera plano de estudos personalizado com base no catálogo e perfil do usuário.
    """

    def generate_plan(
        self,
        courses: list[dict],
        profile: dict,
        plan_weeks: int = 24,
    ) -> dict:
        """Gera plano de estudos para N semanas."""
        sessions_per_week = max(1, profile["available_hours_per_week"] * 60 // profile["study_session_minutes"])
        weekly_hours = profile["available_hours_per_week"]
        total_hours = weekly_hours * plan_weeks

        filtered = self._filter_courses(courses, profile)

        phases = []
        scheduled_ids = []

        for phase_def in PLAN_PHASES:
            # Ajustar range de semanas se plan_weeks < 24
            w_start, w_end = phase_def["weeks_range"]
            if w_start > plan_weeks:
                continue
            w_end = min(w_end, plan_weeks)
            phase_weeks = w_end - w_start + 1

            selected = self._select_courses_for_phase(
                filtered,
                phase_def["focus_categories"],
                profile,
                scheduled_ids,
            )

            phase_courses = []
            week_cursor = w_start
            for i, course in enumerate(selected):
                priority_label = "principal" if i < 2 else "complementar"
                est_weeks = self._estimate_course_weeks(
                    course,
                    sessions_per_week,
                    profile["study_session_minutes"],
                )
                est_weeks = min(est_weeks, phase_weeks)
                phase_courses.append({
                    "course_id": course["id"],
                    "title": course["title"],
                    "instructor": course.get("instructor", ""),
                    "why": self._build_why(course, profile, phase_def),
                    "priority": priority_label,
                    "suggested_start_week": week_cursor,
                    "estimated_weeks": est_weeks,
                    "sessions_per_week": sessions_per_week,
                    "session_focus": self._generate_session_focus(course, phase_def["title"]),
                })
                scheduled_ids.append(course["id"])
                if priority_label == "principal":
                    week_cursor = min(week_cursor + est_weeks, w_end)

            phases.append({
                "phase": phase_def["phase"],
                "title": phase_def["title"],
                "weeks": f"{w_start}-{w_end}",
                "focus": phase_def["focus_label"],
                "description": phase_def["description"],
                "courses": phase_courses,
                "weekly_practice_tips": phase_def["tips"],
                "milestone": phase_def["milestone"],
            })

        goals_str = "; ".join(profile.get("goals", []))
        profile_summary = (
            f"{profile['name']} | Nível: {profile['level']} | "
            f"Instrumento: {', '.join(profile['instruments'])} | "
            f"Estilos: {', '.join(profile['styles'])} | "
            f"{weekly_hours}h/semana | Objetivos: {goals_str}"
        )

        return {
            "profile_summary": profile_summary,
            "total_weeks": plan_weeks,
            "total_hours": round(total_hours, 1),
            "weekly_hours": weekly_hours,
            "phases": phases,
            "parallel_practices": PARALLEL_PRACTICES,
            "recommended_order_rationale": RECOMMENDED_ORDER_RATIONALE,
        }

    def _filter_courses(self, courses: list[dict], profile: dict) -> list[dict]:
        """Remove cursos excluídos pelo perfil e iniciantes se skip_beginner=True."""
        excluded_cats = [c.lower() for c in profile.get("exclude_categories", [])]
        skip_beginner = profile.get("skip_beginner", True)

        result = []
        for c in courses:
            # Excluir por foco de instrumento
            instrument_focus = [i.lower() for i in c.get("instrument_focus", [])]
            if any(excl in instrument_focus for excl in excluded_cats):
                continue
            # Excluir iniciante
            if skip_beginner and c.get("level") == "Iniciante":
                continue
            result.append(c)
        return result

    def _select_courses_for_phase(
        self,
        courses: list[dict],
        phase_focus: list[str],
        profile: dict,
        already_scheduled: list[str],
    ) -> list[dict]:
        """Seleciona e ordena cursos para uma fase."""
        high_prio = profile.get("priorities", {}).get("high", [])
        medium_prio = profile.get("priorities", {}).get("medium", [])
        preferred_instructors = [i.lower() for i in profile.get("preferred_instructors", [])]
        user_styles = [s.lower() for s in profile.get("styles", [])]

        available = [c for c in courses if c["id"] not in already_scheduled]

        def score(course):
            s = 0
            cat = course.get("category", "")
            # Prioridade de fase
            if cat in phase_focus:
                s += 10
            # Prioridades do perfil
            if cat in high_prio:
                s += 5
            elif cat in medium_prio:
                s += 2
            # Estilos do usuário
            course_styles = [st.lower() for st in course.get("style_focus", [])]
            if any(st in course_styles for st in user_styles):
                s += 3
            # Instrutor preferido
            if course.get("instructor", "").lower() in preferred_instructors:
                s += 2
            # Prioridade calculada pelo parser
            s += course.get("priority_for_user", 3)
            return s

        return sorted(available, key=score, reverse=True)[:4]

    def _estimate_course_weeks(
        self,
        course: dict,
        sessions_per_week: int,
        session_minutes: int,
    ) -> int:
        """Estima semanas para completar o curso com buffer de 30%."""
        total_min = course.get("total_duration_minutes", 0)
        if total_min == 0:
            return 2
        minutes_per_week = sessions_per_week * session_minutes
        raw_weeks = total_min / minutes_per_week
        with_buffer = raw_weeks * 1.3
        return max(1, math.ceil(with_buffer))

    def _generate_session_focus(self, course: dict, phase_title: str) -> str:
        """Gera dica específica de como abordar o curso na fase."""
        cat = course.get("category", "")
        title = course.get("title", "")
        styles = course.get("style_focus", [])
        style_hint = f" com foco em {', '.join(styles)}" if styles else ""

        tips_by_category = {
            "escalas": (
                f"Aprenda as digitações em blocos de 2-3 por sessão. "
                f"Sempre finalize a sessão improvisando{style_hint} sobre backing track."
            ),
            "harmonia": (
                f"Estude os acordes no braço primeiro, depois analise progressões reais{style_hint}. "
                f"Aplique imediatamente em músicas que você já conhece."
            ),
            "improvisação": (
                f"Alterne entre assistir a aula e improvisar sobre o mesmo contexto{style_hint}. "
                f"Grave suas tentativas — a autocrítica é parte do processo."
            ),
            "técnica": (
                f"Use metrônomo em todas as sessões técnicas. "
                f"Comece 20% abaixo do tempo confortável e suba gradualmente."
            ),
            "repertório": (
                f"Aprenda cada música em partes: tema → harmonia → improv → arranjo. "
                f"Só avance quando cada parte estiver sólida{style_hint}."
            ),
            "ritmo": (
                f"Toque com metrônomo e também com drummers virtuais{style_hint}. "
                f"Grave e compare com a referência original."
            ),
        }

        return tips_by_category.get(
            cat,
            f"Siga o currículo do curso e aplique cada conceito em contexto musical real{style_hint}.",
        )

    def _build_why(self, course: dict, profile: dict, phase_def: dict) -> str:
        """Gera justificativa personalizada para incluir o curso no plano."""
        cat = course.get("category", "")
        styles = course.get("style_focus", [])
        user_goals = profile.get("goals", [])

        goal_map = {
            "escalas": "dominar escalas para contextos modais",
            "harmonia": "expandir vocabulário harmônico",
            "improvisação": "aprimorar improvisação em jazz",
            "repertório": "desenvolver fraseologia MPB/jazz",
            "técnica": "aprimorar técnica instrumental",
        }
        matched_goal = goal_map.get(cat, "")

        style_context = ""
        if styles:
            matching = [s for s in styles if s in profile.get("styles", [])]
            if matching:
                style_context = f" com conteúdo direto de {', '.join(matching)}"

        phase_context = f"Essencial na {phase_def['title']}: {phase_def['focus_label']}."

        if matched_goal and matched_goal in user_goals:
            return (
                f"{phase_context} Alinhado diretamente com seu objetivo: '{matched_goal}'{style_context}."
            )

        return f"{phase_context} Complementa o desenvolvimento{style_context} nesta etapa."
