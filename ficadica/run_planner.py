"""
Gera plano de estudos personalizado.

Uso:
  python run_planner.py               # plano de 24 semanas com perfil padrão
  python run_planner.py --weeks 12    # plano mais curto
  python run_planner.py --profile study_plan/user_profile.json
"""

import argparse
import json
from pathlib import Path
from rich.console import Console

console = Console()

COURSES_PATH = "data/courses.json"
DEFAULT_PROFILE = "study_plan/user_profile.json"
OUTPUT_JSON = "data/study_plan.json"
OUTPUT_MD = "data/study_plan.md"


def main():
    parser = argparse.ArgumentParser(description="Gerador de plano de estudos — Fica a Dica Premium")
    parser.add_argument("--weeks", type=int, default=24, help="Duração do plano em semanas (padrão: 24)")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="Caminho do perfil JSON do usuário")
    args = parser.parse_args()

    # Carregar catálogo
    courses_path = Path(COURSES_PATH)
    if not courses_path.exists():
        console.print(f"[red]Catálogo não encontrado: {courses_path}[/red]")
        console.print("Execute primeiro: [cyan]python run_parser.py[/cyan]")
        raise SystemExit(1)

    with open(courses_path, encoding="utf-8") as f:
        courses = json.load(f)
    console.print(f"[cyan]Catálogo carregado:[/cyan] {len(courses)} cursos")

    # Carregar perfil
    profile_path = Path(args.profile)
    if not profile_path.exists():
        console.print(f"[red]Perfil não encontrado: {profile_path}[/red]")
        raise SystemExit(1)

    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)
    console.print(f"[cyan]Perfil carregado:[/cyan] {profile['name']} ({profile['level']})\n")

    # Gerar plano
    from study_plan.planner import StudyPlanner
    from study_plan.report_generator import PlanReportGenerator

    planner = StudyPlanner()
    plan = planner.generate_plan(courses, profile, plan_weeks=args.weeks)

    # Exportar
    reporter = PlanReportGenerator()
    reporter.to_json(plan, OUTPUT_JSON)
    reporter.to_markdown(plan, OUTPUT_MD)

    console.print()
    reporter.to_rich_terminal(plan)


if __name__ == "__main__":
    main()
