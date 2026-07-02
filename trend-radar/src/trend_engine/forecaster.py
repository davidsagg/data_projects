# src/trend_engine/forecaster.py — Previsão de trend_score com Prophet / Weighted MA

import logging
from datetime import date, timedelta
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

# Silencia logs verbosos do Prophet e CmdStanPy
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

_WEIGHTS_4 = [0.10, 0.15, 0.25, 0.50]  # mais recente tem maior peso


class TrendForecaster:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self.conn = conn
        self.method: str | None = None

    # ------------------------------------------------------------------
    # Ponto de entrada público
    # ------------------------------------------------------------------

    def forecast(self, artist_mbid: str, weeks_ahead: int = 4) -> list[dict[str, Any]]:
        """Prevê trend_score para as próximas `weeks_ahead` semanas.

        Usa Prophet se >= 12 semanas de histórico, caso contrário Weighted MA.

        Returns:
            Lista de dicts: {week, predicted_score, lower_bound, upper_bound}
        """
        history = self._get_history(artist_mbid)

        if len(history) >= 12:
            return self._prophet_forecast(history, weeks_ahead)
        return self._weighted_ma_forecast(history, weeks_ahead)

    # ------------------------------------------------------------------
    # Histórico
    # ------------------------------------------------------------------

    def _get_history(self, artist_mbid: str) -> list[tuple]:
        """Retorna [(week_start, score), ...] em ordem cronológica.

        Tenta gold_trend_scores primeiro; se a tabela não existir usa
        silver_weekly_plays com lastfm_plays como proxy de score.
        """
        try:
            rows = self.conn.execute(
                "SELECT week_start, trend_score "
                "FROM gold_trend_scores "
                "WHERE artist_mbid = ? AND trend_score IS NOT NULL "
                "ORDER BY week_start",
                [artist_mbid],
            ).fetchall()
            if rows:
                return rows
        except Exception:
            pass  # tabela não existe → fallback

        # Fallback: usa lastfm_plays normalizado como proxy de score
        rows = self.conn.execute(
            "SELECT week_start, CAST(lastfm_plays AS DOUBLE) "
            "FROM silver_weekly_plays "
            "WHERE artist_mbid = ? "
            "ORDER BY week_start",
            [artist_mbid],
        ).fetchall()
        return rows

    # ------------------------------------------------------------------
    # Prophet (>= 12 semanas)
    # ------------------------------------------------------------------

    def _prophet_forecast(self, history: list[tuple], periods: int) -> list[dict[str, Any]]:
        import pandas as pd
        from prophet import Prophet  # importação lazy para evitar overhead

        df = pd.DataFrame(history, columns=["ds", "y"])
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"] = df["y"].astype(float)

        m = Prophet(
            weekly_seasonality=False,
            yearly_seasonality=False,
            daily_seasonality=False,
            uncertainty_samples=200,
        )
        m.fit(df)

        future = m.make_future_dataframe(periods=periods, freq="W")
        forecast_df = m.predict(future)

        future_rows = forecast_df.tail(periods)
        result: list[dict[str, Any]] = []
        for _, row in future_rows.iterrows():
            result.append({
                "week":            row["ds"].date().isoformat(),
                "predicted_score": float(max(0.0, min(100.0, row["yhat"]))),
                "lower_bound":     float(max(0.0, row["yhat_lower"])),
                "upper_bound":     float(min(100.0, row["yhat_upper"])),
            })

        self.method = "prophet"
        logger.info("[TrendForecaster] Prophet: %d semanas previstas.", periods)
        return result

    # ------------------------------------------------------------------
    # Weighted Moving Average (< 12 semanas)
    # ------------------------------------------------------------------

    def _weighted_ma_forecast(self, history: list[tuple], periods: int) -> list[dict[str, Any]]:
        scores = [float(r[1] or 0) for r in history]

        # Últimas 4 semanas (ou menos se histórico curto)
        recent = scores[-4:]
        weights = _WEIGHTS_4[-len(recent):]
        total_w = sum(weights)
        normalized = [w / total_w for w in weights]

        predicted = sum(w * v for w, v in zip(normalized, recent))
        lower = predicted * 0.85
        upper = predicted * 1.15

        last_raw = history[-1][0]
        if isinstance(last_raw, str):
            last_date = date.fromisoformat(last_raw)
        else:
            last_date = last_raw  # already a date object

        result: list[dict[str, Any]] = []
        for i in range(1, periods + 1):
            result.append({
                "week":            (last_date + timedelta(weeks=i)).isoformat(),
                "predicted_score": predicted,
                "lower_bound":     lower,
                "upper_bound":     upper,
            })

        self.method = "weighted_ma"
        logger.info("[TrendForecaster] Weighted MA: %d semanas previstas.", periods)
        return result
