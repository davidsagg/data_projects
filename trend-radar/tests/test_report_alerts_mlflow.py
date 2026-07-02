# tests/test_report_alerts_mlflow.py
# TDD RED phase — TC-43 a TC-48: ReportGenerator, AlertEngine, MLflow tracking.

import json
import pytest
import duckdb
import httpx
from datetime import date, timedelta
from pathlib import Path

# Imports lazy — módulos ainda não existem
try:
    from src.report.generator import ReportGenerator, OllamaUnavailableError
except ModuleNotFoundError:
    ReportGenerator = None          # type: ignore[assignment,misc]
    OllamaUnavailableError = None   # type: ignore[assignment]

try:
    from src.report.alerts import AlertEngine
except ModuleNotFoundError:
    AlertEngine = None  # type: ignore[assignment,misc]

try:
    from src.report.mlflow_tracking import run_pipeline_with_tracking
except ModuleNotFoundError:
    run_pipeline_with_tracking = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# DDL helpers
# ---------------------------------------------------------------------------

_DDL_RISING = """
CREATE TABLE IF NOT EXISTS gold_rising_artists (
    artist_mbid         VARCHAR NOT NULL,
    artist_name         VARCHAR NOT NULL,
    genre               VARCHAR,
    country             VARCHAR DEFAULT 'BR',
    trend_score         DOUBLE,
    trending_direction  VARCHAR,
    week_start          DATE NOT NULL,
    PRIMARY KEY (artist_mbid, week_start)
);
"""

_DDL_ANOMALIES = """
CREATE TABLE IF NOT EXISTS gold_anomalies (
    artist_mbid     VARCHAR NOT NULL,
    artist_name     VARCHAR NOT NULL,
    week_start      DATE    NOT NULL,
    anomaly_score   DOUBLE,
    trigger_source  VARCHAR,
    PRIMARY KEY (artist_mbid, week_start)
);
"""

_DDL_TREND_SCORES = """
CREATE TABLE IF NOT EXISTS gold_trend_scores (
    artist_mbid     VARCHAR NOT NULL,
    artist_name     VARCHAR NOT NULL,
    week_start      DATE    NOT NULL,
    trend_score     DOUBLE,
    PRIMARY KEY (artist_mbid, week_start)
);
"""

WEEK_START = "2026-04-14"
PREV_WEEK  = "2026-04-07"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gold_data_for_report():
    """DuckDB com top 5 artistas em gold_rising_artists e 1 anomalia."""
    conn = duckdb.connect(":memory:")
    conn.execute(_DDL_RISING)
    conn.execute(_DDL_ANOMALIES)
    conn.execute(_DDL_TREND_SCORES)

    # colunas: artist_mbid, artist_name, genre, country, trend_score, trending_direction, week_start
    artists = [
        ("mbid-1", "Emicida",  "hip-hop", "BR", 92.0, "up",     WEEK_START),
        ("mbid-2", "Alcione",  "samba",   "BR", 85.0, "up",     WEEK_START),
        ("mbid-3", "Criolo",   "hip-hop", "BR", 78.0, "stable", WEEK_START),
        ("mbid-4", "Ludmilla", "funk",    "BR", 74.0, "up",     WEEK_START),
        ("mbid-5", "Ivete",    "axe",     "BR", 68.0, "stable", WEEK_START),
    ]
    conn.executemany(
        "INSERT INTO gold_rising_artists VALUES (?, ?, ?, ?, ?, ?, ?)",
        artists,
    )

    conn.execute(
        f"INSERT INTO gold_anomalies VALUES ('mbid-1', 'Emicida', '{WEEK_START}', 3.8, 'multi')"
    )

    yield conn
    conn.close()


@pytest.fixture
def mock_ollama(mocker):
    """Mock de httpx.post para o endpoint Ollama local."""
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.raise_for_status = mocker.MagicMock()
    mock_resp.json.return_value = {"response": "Relatório gerado com sucesso pelo LLM."}
    return mocker.patch("httpx.post", return_value=mock_resp)


@pytest.fixture
def mlflow_test_run(tmp_path):
    """Configura MLflow com tracking_uri isolado em tmp_path."""
    import mlflow
    uri = f"file://{tmp_path}/mlruns-test"
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("trend_radar")
    yield uri
    mlflow.set_tracking_uri(None)


# ---------------------------------------------------------------------------
# TC-43: relatório contém as 4 seções obrigatórias
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_report_contains_required_sections(mock_ollama, gold_data_for_report):
    if ReportGenerator is None:
        pytest.fail("ReportGenerator não implementado — RED phase")

    generator = ReportGenerator(
        conn=gold_data_for_report,
        ollama_url="http://localhost:11434/api/generate",
    )
    report = generator.generate(week_start=WEEK_START)

    assert isinstance(report, str), "generate() deve retornar uma string"
    for section in ("## Resumo Executivo", "## Top 5 Artistas",
                    "## Gênero da Semana", "## Destaque de Anomalia"):
        assert section in report, f"Seção ausente no relatório: '{section}'"


# ---------------------------------------------------------------------------
# TC-44: relatório salvo no caminho correto
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_report_saved_to_correct_path(mock_ollama, gold_data_for_report, tmp_path):
    if ReportGenerator is None:
        pytest.fail("ReportGenerator não implementado — RED phase")

    generator = ReportGenerator(
        conn=gold_data_for_report,
        ollama_url="http://localhost:11434/api/generate",
    )
    generator.generate_and_save(week_start=WEEK_START, data_dir=tmp_path)

    expected = tmp_path / f"{WEEK_START}_report.md"
    assert expected.exists(), f"Arquivo de relatório não encontrado em: {expected}"
    assert expected.stat().st_size > 0, "Arquivo de relatório está vazio"


