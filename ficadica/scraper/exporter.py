import json
import csv
from pathlib import Path
from collections import Counter, defaultdict

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

PRIORITY_STARS = {5: "⭐⭐⭐⭐⭐", 4: "⭐⭐⭐⭐", 3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐"}


class DataExporter:
    """Exporta o catálogo em múltiplos formatos."""

    def to_json(self, courses: list[dict], path: str):
        """Salva JSON formatado em data/courses.json."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(courses, f, ensure_ascii=False, indent=2)
        console.print(f"[green]JSON salvo:[/green] {path} ({len(courses)} cursos)")

    def to_csv(self, courses: list[dict], path: str):
        """Salva CSV flat em data/courses.csv."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "id", "title", "instructor", "category", "pillar", "level",
            "style_focus", "instrument_focus", "total_lessons",
            "total_duration_minutes", "priority_for_user", "url",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for c in courses:
                writer.writerow({
                    "id": c.get("id", ""),
                    "title": c.get("title", ""),
                    "instructor": c.get("instructor", ""),
                    "category": c.get("category", ""),
                    "pillar": c.get("pillar", ""),
                    "level": c.get("level", ""),
                    "style_focus": ", ".join(c.get("style_focus", [])),
                    "instrument_focus": ", ".join(c.get("instrument_focus", [])),
                    "total_lessons": c.get("total_lessons", 0),
                    "total_duration_minutes": c.get("total_duration_minutes", 0),
                    "priority_for_user": c.get("priority_for_user", 3),
                    "url": c.get("url", ""),
                })
        console.print(f"[green]CSV salvo:[/green] {path}")

    def to_markdown_catalog(self, courses: list[dict], path: str):
        """Gera data/catalog.md — catálogo agrupado por categoria, ordenado por prioridade."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        by_category = defaultdict(list)
        for c in courses:
            by_category[c.get("category", "outros")].append(c)

        lines = ["# Catálogo Fica a Dica Premium\n"]
        lines.append(f"**Total:** {len(courses)} cursos\n")
        total_hours = sum(c.get("total_duration_minutes", 0) for c in courses) // 60
        lines.append(f"**Horas de conteúdo:** ~{total_hours}h\n\n---\n")

        for category in sorted(by_category.keys()):
            cat_courses = sorted(
                by_category[category],
                key=lambda c: c.get("priority_for_user", 0),
                reverse=True,
            )
            lines.append(f"\n## {category.title()}\n")
            for c in cat_courses:
                priority = c.get("priority_for_user", 3)
                stars = PRIORITY_STARS.get(priority, "⭐⭐⭐")
                dur_h = c.get("total_duration_minutes", 0) // 60
                dur_m = c.get("total_duration_minutes", 0) % 60
                dur_str = f"{dur_h}h{dur_m:02d}m" if dur_h else f"{dur_m}min"
                styles = ", ".join(c.get("style_focus", [])) or "—"
                lines.append(
                    f"### {stars} {c.get('title', '')}\n"
                    f"- **Instrutor:** {c.get('instructor', '—')}\n"
                    f"- **Nível:** {c.get('level', '—')}\n"
                    f"- **Estilos:** {styles}\n"
                    f"- **Aulas:** {c.get('total_lessons', 0)} | "
                    f"**Duração:** {dur_str}\n"
                    f"- **URL:** {c.get('url', '')}\n"
                )
                if c.get("description"):
                    lines.append(f"\n> {c['description'][:200]}...\n")
                lines.append("\n")

        Path(path).write_text("".join(lines), encoding="utf-8")
        console.print(f"[green]Markdown salvo:[/green] {path}")

    def summary_report(self, courses: list[dict]) -> str:
        """Imprime relatório resumido com rich.table."""
        console.rule("[bold cyan]Relatório do Catálogo — Fica a Dica Premium[/bold cyan]")

        # Totais gerais
        total_lessons = sum(c.get("total_lessons", 0) for c in courses)
        total_minutes = sum(c.get("total_duration_minutes", 0) for c in courses)
        total_hours = total_minutes // 60

        console.print(
            f"\n[bold]Cursos:[/bold] {len(courses)}  |  "
            f"[bold]Aulas:[/bold] {total_lessons}  |  "
            f"[bold]Conteúdo:[/bold] ~{total_hours}h\n"
        )

        # Cursos por categoria
        cat_table = Table(title="Cursos por Categoria", box=box.ROUNDED)
        cat_table.add_column("Categoria", style="cyan")
        cat_table.add_column("Cursos", justify="right")
        cat_table.add_column("Aulas", justify="right")
        cat_table.add_column("Horas", justify="right")

        by_cat = defaultdict(list)
        for c in courses:
            by_cat[c.get("category", "outros")].append(c)

        for cat in sorted(by_cat.keys()):
            cat_courses = by_cat[cat]
            cat_lessons = sum(c.get("total_lessons", 0) for c in cat_courses)
            cat_hours = sum(c.get("total_duration_minutes", 0) for c in cat_courses) // 60
            cat_table.add_row(cat.title(), str(len(cat_courses)), str(cat_lessons), f"{cat_hours}h")

        console.print(cat_table)

        # Top 10 por prioridade
        top10 = sorted(courses, key=lambda c: c.get("priority_for_user", 0), reverse=True)[:10]
        top_table = Table(title="\nTop 10 por Prioridade (Perfil do Usuário)", box=box.ROUNDED)
        top_table.add_column("#", justify="right", style="dim")
        top_table.add_column("Curso", style="bold")
        top_table.add_column("Categoria")
        top_table.add_column("Nível")
        top_table.add_column("Prioridade", justify="center")
        top_table.add_column("Aulas", justify="right")

        for i, c in enumerate(top10, 1):
            stars = PRIORITY_STARS.get(c.get("priority_for_user", 3), "⭐⭐⭐")
            top_table.add_row(
                str(i),
                c.get("title", ""),
                c.get("category", ""),
                c.get("level", ""),
                stars,
                str(c.get("total_lessons", 0)),
            )

        console.print(top_table)

        # Professores mais presentes
        instructor_counter = Counter(
            c.get("instructor", "Desconhecido") for c in courses if c.get("instructor")
        )
        instr_table = Table(title="\nProfessores", box=box.ROUNDED)
        instr_table.add_column("Instrutor", style="cyan")
        instr_table.add_column("Cursos", justify="right")
        instr_table.add_column("Aulas", justify="right")

        for instructor, count in instructor_counter.most_common():
            inst_courses = [c for c in courses if c.get("instructor") == instructor]
            inst_lessons = sum(c.get("total_lessons", 0) for c in inst_courses)
            instr_table.add_row(instructor, str(count), str(inst_lessons))

        console.print(instr_table)

        return ""
