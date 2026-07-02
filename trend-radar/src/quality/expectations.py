# src/quality/expectations.py — Validação de qualidade de dados com Great Expectations 1.x

import logging
from typing import Any

import duckdb
import great_expectations as gx
from great_expectations import expectations as gxe

logger = logging.getLogger(__name__)


def _run_suite(
    df,
    suite_name: str,
    expectations: list,
) -> dict[str, Any]:
    """Executa um suite de expectativas em um DataFrame e retorna o resultado padronizado.

    Usa contexto ephemeral — sem necessidade de `great_expectations init`.
    """
    context = gx.get_context(mode="ephemeral")

    datasource = context.data_sources.add_pandas(f"{suite_name}_source")
    asset = datasource.add_dataframe_asset(f"{suite_name}_asset")
    batch_def = asset.add_batch_definition_whole_dataframe("batch")

    suite = gx.ExpectationSuite(name=suite_name)
    for exp in expectations:
        suite.add_expectation(exp)
    suite = context.suites.add(suite)

    validation_def = context.validation_definitions.add(
        gx.ValidationDefinition(
            name=f"{suite_name}_validation",
            data=batch_def,
            suite=suite,
        )
    )

    results = validation_def.run(batch_parameters={"dataframe": df})

    failed = [
        {
            "expectation_type": r.expectation_config.type,
            "kwargs": r.expectation_config.kwargs,
            "result": r.result,
        }
        for r in results.results
        if not r.success
    ]

    logger.info(
        "[GE] Suite '%s': success=%s failed=%d/%d",
        suite_name,
        results.success,
        len(failed),
        len(results.results),
    )

    return {
        "success": results.success,
        "failed": failed,
        "stats": results.statistics,
    }


def validate_bronze_lastfm(
    conn: duckdb.DuckDBPyConnection,
    week_start: str,
) -> dict[str, Any]:
    """Valida bronze_lastfm_artist_weekly para a semana informada.

    Expectativas:
    - Colunas obrigatórias existem: artist_name, week_start, listeners
    - artist_name sem nulos
    - listeners entre 0 e 50 000 000
    - playcount >= 0
    - Contagem de linhas entre 50 e 250
    - (artist_name, week_start) únicos
    """
    df = conn.execute(
        f"SELECT * FROM bronze_lastfm_artist_weekly WHERE week_start = '{week_start}'"
    ).df()

    expectations = [
        gxe.ExpectColumnToExist(column="artist_name"),
        gxe.ExpectColumnToExist(column="week_start"),
        gxe.ExpectColumnToExist(column="listeners"),
        gxe.ExpectColumnValuesToNotBeNull(column="artist_name"),
        gxe.ExpectColumnValuesToBeBetween(
            column="listeners", min_value=0, max_value=50_000_000
        ),
        gxe.ExpectColumnValuesToBeBetween(column="playcount", min_value=0),
        gxe.ExpectTableRowCountToBeBetween(min_value=50, max_value=250),
        gxe.ExpectCompoundColumnsToBeUnique(
            column_list=["artist_name", "week_start"]
        ),
    ]

    return _run_suite(df, "bronze_lastfm", expectations)


def validate_bronze_youtube(
    conn: duckdb.DuckDBPyConnection,
    week_start: str,
) -> dict[str, Any]:
    """Valida bronze_youtube_channel_weekly para a semana informada.

    Expectativas:
    - channel_id não nulo quando weekly_views > 0
    - weekly_views >= 0
    - subscriber_count entre 0 e 500 000 000
    - Contagem de linhas entre 10 e 500
    - (channel_id, week_start) únicos quando channel_id não é nulo
    """
    df = conn.execute(
        f"SELECT * FROM bronze_youtube_channel_weekly WHERE week_start = '{week_start}'"
    ).df()

    # Filtra apenas linhas com weekly_views > 0 para checar channel_id
    df_with_views = df[df["weekly_views"] > 0] if "weekly_views" in df.columns else df

    expectations = [
        gxe.ExpectColumnToExist(column="channel_id"),
        gxe.ExpectColumnToExist(column="weekly_views"),
        gxe.ExpectColumnToExist(column="subscriber_count"),
        gxe.ExpectColumnValuesToBeBetween(column="weekly_views", min_value=0),
        gxe.ExpectColumnValuesToBeBetween(
            column="subscriber_count", min_value=0, max_value=500_000_000
        ),
        gxe.ExpectTableRowCountToBeBetween(min_value=10, max_value=500),
    ]

    return _run_suite(df, "bronze_youtube", expectations)
