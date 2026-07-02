import json
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.text import Text

console = Console()

PRIORITY_COLOR = {
    "principal": "bold green",
    "complementar": "yellow",
}


class PlanReportGenerator:
    """Gera relatórios do plano de estudos em múltiplos formatos."""

    def to_json(self, plan: dict, path: str):
        """Salva em data/study_plan.json."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        console.print(f"[green]JSON salvo:[/green] {path}")

    def to_markdown(self, plan: dict, path: str):
        """Gera data/study_plan.md — documento completo e formatado."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        lines = []

        lines.append("# Plano de Estudos — Fica a Dica Premium\n")
        lines.append(f"**Duração:** {plan['total_weeks']} semanas  ")
        lines.append(f"**Carga total:** ~{plan['total_hours']}h  ")
        lines.append(f"**Ritmo:** {plan['weekly_hours']}h/semana\n")

        # Resumo do perfil
        lines.append("## Resumo do Perfil\n")
        lines.append(f"> {plan['profile_summary']}\n")

        # Visão geral
        lines.append("\n## Visão Geral\n")
        lines.append("| Fase | Semanas | Foco | Cursos |\n")
        lines.append("|------|---------|------|--------|\n")
        for phase in plan["phases"]:
            n_courses = len(phase["courses"])
            lines.append(
                f"| Fase {phase['phase']}: {phase['title']} "
                f"| {phase['weeks']} "
                f"| {phase['focus']} "
                f"| {n_courses} cursos |\n"
            )

        # Fases
        for phase in plan["phases"]:
            lines.append(f"\n---\n\n## Fase {phase['phase']}: {phase['title']}\n")
            lines.append(f"**Semanas:** {phase['weeks']}  \n")
            lines.append(f"**Foco:** {phase['focus']}  \n\n")
            lines.append(f"{phase['description']}\n")

            # Cursos principais
            principals = [c for c in phase["courses"] if c["priority"] == "principal"]
            complementares = [c for c in phase["courses"] if c["priority"] == "complementar"]

            if principals:
                lines.append("\n### Cursos Principais\n")
                for c in principals:
                    lines.append(f"#### {c['title']}")
                    if c.get("instructor"):
                        lines.append(f" *(por {c['instructor']})*")
                    lines.append("\n")
                    lines.append(f"- **Por que:** {c['why']}\n")
                    lines.append(
                        f"- **Início sugerido:** semana {c['suggested_start_week']}  "
                        f"**Duração estimada:** {c['estimated_weeks']} semanas  "
                        f"**Sessões/semana:** {c['sessions_per_week']}\n"
                    )
                    lines.append(f"- **Como estudar:** {c['session_focus']}\n")

            if complementares:
                lines.append("\n### Cursos Complementares\n")
                for c in complementares:
                    lines.append(f"#### {c['title']}")
                    if c.get("instructor"):
                        lines.append(f" *(por {c['instructor']})*")
                    lines.append("\n")
                    lines.append(f"- **Por que:** {c['why']}\n")
                    lines.append(f"- **Como estudar:** {c['session_focus']}\n")

            # Dicas e marco
            if phase.get("weekly_practice_tips"):
                lines.append("\n### Dicas de Prática Semanal\n")
                for tip in phase["weekly_practice_tips"]:
                    lines.append(f"- {tip}\n")

            lines.append(f"\n### Marco: o que você vai conseguir fazer\n")
            lines.append(f"> {phase['milestone']}\n")

        # Práticas paralelas
        lines.append("\n---\n\n## Práticas Paralelas (sempre ativas)\n")
        for p in plan["parallel_practices"]:
            lines.append(f"- {p}\n")

        # Racional
        lines.append("\n## Racional da Sequência\n")
        lines.append(f"{plan['recommended_order_rationale']}\n")

        Path(path).write_text("".join(lines), encoding="utf-8")
        console.print(f"[green]Markdown salvo:[/green] {path}")

    def to_rich_terminal(self, plan: dict):
        """Exibe plano formatado no terminal usando rich."""
        console.rule("[bold cyan]Plano de Estudos — Fica a Dica Premium[/bold cyan]")

        # Painel de resumo
        summary_text = (
            f"[bold]{plan['profile_summary']}[/bold]\n\n"
            f"[cyan]Duração:[/cyan] {plan['total_weeks']} semanas  |  "
            f"[cyan]Carga total:[/cyan] ~{plan['total_hours']}h  |  "
            f"[cyan]Ritmo:[/cyan] {plan['weekly_hours']}h/semana"
        )
        console.print(Panel(summary_text, title="[bold green]Perfil do Estudante[/bold green]", expand=False))

        # Tabela de fases
        phase_table = Table(title="\nVisão Geral do Plano", box=box.ROUNDED, show_lines=True)
        phase_table.add_column("Fase", style="bold cyan", width=8)
        phase_table.add_column("Semanas", justify="center", width=10)
        phase_table.add_column("Título", style="bold", width=28)
        phase_table.add_column("Foco", width=30)
        phase_table.add_column("Cursos", justify="right", width=7)

        for phase in plan["phases"]:
            phase_table.add_row(
                f"Fase {phase['phase']}",
                phase["weeks"],
                phase["title"],
                phase["focus"],
                str(len(phase["courses"])),
            )

        console.print(phase_table)

        # Detalhe por fase
        for phase in plan["phases"]:
            console.print(f"\n[bold cyan]━━━ Fase {phase['phase']}: {phase['title']} "
                          f"(semanas {phase['weeks']}) ━━━[/bold cyan]")
            console.print(f"[dim]{phase['description']}[/dim]\n")

            if phase["courses"]:
                course_table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
                course_table.add_column("Curso", style="bold", min_width=20)
                course_table.add_column("Instrutor", min_width=16)
                course_table.add_column("Tipo", min_width=12)
                course_table.add_column("Início", justify="center", min_width=8)
                course_table.add_column("Semanas", justify="center", min_width=8)
                course_table.add_column("Por que", min_width=40)

                for c in phase["courses"]:
                    color = PRIORITY_COLOR.get(c["priority"], "white")
                    course_table.add_row(
                        c["title"],
                        c.get("instructor", "—"),
                        Text(c["priority"].upper(), style=color),
                        f"sem. {c['suggested_start_week']}",
                        f"~{c['estimated_weeks']}sem",
                        c["why"][:70] + ("…" if len(c["why"]) > 70 else ""),
                    )

                console.print(course_table)
            else:
                console.print(
                    f"  [yellow]Nenhum curso disponível no catálogo para esta fase ainda.[/yellow]\n"
                    f"  [dim]Execute run_scraper.py para mapear o catálogo completo.[/dim]\n"
                )

            # Marco
            console.print(
                Panel(
                    f"[bold]{phase['milestone']}[/bold]",
                    title="[green]Marco — O que você vai conseguir fazer[/green]",
                    border_style="green",
                    padding=(0, 1),
                )
            )

        # Práticas paralelas
        console.print("\n[bold cyan]━━━ Práticas Paralelas (sempre ativas) ━━━[/bold cyan]")
        for p in plan["parallel_practices"]:
            console.print(f"  • {p}")

        # Racional
        console.print(
            Panel(
                plan["recommended_order_rationale"],
                title="[bold]Racional da Sequência[/bold]",
                border_style="dim",
                padding=(0, 1),
            )
        )
