import yaml
from pathlib import Path

DBT = Path("dbt")


def test_dbt_project_valid():
    f = DBT / "dbt_project.yml"
    assert f.exists()
    c = yaml.safe_load(f.read_text())
    assert "name" in c and "version" in c and ("model-paths" in c or "models" in c)


def test_weekly_summary_exists():
    f = DBT / "models" / "weekly_summary.sql"
    assert f.exists()
    s = f.read_text().lower()
    assert "select" in s and "sum" in s and "tss" in s


def test_athlete_profile_exists():
    f = DBT / "models" / "athlete_profile.sql"
    assert f.exists()
    s = f.read_text().lower()
    assert "athlete_metrics" in s or "health_daily" in s


def test_docker_compose_has_services():
    import yaml
    f = Path(".devcontainer/docker-compose.yml")
    assert f.exists()
    c = yaml.safe_load(f.read_text())
    svcs = c.get("services", {})
    assert "app" in svcs and "airflow" in svcs and "mlflow" in svcs