# ---------------------------------------------------------------------------
# TC-45: Ollama indisponível → OllamaUnavailableError com mensagem clara
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_report_fails_gracefully_when_ollama_down(mocker, gold_data_for_report):
    if ReportGenerator is None or OllamaUnavailableError is None:
        pytest.fail("ReportGenerator / OllamaUnavailableError não implementado — RED phase")

    mocker.patch(
        "httpx.post",
        side_effect=httpx.ConnectError("Connection refused"),
    )

    generator = ReportGenerator(
        conn=gold_data_for_report,
        ollama_url="http://localhost:11434/api/generate",
    )

    with pytest.raises(OllamaUnavailableError) as exc_info:
        generator.generate(week_start=WEEK_START)

    msg = str(exc_info.value)
    assert "ollama" in msg.lower() or "llm" in msg.lower(), (
        f"Mensagem de erro não identifica o problema claramente: '{msg}'"
    )
    assert "ConnectError" not in msg, (
        "Mensagem não deve expor stacktrace interno; deve ser legível pelo usuário"
    )


# ---------------------------------------------------------------------------
# TC-46: alerta gerado para artista que cruza threshold pela 1ª vez
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_alert_generated_for_new_threshold_crossing(tmp_path, duckdb_conn):
    if AlertEngine is None:
        pytest.fail("AlertEngine não implementado — RED phase")

    duckdb_conn.execute(_DDL_TREND_SCORES)

    # Semana passada: score=60 (abaixo do threshold=65)
    duckdb_conn.execute(
        "INSERT INTO gold_trend_scores VALUES ('mbid-novo', 'Novo', ?, 60.0)",
        [PREV_WEEK],
    )
    # Semana atual: score=70 (cruzou threshold)
    duckdb_conn.execute(
        "INSERT INTO gold_trend_scores VALUES ('mbid-novo', 'Novo', ?, 70.0)",
        [WEEK_START],
    )

    alert_path = tmp_path / "alerts.json"
    engine = AlertEngine(conn=duckdb_conn, threshold=65.0, output_path=alert_path)
    engine.run(week_start=WEEK_START)

    assert alert_path.exists(), "Arquivo de alertas não foi criado"
    alerts = json.loads(alert_path.read_text())
    artist_names = [a["artist_name"] for a in alerts]
    assert "Novo" in artist_names, f"'Novo' deveria estar nos alertas: {artist_names}"

    novo_alert = next(a for a in alerts if a["artist_name"] == "Novo")
    assert novo_alert["type"] == "threshold_crossed", (
        f"type esperado 'threshold_crossed', obteve '{novo_alert['type']}'"
    )


# ---------------------------------------------------------------------------
# TC-47: artista acima do threshold há 3+ semanas NÃO gera alerta novo
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_no_duplicate_alert_for_continuing_artist(tmp_path, duckdb_conn):
    if AlertEngine is None:
        pytest.fail("AlertEngine não implementado — RED phase")

    duckdb_conn.execute(_DDL_TREND_SCORES)

    # Veterano já está acima de 65 há 3 semanas consecutivas
    for weeks_ago in (3, 2, 1, 0):
        w = (date.fromisoformat(WEEK_START) - timedelta(weeks=weeks_ago)).isoformat()
        duckdb_conn.execute(
            "INSERT INTO gold_trend_scores VALUES ('mbid-vet', 'Veterano', ?, 75.0)",
            [w],
        )

    alert_path = tmp_path / "alerts.json"
    engine = AlertEngine(conn=duckdb_conn, threshold=65.0, output_path=alert_path)
    engine.run(week_start=WEEK_START)

    if alert_path.exists():
        alerts = json.loads(alert_path.read_text())
        vet_alerts = [a for a in alerts if a["artist_name"] == "Veterano"]
        assert len(vet_alerts) == 0, (
            f"'Veterano' não deveria gerar alerta (já estava acima do threshold): {vet_alerts}"
        )


# ---------------------------------------------------------------------------
# TC-48: MLflow registra params, metrics e tags obrigatórios
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_mlflow_logs_required_params_and_metrics(duckdb_conn, mlflow_test_run):
    if run_pipeline_with_tracking is None:
        pytest.fail("run_pipeline_with_tracking não implementado — RED phase")

    duckdb_conn.execute(_DDL_RISING)
    duckdb_conn.execute(_DDL_TREND_SCORES)

    # Seed mínimo para a pipeline rodar
    duckdb_conn.execute(
        f"INSERT INTO gold_rising_artists VALUES "
        f"('mbid-x', 'Artista X', 'mpb', 'BR', 80.0, 'up', '{WEEK_START}')"
    )

    run_pipeline_with_tracking(
        conn=duckdb_conn,
        mlflow_uri=mlflow_test_run,
        week_start=WEEK_START,
    )

    import mlflow
    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name("trend_radar")
    assert experiment is not None, "Experimento 'trend_radar' não encontrado no MLflow"

    runs = client.search_runs(experiment_ids=[experiment.experiment_id])
    assert len(runs) > 0, "Nenhum run encontrado no experimento 'trend_radar'"

    last_run = runs[0]

    assert "weight_lastfm" in last_run.data.params, (
        f"Param 'weight_lastfm' ausente. Params: {last_run.data.params}"
    )
    assert "rising_artists_count" in last_run.data.metrics, (
        f"Metric 'rising_artists_count' ausente. Metrics: {last_run.data.metrics}"
    )
    assert "week_start" in last_run.data.tags, (
        f"Tag 'week_start' ausente. Tags: {last_run.data.tags}"
    )
